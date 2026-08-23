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

// mermaid 基础配置（延迟渲染，由我们手动触发）
// htmlLabels 关闭 + sequence 使用 SVG 文本：可被 QtSvg 等矢量渲染器识别，
// 也便于无 Chrome 时用 PyQt5 生成 PDF。
// 注意：mermaid.initialize 会把未传递的字段重置回默认值，主题切换时
// 必须整体重传本配置，否则 htmlLabels / fontFamily 会悄悄丢失，
// 导致暗色主题下流程图退化为 foreignObject 标签、Qt 矢量导出丢文字
const MERMAID_BASE_CONFIG = {
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
    flowchart: {
        htmlLabels: false,
        useMaxWidth: true,
    },
    sequence: {
        textPlacement: 'old',
        useMaxWidth: true,
    },
};

mermaid.initialize(MERMAID_BASE_CONFIG);

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

// KaTeX 结果缓存：key = 公式所在文本节点的原文，value = 渲染后片段。
// marked 重新生成的未变化区域文本内容不变，命中后无需再跑 KaTeX
// （KaTeX 曾占全文渲染耗时的一半以上）；产物只含通用结构，
// 配色由 CSS 控制，主题切换无需清空。
const katexNodeCache = new Map();
const KATEX_CACHE_MAX = 2000;

const KATEX_OPTIONS = {
    delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
        { left: '\\(', right: '\\)', display: false },
        { left: '\\[', right: '\\]', display: true },
    ],
    throwOnError: false,
    errorColor: '#cc0000',
};

// 与 auto-render 默认 ignoredTags 保持一致（这些子树不处理公式）
const KATEX_IGNORED_TAGS = {
    NOSCRIPT: 1, NOSTYLE: 1, STYLE: 1, TEXTAREA: 1, PRE: 1, CODE: 1, OPTION: 1,
};

/** 文本节点是否位于忽略标签（pre/code 等）内 */
function mathInIgnoredTag(node, container) {
    let el = node.parentElement;
    while (el && el !== container) {
        if (KATEX_IGNORED_TAGS[el.tagName]) return true;
        el = el.parentElement;
    }
    return false;
}

/**
 * KaTeX 渲染（文本节点级缓存）：
 * 只处理含定界符的文本节点，未变化的节点直接回填缓存片段。
 * 命中路径只做 Map 查找 + innerHTML 构造，完全跳过 KaTeX 解析。
 */
function renderMathCached(container) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const targets = [];
    let node;
    while ((node = walker.nextNode())) {
        const t = node.nodeValue;
        if (
            (t.indexOf('$') >= 0 || t.indexOf('\\(') >= 0 || t.indexOf('\\[') >= 0)
            && !mathInIgnoredTag(node, container)
        ) {
            targets.push(node);
        }
    }
    targets.forEach(function (textNode) {
        const src = textNode.nodeValue;
        const span = document.createElement('span');
        let html = katexNodeCache.get(src);
        if (html === undefined) {
            textNode.parentNode.replaceChild(span, textNode);
            span.appendChild(textNode);
            renderMathInElement(span, KATEX_OPTIONS);
            html = span.innerHTML;
            cacheSet(katexNodeCache, KATEX_CACHE_MAX, src, html);
        } else {
            span.innerHTML = html;
            textNode.parentNode.replaceChild(span, textNode);
        }
    });
}

/* ========== 分块增量渲染 ========== */

// 块映射状态：entries[i] = { h: 源码 hash, n: 对应 #content 顶层子节点数 }
// 首次渲染 / 强制重建时建立；重渲染时按 hash 对比，只重新解析并替换
// 变化的块，未变化块的 DOM 原样保留（跳过解析、KaTeX、hljs 与布局）。
const blockState = { entries: [], ready: false };
let forceFullRender = true; // 主题切换等全局状态变化后置位，下次全量重建

// 重同步搜索窗口：diff 区域向前最多找这么多个块的对齐点，
// 超出则视为全文重写（退化为一次全量替换）
const _RESYNC_LIMIT = 200;

const _LIST_RE = /^(?: {0,3})(?:[-*+]|\d{1,9}[.)])(?: |$)/;
const _LINK_DEF_RE = /^ {0,3}\[[^\]]*\]: *\S+ *$/;

/**
 * 把 Markdown 源码拆成顶层块。
 * 只在空行处分割（围栏代码 / 块级公式内的空行不算），
 * 列表与引用跨空行延续时并入同一块。拆分只影响增量粒度：
 * 合并相邻构造与整篇解析结果一致（marked 对同一文本的输出不变），
 * 只有错误地"拆开"本应一体的块才会改变渲染，故偏向保守合并。
 */
function splitBlocks(mdText) {
    const lines = mdText.split('\n');
    const blocks = [];
    let cur = null;
    let mode = null; // null | 'quote' | 'list'：空行后的延续判断
    let fence = null; // '`' | '~'：围栏代码内
    let inMath = false; // 多行 $$...$$ 内
    let blanks = 0;

    function flush() {
        if (cur !== null) {
            while (cur.length && cur[cur.length - 1].trim() === '') cur.pop();
            if (cur.length) blocks.push(cur.join('\n'));
        }
        cur = null;
        mode = null;
    }

    for (const line of lines) {
        const stripped = line.trim();

        if (fence) {
            if (cur === null) cur = [];
            cur.push(line);
            if ((fence === '`' && /^`{3,}\s*$/.test(stripped))
                || (fence === '~' && /^~{3,}\s*$/.test(stripped))) {
                fence = null;
            }
            continue;
        }
        if (inMath) {
            if (cur === null) cur = [];
            cur.push(line);
            if (stripped.slice(-2) === '$$') inMath = false;
            continue;
        }

        if (stripped === '') { blanks++; continue; }

        const fenceMatch = stripped.match(/^(`{3,}|~{3,})/);
        if (fenceMatch) {
            // 空行后的顶层围栏开新块；无空行时并入当前块（解析结果一致）
            if (cur !== null && blanks > 0) flush();
            if (cur === null) cur = [];
            cur.push(line);
            blanks = 0;
            fence = fenceMatch[1].charAt(0);
            continue;
        }

        if (stripped.charAt(0) === '$' && stripped.slice(0, 2) === '$$') {
            if (cur !== null && blanks > 0) flush();
            if (cur === null) cur = [];
            cur.push(line);
            blanks = 0;
            // 单行完整的 $$...$$ 不进入多行状态
            if (!(stripped.length >= 4 && stripped.indexOf('$$', 2) >= 0)) {
                inMath = true;
            }
            continue;
        }

        if (cur !== null && blanks > 0) {
            const isQuote = stripped.charAt(0) === '>';
            const isList = _LIST_RE.test(line);
            const isIndented = line.charAt(0) === ' ' || line.charAt(0) === '\t';
            const continues = (isQuote && mode === 'quote')
                || ((isList || isIndented) && mode === 'list');
            if (!continues) flush();
        }
        blanks = 0;
        if (cur === null) cur = [];
        cur.push(line);
        if (stripped.charAt(0) === '>') mode = 'quote';
        else if (_LIST_RE.test(line)) mode = 'list';
        else if (mode !== 'list') mode = null;
        // 列表内的缩进延续行保持 list 模式
    }
    flush();
    return blocks;
}

/** 块源码 hash（双 32 位 FNV 风格组合，避免长期持有全部原文） */
function blockHash(text) {
    let h1 = 0xdeadbeef ^ text.length;
    let h2 = 0x41c6ce57 ^ text.length;
    for (let i = 0; i < text.length; i++) {
        const c = text.charCodeAt(i);
        h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0;
        h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0;
    }
    return h1.toString(36) + '-' + h2.toString(36);
}

/**
 * 收集纯链接定义块（[ref]: url）。
 * 分块解析时变化的块拿不到别处定义的引用，统一前置这些定义
 * （marked 对链接定义不产生任何输出，前置不影响渲染结果）。
 */
function collectLinkDefs(blocks) {
    const defs = [];
    for (const b of blocks) {
        const linesArr = b.split('\n');
        let allDef = true;
        for (const l of linesArr) {
            if (l.trim() === '') continue;
            if (!_LINK_DEF_RE.test(l)) { allDef = false; break; }
        }
        if (allDef) defs.push(b);
    }
    return defs.join('\n\n');
}

/* ── 单块渲染管线（与旧全量管线相同步骤，作用域限定在块内） ── */

function wrapTablesIn(root) {
    root.querySelectorAll('table').forEach(function (table) {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-wrap';
        table.parentNode.insertBefore(wrapper, table);
        wrapper.appendChild(table);
    });
}

/**
 * mermaid 处理分两阶段（见 renderBlockFragment / renderPendingMermaid）：
 * 1) 构建片段时：pre 替换为注释占位（防止 KaTeX 误处理源码里的 $），
 *    KaTeX 完成后还原为 div（缓存命中直接回填 SVG）
 * 2) 片段插入文档后：才调用 mermaid.run 渲染未命中的图——
 *    mermaid 的 d3 布局依赖真实排版（getBBox），
 *    在 detached 容器里渲染会得到零尺寸/布局损坏的 SVG
 */
function protectMermaidIn(root) {
    const sources = [];
    root.querySelectorAll('pre code.language-mermaid').forEach(function (code) {
        const pre = code.parentElement;
        const holder = document.createComment(
            'MERMAID_PLACEHOLDER_' + sources.length
        );
        sources.push(code.textContent);
        pre.parentNode.replaceChild(holder, pre);
    });
    return sources;
}

function restoreMermaidIn(root, sources) {
    const pending = [];
    if (sources.length === 0) return pending;

    const placeholderNodes = {};
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT);
    let commentNode;
    while ((commentNode = walker.nextNode())) {
        const pm = commentNode.textContent.match(/^MERMAID_PLACEHOLDER_(\d+)$/);
        if (pm) placeholderNodes[parseInt(pm[1], 10)] = commentNode;
    }

    for (let i = 0; i < sources.length; i++) {
        const holder = placeholderNodes[i];
        if (!holder) continue;
        const source = sources[i];
        const div = document.createElement('div');
        const cachedSvg = mermaidSvgCache.get(source);
        if (cachedSvg !== undefined) {
            div.className = 'mermaid';
            div.setAttribute('data-processed', 'true');
            div.innerHTML = cachedSvg;
        } else {
            div.className = 'mermaid';
            div.textContent = source;
            pending.push({ node: div, source: source });
        }
        holder.parentNode.replaceChild(div, holder);
    }
    return pending;
}

async function renderPendingMermaid(pending) {
    if (!pending || pending.length === 0) return;
    try {
        await mermaid.run({
            nodes: pending.map(function (p) { return p.node; }),
        });
        pending.forEach(function (p) {
            if (p.node.querySelector('svg')) {
                cacheSet(mermaidSvgCache, MERMAID_CACHE_MAX, p.source, p.node.innerHTML);
            }
        });
    } catch (e) {
        console.warn('[render.js] Mermaid render error:', e);
        pending.forEach(function (p) {
            if (!p.node.querySelector('svg')) {
                p.node.innerHTML =
                    '<div class="mermaid-error">⚠ Mermaid 渲染失败: ' +
                    escapeHtml(e.message || String(e)) + '</div>';
            }
        });
    }
}

function highlightCodeIn(root) {
    root.querySelectorAll('pre code').forEach(function (block) {
        if (block.classList.contains('language-mermaid')) return;
        const langMatch = block.className.match(/language-([\w+-]+)/);
        const cacheKey = (langMatch ? langMatch[1] : '') + '\u0001' + block.textContent;
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
}

/**
 * 渲染单个块为 DocumentFragment（不插入文档）。
 * defsPrefix 为全部链接定义块的拼接文本，保证引用式链接可用。
 * 返回 { frag, pendingMermaid }：未命中缓存的 mermaid 图必须等
 * frag 插入文档后再交给 renderPendingMermaid 渲染（d3 需要真实布局）。
 */
async function renderBlockFragment(blockText, defsPrefix) {
    const holder = document.createElement('div');
    // 链接定义与正文之间必须有空行，否则定义的 URL 会吞掉正文首行
    //（如 [ref]: url## 标题 会被整体解析为一条链接定义）
    const source = defsPrefix ? defsPrefix + '\n\n' + blockText : blockText;
    const mathGuard = protectBlockMath(source);
    let html = marked.parse(mathGuard.text);
    html = restoreBlockMath(html, mathGuard.store);
    holder.innerHTML = html;

    wrapTablesIn(holder);
    const mermaidSources = protectMermaidIn(holder);
    renderMathCached(holder);
    const pendingMermaid = restoreMermaidIn(holder, mermaidSources);
    highlightCodeIn(holder);
    addCodeBlockHeaders(holder);

    const frag = document.createDocumentFragment();
    while (holder.firstChild) frag.appendChild(holder.firstChild);
    return { frag: frag, pendingMermaid: pendingMermaid };
}

/* ── 全量重建（首次渲染 / 增量失败回退 / 全局状态变化） ── */

async function renderAllBlocks(mdText, content) {
    const prevRange = document.documentElement.scrollHeight - window.innerHeight;
    const scrollRatio = prevRange > 0 ? window.scrollY / prevRange : 0;

    const blocks = splitBlocks(mdText);
    const defs = collectLinkDefs(blocks);
    content.innerHTML = '';
    const entries = [];
    const allPending = [];
    for (let k = 0; k < blocks.length; k++) {
        const r = await renderBlockFragment(blocks[k], defs);
        entries.push({ h: blockHash(blocks[k]), n: r.frag.childNodes.length });
        content.appendChild(r.frag);
        allPending.push.apply(allPending, r.pendingMermaid);
    }
    // 全部片段已插入文档，统一渲染未命中的 mermaid（批次越大越省）
    await renderPendingMermaid(allPending);
    blockState.entries = entries;
    blockState.ready = true;
    forceFullRender = false;

    // 全量重建可能大幅改变内容高度，按比例恢复阅读位置
    const newRange = document.documentElement.scrollHeight - window.innerHeight;
    if (newRange > 0 && scrollRatio > 0) {
        window.scrollTo(0, Math.round(newRange * scrollRatio));
    }
}

/* ── 增量渲染：hash 对比，只替换变化的块 ── */

/**
 * 在旧侧 oldStart / 新侧 newStart 之后寻找最近的 hash 对齐点，
 * 返回 [旧侧位置, 新侧位置]；找不到返回各自末尾。
 */
function findResync(old, newHashes, i, j) {
    for (let span = 1; span <= _RESYNC_LIMIT; span++) {
        const aHi = Math.min(old.length, i + span);
        const bHi = Math.min(newHashes.length, j + span);
        for (let x = i; x <= aHi; x++) {
            for (let y = j; y <= bHi; y++) {
                if (x === i && y === j) continue;
                if (x < old.length && y < newHashes.length && old[x].h === newHashes[y]) {
                    return [x, y];
                }
            }
        }
        if (aHi >= old.length && bHi >= newHashes.length) break;
    }
    return [old.length, newHashes.length];
}

async function renderIncremental(mdText, content) {
    const blocks = splitBlocks(mdText);
    const defs = collectLinkDefs(blocks);
    const newHashes = blocks.map(blockHash);
    const old = blockState.entries;

    let i = 0, j = 0, domPos = 0;
    const result = [];
    while (i < old.length || j < blocks.length) {
        if (i < old.length && j < blocks.length && old[i].h === newHashes[j]) {
            result.push(old[i]);
            domPos += old[i].n;
            i++; j++;
            continue;
        }

        const synced = findResync(old, newHashes, i, j);
        const a = synced[0], b = synced[1];

        let oldCount = 0;
        for (let k = i; k < a; k++) oldCount += old[k].n;
        if (domPos + oldCount > content.childNodes.length) {
            // 块映射与 DOM 脱同步（外部改动等），交给上层回退全量
            throw new Error('block mapping out of sync');
        }

        const children = content.childNodes;
        const oldNodes = [];
        for (let k = domPos; k < domPos + oldCount; k++) oldNodes.push(children[k]);

        const frag = document.createDocumentFragment();
        const runPending = [];
        let newCount = 0;
        for (let k = j; k < b; k++) {
            const r = await renderBlockFragment(blocks[k], defs);
            result.push({ h: newHashes[k], n: r.frag.childNodes.length });
            newCount += r.frag.childNodes.length;
            runPending.push.apply(runPending, r.pendingMermaid);
            frag.appendChild(r.frag);
        }
        const anchor = content.childNodes[domPos] || null;
        content.insertBefore(frag, anchor);
        for (const node of oldNodes) content.removeChild(node);
        // 片段已在文档内，渲染未命中的 mermaid
        await renderPendingMermaid(runPending);

        domPos += newCount;
        i = a; j = b;
    }
    blockState.entries = result;
}

/* ========== 核心渲染函数 ========== */

/**
 * 渲染 Markdown 文本（由 Python 端调用）。
 * 首次全量建立块映射；此后增量渲染只替换变化的块，
 * 未变化块的 DOM/布局完全不动（滚动位置天然保持）。
 * @param {string} mdText - Markdown 原文
 */
async function renderMarkdown(mdText) {
    const content = document.getElementById('content');
    if (!mdText || mdText.trim() === '') {
        content.innerHTML = '<p class="placeholder-text">打开一个 Markdown 文件开始预览</p>';
        blockState.ready = false;
        notifyRenderFinished();
        return;
    }

    try {
        if (forceFullRender || !blockState.ready) {
            await renderAllBlocks(mdText, content);
        } else {
            try {
                await renderIncremental(mdText, content);
            } catch (e) {
                console.warn('[render.js] Incremental render failed, fallback:', e);
                await renderAllBlocks(mdText, content);
            }
        }
    } catch (err) {
        console.error('[render.js] Render error:', err);
        blockState.ready = false;
        content.innerHTML =
            '<div class="render-error">渲染出错: ' + escapeHtml(err.message || String(err)) + '</div>';
        notifyRenderFinished();
        reportScrollMetrics();
        return;
    }

    // 标题 id / TOC 全量重算（遍历很便宜，且保证与全量渲染一致的去重序）
    addHeadingIds(content);
    extractAndSendTOC(content);
    notifyRenderFinished();
    reportScrollMetrics();
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

/* ========== 字体设置 ========== */

/**
 * 应用字体设置（由 Python 端调用）。
 * 通过注入持久 <style> 覆盖主题的 CSS 变量与正文字号；
 * bodyStack / headingStack / monoStack 为完整的字体栈字符串（含引号与
 * 回退），传空字符串表示该项跟随主题默认。style 元素晚于所有 <link>
 * 加载，同特异性下级联胜出。
 */
function applyFontSettings(bodyStack, headingStack, monoStack, sizePx) {
    var el = document.getElementById('font-override');
    if (!el) {
        el = document.createElement('style');
        el.id = 'font-override';
        document.head.appendChild(el);
    }
    var css = '';
    if (bodyStack) css += ':root{--font-body:' + bodyStack + ';}';
    if (headingStack) css += ':root{--font-display:' + headingStack + ';}';
    if (monoStack) css += ':root{--font-mono:' + monoStack + ';}';
    if (sizePx > 0) css += 'body{font-size:' + sizePx + 'px;}';
    el.textContent = css;
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
    // 未变化块的 DOM 里还是旧主题的 SVG/高亮，必须整体重建
    forceFullRender = true;

    const themeLink = document.getElementById('theme-stylesheet');
    const hljsLight = document.getElementById('hljs-light');
    const hljsDark = document.getElementById('hljs-dark');

    if (themeName === 'dark') {
        themeLink.href = '../css/theme-dark.css';
        hljsLight.disabled = true;
        hljsDark.disabled = false;
        document.body.classList.add('dark-theme');
        // 更新 mermaid 主题（须整体重传基础配置，见 MERMAID_BASE_CONFIG 注释）
        mermaid.initialize(
            Object.assign({}, MERMAID_BASE_CONFIG, { theme: 'dark' }));
    } else {
        themeLink.href = '../css/theme-light.css';
        hljsLight.disabled = false;
        hljsDark.disabled = true;
        document.body.classList.remove('dark-theme');
        mermaid.initialize(
            Object.assign({}, MERMAID_BASE_CONFIG, { theme: 'default' }));
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

/* ========== 搜索计数（供 Python 端 findText 配套使用） ========== */

/**
 * 统计正文中关键词出现次数（只读扫描文本节点，不修改 DOM）。
 * Python 侧 QWebEnginePage.findText 的回调只回传 bool，
 * 匹配总数由此函数提供。
 */
function countSearchMatches(term, caseSensitive) {
    if (!term) return 0;
    var root = document.getElementById('content') || document.body;
    var needle = caseSensitive ? term : term.toLowerCase();
    var count = 0;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var node;
    while ((node = walker.nextNode())) {
        var text = caseSensitive ? node.textContent : node.textContent.toLowerCase();
        var idx = 0;
        while ((idx = text.indexOf(needle, idx)) >= 0) {
            count++;
            idx += needle.length;
        }
    }
    return count;
}
