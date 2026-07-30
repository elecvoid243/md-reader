"""
exporter.py — 导出功能

支持将当前预览内容导出为：
- 独立 HTML 文件（内联 CSS，可离线打开）
- PDF 文件（通过 QWebEngineView.printToPdf）
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QMarginsF
from PyQt5.QtGui import QPageLayout, QPageSize
from PyQt5.QtWidgets import QFileDialog, QWidget

from .preview import PreviewPane

_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
)


def _read_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


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
        # 读取 CSS 文件内联
        markdown_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "markdown.css"))
        theme_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "theme-light.css"))
        katex_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "katex.min.css"))
        hljs_css = _read_file(os.path.join(_RESOURCES_DIR, "css", "github.min.css"))

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
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

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(full_html)
        except OSError:
            pass

    preview.get_rendered_html(_do_export)
    return True


def export_pdf(preview: PreviewPane, parent: QWidget | None = None) -> bool:
    """
    导出为 PDF 文件

    使用 QWebEngineView.printToPdf 生成 A4 排版的 PDF。
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

    preview.page().printToPdf(path, page_layout)
    return True
