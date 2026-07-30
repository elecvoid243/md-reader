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

// 初始化 QWebChannel
if (typeof QWebChannel !== 'undefined') {
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

    try {
        // 1. 保护块级公式 $$...$$（避免 marked 的 breaks 在公式内插入 <br>，
        //    切割文本节点导致 KaTeX 无法匹配 $$ 定界符）
        const mathGuard = protectBlockMath(mdText);

        // 2. marked.js 解析 Markdown → HTML
        let html = marked.parse(mathGuard.text);

        // 2.5 还原块级公式（HTML 转义后回填，保持 $$...$$ 位于单一文本节点）
        html = restoreBlockMath(html, mathGuard.store);

        // 3. 预处理：保护 mermaid 代码块（避免被 KaTeX 误处理）
        const mermaidBlocks = [];
        html = html.replace(
            /<pre><code class="language-mermaid">([\s\S]*?)<\/code><\/pre>/gi,
            function (match, code) {
                const idx = mermaidBlocks.length;
                mermaidBlocks.push(decodeHtml(code));
                return `<!--MERMAID_PLACEHOLDER_${idx}-->`;
            }
        );

        // 3. 设置 HTML 内容
        content.innerHTML = html;

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

        // 5. 还原并渲染 Mermaid 图表
        for (let i = 0; i < mermaidBlocks.length; i++) {
            const placeholder = content.querySelector(`#MERMAID_PLACEHOLDER_${i}`);
            // 占位符是注释节点，需要遍历查找
            const walker = document.createTreeWalker(content, NodeFilter.SHOW_COMMENT);
            let commentNode;
            while ((commentNode = walker.nextNode())) {
                if (commentNode.textContent === `MERMAID_PLACEHOLDER_${i}`) {
                    const div = document.createElement('div');
                    div.className = 'mermaid';
                    div.textContent = mermaidBlocks[i];
                    commentNode.parentNode.replaceChild(div, commentNode);
                    break;
                }
            }
        }

        // 渲染所有 mermaid 图表
        const mermaidDivs = content.querySelectorAll('.mermaid:not([data-processed])');
        if (mermaidDivs.length > 0) {
            try {
                await mermaid.run({ nodes: mermaidDivs });
            } catch (e) {
                console.warn('[render.js] Mermaid render error:', e);
                mermaidDivs.forEach(function (div) {
                    if (!div.querySelector('svg')) {
                        div.innerHTML =
                            '<div class="mermaid-error">⚠ Mermaid 渲染失败: ' +
                            escapeHtml(e.message || String(e)) + '</div>';
                    }
                });
            }
        }

        // 6. highlight.js 代码高亮（跳过 mermaid）
        content.querySelectorAll('pre code').forEach(function (block) {
            if (!block.classList.contains('language-mermaid')) {
                hljs.highlightElement(block);
            }
        });

        // 6.5 为代码块添加语言标签
        addCodeBlockHeaders(content);

        // 7. 为标题添加锚点 id（用于 TOC 跳转）
        addHeadingIds(content);

        // 8. 提取 TOC 并回传 Python
        extractAndSendTOC(content);

        // 9. 通知渲染完成
        notifyRenderFinished();

    } catch (err) {
        console.error('[render.js] Render error:', err);
        content.innerHTML =
            '<div class="render-error">渲染出错: ' + escapeHtml(err.message) + '</div>';
        notifyRenderFinished();
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

/** HTML 实体解码 */
function decodeHtml(text) {
    const el = document.createElement('textarea');
    el.innerHTML = text;
    return el.value;
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

// 监听预览区滚动，回传比例给 Python（用于反向同步）
let scrollTimer = null;
window.addEventListener('scroll', function () {
    if (scrollTimer) clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () {
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (scrollHeight > 0 && window.bridge) {
            const percent = window.scrollY / scrollHeight;
            window.bridge.onScroll(percent);
        }
    }, 50);
});

/* ========== 获取渲染后的 HTML（用于导出） ========== */

function getRenderedHtml() {
    return document.getElementById('content').innerHTML;
}
