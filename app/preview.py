"""
preview.py — Markdown 预览引擎

基于 QWebEngineView，通过 QWebChannel 与 JS 端通信。
渲染管线全部在 JS 端完成（marked + KaTeX + mermaid + highlight.js）。
"""

from __future__ import annotations

import json
import os

from PyQt5.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView

# 资源目录（相对于项目根目录）
_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
)
_PREVIEW_HTML = os.path.join(_RESOURCES_DIR, "html", "preview.html")


class JsBridge(QObject):
    """
    Python ↔ JavaScript 通信桥

    JS 端通过 window.bridge 调用这些 slot；
    Python 端通过 signal 接收 JS 发来的数据。
    """

    # JS → Python 信号
    toc_updated = pyqtSignal(list)  # TOC 列表 [{level, text, id}, ...]
    render_finished = pyqtSignal()  # 渲染完成
    scroll_updated = pyqtSignal(float)  # 预览区滚动比例

    @pyqtSlot(str)
    def onTocUpdate(self, toc_json: str) -> None:  # noqa: N802
        """接收 JS 端提取的 TOC 数据"""
        try:
            toc = json.loads(toc_json)
            self.toc_updated.emit(toc)
        except json.JSONDecodeError:
            self.toc_updated.emit([])

    @pyqtSlot()
    def onRenderFinished(self) -> None:  # noqa: N802
        """JS 端渲染完成通知"""
        self.render_finished.emit()

    @pyqtSlot(float)
    def onScroll(self, percent: float) -> None:  # noqa: N802
        """预览区滚动比例"""
        self.scroll_updated.emit(percent)


class PreviewPane(QWebEngineView):
    """Markdown 预览面板"""

    # 转发 bridge 的信号，方便外部连接
    toc_updated = pyqtSignal(list)
    render_finished = pyqtSignal()
    scroll_updated = pyqtSignal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._bridge = JsBridge()
        self._ready = False
        self._pending_markdown: str | None = None
        # 上次已送渲染的文本（相同则跳过，避免标签切换/重复触发时的全量重渲染）
        self._last_rendered: str | None = None

        # 转发信号
        self._bridge.toc_updated.connect(self.toc_updated)
        self._bridge.render_finished.connect(self.render_finished)
        self._bridge.scroll_updated.connect(self.scroll_updated)

        # 设置 QWebChannel
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        # 加载预览页面
        self._load_preview_page()

        # 页面加载完成后标记就绪
        self.loadFinished.connect(self._on_load_finished)

    def _load_preview_page(self) -> None:
        url = QUrl.fromLocalFile(_PREVIEW_HTML)
        self.load(url)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self._ready = True
            # 页面重新加载后 DOM 已重置，渲染缓存同步失效
            self._last_rendered = None
            # 如果有等待渲染的内容，立即渲染
            if self._pending_markdown is not None:
                text = self._pending_markdown
                self._pending_markdown = None
                self.render_markdown(text)

    def render_markdown(self, text: str) -> None:
        """
        渲染 Markdown 文本

        如果页面尚未加载完成，会缓存文本等待就绪后渲染。
        文本与上次渲染一致时跳过（DOM 中已是对应内容）。
        """
        if not self._ready:
            self._pending_markdown = text
            return

        if text == self._last_rendered:
            return
        self._last_rendered = text

        # 通过 JS 调用渲染函数（json.dumps 确保字符串安全转义）
        js_code = f"renderMarkdown({json.dumps(text)});"
        self.page().runJavaScript(js_code)

    def set_theme(self, theme_name: str) -> None:
        """切换预览主题 ('light' / 'dark')"""
        js_code = f"setTheme({json.dumps(theme_name)});"
        self.page().runJavaScript(js_code)

    def set_scroll_percent(self, percent: float) -> None:
        """设置预览区滚动位置（用于滚动同步）"""
        js_code = f"setScrollPercent({percent});"
        self.page().runJavaScript(js_code)

    def scroll_to_heading(self, heading_id: str) -> None:
        """滚动到指定标题"""
        js_code = f"scrollToHeading({json.dumps(heading_id)});"
        self.page().runJavaScript(js_code)

    def get_rendered_html(self, callback) -> None:
        """获取渲染后的 HTML（异步，通过 callback 返回）"""
        self.page().runJavaScript("getRenderedHtml()", callback)

    def is_ready(self) -> bool:
        return self._ready
