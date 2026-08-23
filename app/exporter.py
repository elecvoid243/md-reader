"""
exporter.py — 导出功能

支持将当前预览内容导出为：
- 独立 HTML 文件（内联 CSS，可离线打开）
- PDF 文件

PDF 导出顺序：
1. 本机 Chrome / Edge 无头打印（矢量文字，质量最好）
2. PyQt5 QTextDocument + QPdfWriter + QtSvg（无第三方依赖，正文矢量，
   Mermaid 以高分辨率图片嵌入）
3. QWebEngineView.printToPdf（最后回退）
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Match, Optional, Tuple

from PyQt5.QtCore import QByteArray, QMarginsF, QRectF, QSize, Qt, QUrl
from PyQt5.QtGui import (
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPdfWriter,
    QTextDocument,
)
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QFileDialog, QWidget

from .preview import PreviewPane

_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
)
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# A4 内容宽度（左右各 15mm 边距），单位 px（96dpi）
_PRINT_CONTENT_WIDTH_PX = int(180 / 25.4 * 96)
# Mermaid 等 SVG 转图片时的采样倍数
_SVG_RENDER_SCALE = 3

_PRINT_STYLESHEET = """
body {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
}
h1, h2, h3, h4, h5, h6 { color: #111; line-height: 1.25; }
h1 { font-size: 24pt; border-bottom: 1px solid #bbb; margin: 14pt 0 10pt; }
h2 { font-size: 18pt; border-bottom: 1px solid #ddd; margin: 12pt 0 8pt; }
h3 { font-size: 14pt; margin: 10pt 0 6pt; }
h4 { font-size: 12pt; margin: 8pt 0 5pt; }
p { margin: 6pt 0; }
ul, ol { margin: 6pt 0 6pt 20pt; }
li { margin: 2pt 0; }
pre {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9pt;
    line-height: 1.4;
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4pt;
    padding: 8pt;
    margin: 8pt 0;
    white-space: pre-wrap;
}
code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9.5pt;
    background-color: #f2f2f2;
    border-radius: 2pt;
    padding: 0 2pt;
}
pre code { background-color: transparent; padding: 0; }
blockquote {
    margin: 8pt 0;
    padding: 4pt 10pt;
    border-left: 3pt solid #0e6b5a;
    color: #555;
    background-color: #f7f7f7;
}
table { border-collapse: collapse; margin: 0; width: 100%; }
/* 表格的边距在网页端由 .table-wrap 承担（markdown.css），
   QTextDocument 不执行该样式，这里补齐 */
.table-wrap { margin: 8pt 0; }
th, td { border: 1px solid #bbb; padding: 4pt 6pt; }
th { background-color: #efefef; }
hr { border: none; border-top: 1px solid #bbb; margin: 12pt 0; }
.mermaid, .vditor-mermaid-preview { margin: 10pt 0; text-align: center; }
img { max-width: 100%; }
"""

# 常见无头浏览器路径（Chrome 109 及更早版本仍支持 Win7 32 位）
_BROWSER_PATHS = (
    os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        "Google", "Chrome", "Application", "chrome.exe",
    ),
    os.path.join(
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        "Google", "Chrome", "Application", "chrome.exe",
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "Application", "chrome.exe",
    ),
    os.path.join(
        os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        "Microsoft", "Edge", "Application", "msedge.exe",
    ),
    os.path.join(
        os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
        "Microsoft", "Edge", "Application", "msedge.exe",
    ),
)


def _read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _build_standalone_html(rendered_html: str) -> str:
    """把已渲染 HTML 和本地 CSS 打包成完全离线的单文件 HTML"""
    markdown_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "markdown.css"))
    theme_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "theme-light.css"))
    katex_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "katex.min.css"))
    hljs_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "github.min.css"))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
@page {{
    size: A4;
    margin: 15mm;
}}
{theme_css}
{markdown_css}
{katex_css}
{hljs_css}
</style>
</head>
<body>
<div id="content" class="markdown-body">
{rendered_html}
</div>
</body>
</html>"""


_PDF_PRINT_OVERRIDES = """
/* 打印导出：去除应用主题的桌面背景、纸面边框、阴影等装饰，
   只保留正文、代码、表格等必要排版 */
html, body {
    background: #ffffff !important;
    background-image: none !important;
    margin: 0 !important;
    padding: 0 !important;
}
#content {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    padding: 0 !important;
    min-height: 0 !important;
    background: #ffffff !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}
.markdown-body .mermaid {
    margin: 1.4em 0 !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}
.markdown-body .katex-display {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
.markdown-body blockquote {
    background: transparent !important;
    box-shadow: none !important;
}
.markdown-body pre {
    background: #f7f7f7 !important;
    border: 1px solid #dddddd !important;
    box-shadow: none !important;
}
.markdown-body table {
    background: #ffffff !important;
    box-shadow: none !important;
}
.markdown-body table tbody tr:nth-child(2n) {
    background: transparent !important;
}
"""


def _build_print_html(rendered_html: str) -> str:
    """构建用于 PDF 打印的干净 HTML：保留内容排版，去掉主题装饰"""
    markdown_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "markdown.css"))
    theme_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "theme-light.css"))
    katex_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "katex.min.css"))
    hljs_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "github.min.css"))

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
@page {{
    size: A4;
    margin: 15mm;
}}
{theme_css}
{markdown_css}
{katex_css}
{hljs_css}
{_PDF_PRINT_OVERRIDES}
</style>
</head>
<body>
<div id="content" class="markdown-body">
{rendered_html}
</div>
</body>
</html>"""


def _find_headless_browser() -> Optional[str]:
    """查找可用的 Chromium 内核无头浏览器"""
    candidates = []
    for browser_path in _BROWSER_PATHS:
        if browser_path and os.path.isfile(browser_path):
            candidates.append(browser_path)
    for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
        found = shutil.which(name)
        if found and os.path.isfile(found):
            candidates.append(found)

    for browser_path in candidates:
        if os.path.isfile(browser_path):
            return browser_path
    return None


def _export_pdf_via_headless_browser(html: str, pdf_path: str) -> bool:
    """用 Chrome / Edge 无头模式生成高质量 PDF"""
    browser_path = _find_headless_browser()
    if not browser_path:
        return False

    temp_dir = tempfile.mkdtemp(prefix="md-reader-pdf-")
    try:
        html_path = os.path.join(temp_dir, "export.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        profile_dir = os.path.join(temp_dir, "profile")
        os.makedirs(profile_dir, exist_ok=True)

        command = [
            browser_path,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--no-first-run",
            "--disable-extensions",
            "--allow-file-access-from-files",
            "--user-data-dir=" + profile_dir,
            "--print-to-pdf=" + pdf_path,
            Path(html_path).as_uri(),
        ]
        try:
            result = subprocess.run(
                command,
                timeout=120,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False

        if result.returncode != 0 or not os.path.isfile(pdf_path):
            return False
        return os.path.getsize(pdf_path) > 0
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _svg_to_qimage(svg_text: str) -> Tuple[Optional[QImage], QSize]:
    """用 QtSvg 把纯 SVG 文本渲染为高分辨率 QImage"""
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        return None, QSize()
    size = renderer.defaultSize()
    if size.isEmpty() or size.width() < 1 or size.height() < 1:
        return None, QSize()

    # 限制最大像素，避免异常大的 SVG 占用过多内存
    scale = min(
        float(_SVG_RENDER_SCALE),
        4000.0 / max(size.width(), size.height()),
    )
    width = max(1, int(size.width() * scale))
    height = max(1, int(size.height() * scale))

    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    renderer.render(painter, QRectF(0, 0, width, height))
    painter.end()
    return image, size


def _export_pdf_with_qtdocument(rendered_html: str, pdf_path: str) -> bool:
    """
    无 Chrome 时的 Python/Qt PDF 导出。

    正文使用 QTextDocument 输出矢量文字；Mermaid 等内联 SVG 先由 QtSvg
    渲染为高分辨率图片，再作为 QTextDocument 资源嵌入。
    """
    try:
        document = QTextDocument()
        document.setDefaultStyleSheet(_PRINT_STYLESHEET)

        # 语言标签在打印排版中没有意义，先移除
        prepared_html = re.sub(
            r'<span class="code-lang">.*?</span>',
            "",
            rendered_html,
            flags=re.DOTALL,
        )

        svg_pattern = re.compile(r"<svg\b.*?</svg>", re.DOTALL)
        counter = [0]

        def _replace_svg(match: Match[str]) -> str:
            image, size = _svg_to_qimage(match.group(0))
            if image is None:
                return '<p style="color:#a33">图表渲染失败</p>'
            name = "mermaid-%d" % counter[0]
            counter[0] += 1
            document.addResource(
                QTextDocument.ImageResource,
                QUrl("img://" + name),
                image,
            )
            width = min(size.width(), _PRINT_CONTENT_WIDTH_PX)
            return '<img src="img://%s" width="%d">' % (name, int(width))

        prepared_html = svg_pattern.sub(_replace_svg, prepared_html)
        document.setHtml(prepared_html)

        writer = QPdfWriter(pdf_path)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setPageMargins(
            QMarginsF(15, 15, 15, 15), QPageLayout.Millimeter
        )
        writer.setResolution(300)
        document.print_(writer)

        return os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0
    except Exception:
        return False


def export_html(preview: PreviewPane, parent: QWidget | None = None) -> bool:
    """
    导出为独立 HTML 文件

    将渲染后的 HTML 与必要的 CSS 内联打包，生成可离线打开的单文件。
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出 HTML", "", "HTML 文件 (*.html);;所有文件 (*)"
    )
    if not path:
        return False

    def _do_export(rendered_html: str) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(_build_standalone_html(rendered_html))
        except OSError:
            pass

    preview.get_rendered_html(_do_export)
    return True


def export_pdf(preview: PreviewPane, parent: QWidget | None = None) -> bool:
    """
    导出为 PDF 文件

    优先使用本机 Chrome / Edge 无头模式；不可用时回退到
    QWebEngineView.printToPdf。
    """
    path, _ = QFileDialog.getSaveFileName(
        parent, "导出 PDF", "", "PDF 文件 (*.pdf);;所有文件 (*)"
    )
    if not path:
        return False

    page_layout = QPageLayout(
        QPageSize(QPageSize.A4),
        QPageLayout.Portrait,
        QMarginsF(15, 15, 15, 15),  # mm 边距
    )

    def _do_export(rendered_html: str) -> None:
        print_html = _build_print_html(rendered_html)
        if _export_pdf_via_headless_browser(print_html, path):
            return
        # 无 Chrome/Edge：使用 PyQt5 富文本引擎生成矢量正文 PDF
        if _export_pdf_with_qtdocument(rendered_html, path):
            return
        # 最后回退：QtWebEngine 的 printToPdf 在 Win7 上会光栅化页面，
        # 质量与体积均不如前两种方式，但保证任何机器都能导出。
        preview.page().printToPdf(path, page_layout)

    preview.get_rendered_html(_do_export)
    return True
