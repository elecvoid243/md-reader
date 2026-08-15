/**
 * render.js — Markdown 预览渲染管线
 *
 * 渲染流程：
 *   Markdown 原文 → marked.js 解析 → KaTeX 公式 → Mermaid 图表
 *   → highlight.js 代码高亮 → TOC 提取 → DOM 更新
 *
 * 通过 QWebChannel 与 Python 端双向通信。
 */

/* ========== 初始化 ========== */

// 配置 marked
marked.setOptions({
    gfm: true,          // GitHub Flavored Markdown
    breaks: true,       // 换行符转 <br>
    headerIds: true,    // 标题自动生成 id
    mangle: false,      // 不转义邮箱
});

// 配置 mermaid（延迟渲染，由我们手动触发）
mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
});

// QWebChannel 桥接对象
window.bridge = null;
window.jsReady = false;

// 初始化 QWebChannel（qt.webChannelTransport 缺失或连接失败时降级为
// standalone，避免顶层抛错中断后续 const 初始化，导致 renderMarkdown 进入 TDZ 错误）
try {
    if (
        typeof QWebChannel !== 'undefined'
        && typeof qt !== 'undefined'
        && qt.webChannelTransport
    ) {
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            window.jsReady = true;
            console.log('[render.js] QWebChannel connected');
        });
    } else {
        // 无 QWebChannel 时（如浏览器调试），标记为就绪
        window.jsReady = true;
        console.log('[render.js] No QWebChannel, standalone mode');
    }
} catch (e) {
    window.jsReady = true;
    console.warn('[render.js] QWebChannel init failed, standalone mode:', e);
}

/* ========== 渲染缓存（性能优化：避免每次防抖渲染全量重算） ========== */

// Mermaid SVG 缓存：key = 图表源码，value = 渲染出的 SVG 标记。
// SVG 内嵌主题色，主题切换时必须清空（见 setTheme）。
const mermaidSvgCache = new Map();
const MERMAID_CACHE_MAX = 50;

// highlight.js 结果缓存：key = 语言 + '' + 源码，value = 高亮后的 innerHTML。
// 高亮产物只含通用 class，主题配色由 CSS 类控制，故主题切换无需清空。
const hljsCache = new Map();
const HLJS_CACHE_MAX = 200;

/** 写入缓存并控制容量（Map 按插入序迭代，超出时淘汰最旧条目） */
function cacheSet(map, maxSize, key, value) {
    if (map.has(key)) map.delete(key);
    map.set(key, value);
    if (map.size > maxSize) {
        map.delete(map.keys().next().value);
    }
}

/* ========== 核心渲染函数 ========== */

/**
 * 渲染 Markdown 文本（由 Python 端调用）
 * @param {string} mdText - Markdown 原文
 */
async function renderMarkdown(mdText) {
    const content = document.getElementById('content');
    if (!mdText || mdText.trim() === '') {
        content.innerHTML = '<p class="placeholder-text">打开一个 Markdown 文件开始预览</p>';
        notifyRenderFinished();
        return;
    }

    // 记录渲染前的滚动比例，渲染完成后恢复（避免防抖重渲染时预览跳动）
    const prevScrollRange = document.documentElement.scrollHeight - window.innerHeight;
    const scrollRatio = prevScrollRange > 0 ? window.scrollY / prevScrollRange : 0;

    try {
        // 1. 保护块级公式 $$...$$（避免 marked 的 breaks 在公式内插入 <br>，
        //    切割文本节点导致 KaTeX 无法匹配 $$ 定界符）
        const mathGuard = protectBlockMath(mdText);

        // 2. marked.js 解析 Markdown → HTML
        let html = marked.parse(mathGuard.text);

        // 2.5 还原块级公式（HTML 转义后回填，保持 $$...$$ 位于单一文本节点）
        html = restoreBlockMath(html, mathGuard.store);

        // 3. 设置 HTML 内容
        content.innerHTML = html;

        // 3.5 预处理：保护 mermaid 代码块（直接基于 DOM 提取，避免依赖
        //     marked 序列化 HTML 的固定格式；同时避免被 KaTeX 误处理）
        const mermaidBlocks = [];
        content.querySelectorAll('pre code.language-mermaid').forEach(function (code) {
            const pre = code.parentElement;
            const holder = document.createComment(
                'MERMAID_PLACEHOLDER_' + mermaidBlocks.length
            );
            mermaidBlocks.push(code.textContent);
            pre.parentNode.replaceChild(holder, pre);
        });

        // 4. KaTeX 公式渲染
        renderMathInElement(content, {
            delimiters: [
                { left: '$$', right: '$$', display: true },
                { left: '$', right: '$', display: false },
                { left: '\\(', right: '\\)', display: false },
                { left: '\\[', right: '\\]', display: true },
            ],
            throwOnError: false,
            errorColor: '#cc0000',
        });

        // 5. 还原 Mermaid 占位符：单次 TreeWalker 收集全部注释占位符
        //    （原实现每个块都重新遍历整棵 DOM 树，图多时为 O(n²)）
        const placeholderNodes = {};
        const walker = document.createTreeWalker(content, NodeFilter.SHOW_COMMENT);
        let commentNode;
        while ((commentNode = walker.nextNode())) {
            const pm = commentNode.textContent.match(/^MERMAID_PLACEHOLDER_(\d+)$/);
            if (pm) placeholderNodes[parseInt(pm[1], 10)] = commentNode;
        }

        // 缓存命中的图直接回填缓存 SVG；未命中的收集起来交给 mermaid 渲染
        const pendingMermaid = []; // [{node, source}]
        for (let i = 0; i < mermaidBlocks.length; i++) {
            const holder = placeholderNodes[i];
            if (!holder) continue;
            const source = mermaidBlocks[i];
            const div = document.createElement('div');
            const cachedSvg = mermaidSvgCache.get(source);
            if (cachedSvg !== undefined) {
                div.className = 'mermaid';
                div.setAttribute('data-processed', 'true');
                div.innerHTML = cachedSvg;
            } else {
                div.className = 'mermaid';
                div.textContent = source;
                pendingMermaid.push({ node: div, source: source });
            }
            holder.parentNode.replaceChild(div, holder);
        }

        // 仅渲染未命中缓存的图表，成功后写入缓存（改一个字不再重画所有图）
        if (pendingMermaid.length > 0) {
            try {
                await mermaid.run({
                    nodes: pendingMermaid.map(function (p) { return p.node; }),
                });
                pendingMermaid.forEach(function (p) {
                    if (p.node.querySelector('svg')) {
                        cacheSet(mermaidSvgCache, MERMAID_CACHE_MAX, p.source, p.node.innerHTML);
                    }
                });
            } catch (e) {
                console.warn('[render.js] Mermaid render error:', e);
                pendingMermaid.forEach(function (p) {
                    if (!p.node.querySelector('svg')) {
                        p.node.innerHTML =
                            '<div class="mermaid-error">⚠ Mermaid 渲染失败: ' +
                            escapeHtml(e.message || String(e)) + '</div>';
                    }
                });
            }
        }

        // 6. highlight.js 代码高亮（跳过 mermaid；结果按 语言+源码 缓存，
        //    未变化的代码块直接回填缓存，避免每次渲染全文重算）
        content.querySelectorAll('pre code').forEach(function (block) {
            if (block.classList.contains('language-mermaid')) return;
            const langMatch = block.className.match(/language-([\w+-]+)/);
            const cacheKey = (langMatch ? langMatch[1] : '') + '' + block.textContent;
            const cachedHtml = hljsCache.get(cacheKey);
            if (cachedHtml !== undefined) {
                block.innerHTML = cachedHtml;
                block.classList.add('hljs');
                block.dataset.highlighted = 'true';
            } else {
                hljs.highlightElement(block);
                cacheSet(hljsCache, HLJS_CACHE_MAX, cacheKey, block.innerHTML);
            }
        });

        // 6.5 为代码块添加语言标签
        addCodeBlockHeaders(content);

        // 7. 为标题添加锚点 id（用于 TOC 跳转）
        addHeadingIds(content);

        // 8. 提取 TOC 并回传 Python
        extractAndSendTOC(content);

        // 8.5 恢复渲染前的滚动比例（innerHTML 重建 + mermaid 渲染后内容高度
        //     可能变化，按比例恢复保持阅读位置稳定，避免编辑时预览跳动）
        const newScrollRange = document.documentElement.scrollHeight - window.innerHeight;
        if (newScrollRange > 0 && scrollRatio > 0) {
            window.scrollTo(0, Math.round(newScrollRange * scrollRatio));
        }

        // 9. 通知渲染完成
        notifyRenderFinished();
        reportScrollMetrics();

    } catch (err) {
        console.error('[render.js] Render error:', err);
        content.innerHTML =
            '<div class="render-error">渲染出错: ' + escapeHtml(err.message) + '</div>';
        notifyRenderFinished();
        reportScrollMetrics();
    }
}

/* ========== 辅助函数 ========== */

/** 为代码块添加语言标签（右上角小标签） */
function addCodeBlockHeaders(container) {
    container.querySelectorAll('pre').forEach(function (pre) {
        const code = pre.querySelector('code');
        if (!code) return;
        const match = code.className.match(/language-([\w+-]+)/);
        const lang = match ? match[1] : '';
        if (lang === 'mermaid') return;
        if (lang) {
            pre.classList.add('has-lang');
            if (!pre.querySelector('.code-lang')) {
                const label = document.createElement('span');
                label.className = 'code-lang';
                label.textContent = lang;
                pre.appendChild(label);
            }
        }
    });
}

/** HTML 转义 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/** HTML 转义（字符串版，用于回填 HTML 字符串） */
function escapeHtmlString(s) {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * 保护块级公式 $$...$$：解析前替换为占位符，
 * 避免 marked 在公式内部插入 <br> 破坏 KaTeX 定界符。
 */
function protectBlockMath(mdText) {
    const store = [];
    const text = mdText.replace(/\$\$([\s\S]+?)\$\$/g, function (m) {
        store.push(m);
        return '@@BLOCKMATH' + (store.length - 1) + '@@';
    });
    return { text: text, store: store };
}

/** 还原块级公式占位符（HTML 转义，确保作为纯文本进入单一文本节点） */
function restoreBlockMath(html, store) {
    return html.replace(/@@BLOCKMATH(\d+)@@/g, function (m, idx) {
        return escapeHtmlString(store[parseInt(idx, 10)]);
    });
}

/** 为标题生成唯一 id */
function addHeadingIds(container) {
    const headings = container.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const usedIds = {};
    headings.forEach(function (h) {
        let id = h.textContent
            .toLowerCase()
            .replace(/[^\w\u4e00-\u9fff]+/g, '-')
            .replace(/^-+|-+$/g, '');
        if (!id) id = 'heading';
        if (usedIds[id]) {
            usedIds[id]++;
            id = id + '-' + usedIds[id];
        } else {
            usedIds[id] = 1;
        }
        h.id = id;
    });
}

/** 提取 TOC 结构并通过 bridge 发送给 Python */
function extractAndSendTOC(container) {
    const headings = container.querySelectorAll('h1, h2, h3, h4, h5, h6');
    const toc = [];
    headings.forEach(function (h) {
        toc.push({
            level: parseInt(h.tagName[1]),
            text: h.textContent,
            id: h.id,
        });
    });
    if (window.bridge) {
        window.bridge.onTocUpdate(JSON.stringify(toc));
    }
}

/** 通知 Python 渲染完成 */
function notifyRenderFinished() {
    if (window.bridge) {
        window.bridge.onRenderFinished();
    }
}

/* ========== 主题切换 ========== */

/**
 * 切换主题（由 Python 端调用）
 * @param {string} themeName - 'light' 或 'dark'
 */
function setTheme(themeName) {
    // Mermaid SVG 内嵌主题色，主题切换后缓存全部失效
    // （hljs 缓存产物只含通用 class，配色由 CSS 控制，无需清空）
    mermaidSvgCache.clear();

    const themeLink = document.getElementById('theme-stylesheet');
    const hljsLight = document.getElementById('hljs-light');
    const hljsDark = document.getElementById('hljs-dark');

    if (themeName === 'dark') {
        themeLink.href = '../css/theme-dark.css';
        hljsLight.disabled = true;
        hljsDark.disabled = false;
        document.body.classList.add('dark-theme');
        // 更新 mermaid 主题
        mermaid.initialize({ startOnLoad: false, theme: 'dark' });
    } else {
        themeLink.href = '../css/theme-light.css';
        hljsLight.disabled = false;
        hljsDark.disabled = true;
        document.body.classList.remove('dark-theme');
        mermaid.initialize({ startOnLoad: false, theme: 'default' });
    }
}

/* ========== 滚动同步 ========== */

window.nativeScrollProxyEnabled = false;

/** 设置预览区滚动比例（由 Python 端调用） */
function setScrollPercent(percent) {
    const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (scrollHeight > 0) {
        window.scrollTo(0, scrollHeight * percent);
    }
}

/** 滚动到指定标题 id */
function scrollToHeading(headingId) {
    const el = document.getElementById(headingId);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/** 设置文档滚动位置（原生 Qt 滚动条代理使用） */
function setScrollTop(top) {
    window.scrollTo(0, top);
}

/** 读取文档滚动尺寸 */
function getScrollMetrics() {
    return {
        top: window.scrollY,
        height: document.documentElement.scrollHeight,
        client: window.innerHeight,
    };
}

/** 启用/关闭原生滚动条代理：隐藏网页滚动条，由 Qt 滚动条驱动 */
function setNativeScrollProxy(enabled) {
    window.nativeScrollProxyEnabled = !!enabled;
    document.documentElement.classList.toggle('native-scroll-proxy', !!enabled);
    document.body.classList.toggle('native-scroll-proxy', !!enabled);
    reportScrollMetrics();
}

/** 把滚动尺寸回传给 Python，用于更新原生滚动条 range/value */
function reportScrollMetrics() {
    if (!window.nativeScrollProxyEnabled || !window.bridge) return;
    const metrics = getScrollMetrics();
    window.bridge.onScrollMetrics(metrics.top, metrics.height, metrics.client);
}

// 监听预览区滚动：原生代理开启时只回报量程；编辑双栏时回报比例用于反向同步
let scrollTimer = null;
window.addEventListener('scroll', function () {
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
        if (window.nativeScrollProxyEnabled) {
            reportScrollMetrics();
            return;
        }
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollHeight > 0 && window.bridge) {
            const percent = window.scrollY / scrollHeight;
            window.bridge.onScroll(percent);
        }
    }, 50);
});

window.addEventListener('resize', function () {
    if (window.nativeScrollProxyEnabled) reportScrollMetrics();
});

/* ========== 获取渲染后的 HTML（用于导出） ========== */

function getRenderedHtml() {
    return document.getElementById('content').innerHTML;
}
