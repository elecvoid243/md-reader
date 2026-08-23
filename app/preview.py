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
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import QMenu, QScrollBar

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
    scroll_metrics = pyqtSignal(int, int, int)  # top, scrollHeight, clientHeight

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

    @pyqtSlot(int, int, int)
    def onScrollMetrics(self, top: int, height: int, client: int) -> None:  # noqa: N802
        """预览区滚动尺寸（原生滚动条代理）"""
        self.scroll_metrics.emit(top, height, client)


class PreviewPane(QWebEngineView):
    """Markdown 预览面板"""

    # 转发 bridge 的信号，方便外部连接
    toc_updated = pyqtSignal(list)
    render_finished = pyqtSignal()
    scroll_updated = pyqtSignal(float)
    scroll_metrics = pyqtSignal(int, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._bridge = JsBridge()
        self._ready = False
        self._pending_markdown: str | None = None
        # 字体设置（body 栈, mono 栈, 字号）；页面懒加载，就绪后补发
        self._font_settings: tuple[str, str, int] | None = None
        # 上次已送渲染的文本（相同则跳过，避免标签切换/重复触发时的全量重渲染）
        self._last_rendered: str | None = None
        # 页面是否已开始加载（懒加载：构造时不加载，首次真正需要渲染时才
        # 启动 load —— 避免每个新标签页都立即解析 marked/katex/mermaid 等 JS）
        self._load_started = False

        # 阅读模式的原生滚动条代理
        self._native_scrollbar: QScrollBar | None = None
        self._proxy_enabled = False
        self._apply_proxy_when_ready = False
        self._updating_native_scrollbar = False

        # 转发信号
        self._bridge.toc_updated.connect(self.toc_updated)
        self._bridge.render_finished.connect(self.render_finished)
        self._bridge.scroll_updated.connect(self.scroll_updated)
        self._bridge.scroll_metrics.connect(self.scroll_metrics)
        self._bridge.scroll_metrics.connect(self._on_scroll_metrics)

        # 设置 QWebChannel
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        # 页面加载完成信号（加载本身推迟到 _ensure_loaded）
        self.loadFinished.connect(self._on_load_finished)

    def attach_native_scrollbar(self, scrollbar: QScrollBar) -> None:
        """阅读模式接入原生 Qt 滚动条，由它代理网页滚动"""
        if self._native_scrollbar is not None:
            try:
                self._native_scrollbar.valueChanged.disconnect(
                    self._on_native_scrollbar_changed
                )
            except TypeError:
                pass
        self._native_scrollbar = scrollbar
        scrollbar.valueChanged.connect(self._on_native_scrollbar_changed)

    def set_native_scroll_proxy_enabled(self, enabled: bool) -> None:
        """开启/关闭阅读模式的滚动条代理"""
        self._proxy_enabled = enabled
        self._apply_proxy_when_ready = enabled
        if self._native_scrollbar is not None:
            self._native_scrollbar.setVisible(enabled)
        if self._ready:
            self.page().runJavaScript(
                "setNativeScrollProxy(%s);" % ("true" if enabled else "false")
            )

    def _on_native_scrollbar_changed(self, value: int) -> None:
        if self._updating_native_scrollbar or not self._proxy_enabled:
            return
        self.page().runJavaScript(f"setScrollTop({int(value)});")

    def _on_scroll_metrics(self, top: int, height: int, client: int) -> None:
        bar = self._native_scrollbar
        if bar is None or not self._proxy_enabled:
            return
        maximum = max(0, height - client)
        self._updating_native_scrollbar = True
        try:
            bar.setRange(0, maximum)
            bar.setPageStep(max(1, client))
            bar.setVisible(maximum > 0)
            if not bar.isSliderDown():
                bar.setValue(min(max(top, 0), maximum))
        finally:
            self._updating_native_scrollbar = False

    def _ensure_loaded(self) -> None:
        """按需启动页面加载（幂等）"""
        if not self._load_started:
            self._load_started = True
            self._load_preview_page()

    def _load_preview_page(self) -> None:
        url = QUrl.fromLocalFile(_PREVIEW_HTML)
        self.load(url)

    def _on_load_finished(self, ok: bool) -> None:
        if ok:
            self._ready = True
            # 页面重新加载后 DOM 已重置，渲染缓存同步失效
            self._last_rendered = None
            # 页面加载前可能已设置过滚动代理状态，补发一次
            self.page().runJavaScript(
                "setNativeScrollProxy(%s);"
                % ("true" if self._apply_proxy_when_ready else "false")
            )
            # 如果有等待渲染的内容，立即渲染
            if self._pending_markdown is not None:
                text = self._pending_markdown
                self._pending_markdown = None
                self.render_markdown(text)
            # 页面重载后 <style> 丢失，补发字体设置
            if self._font_settings is not None:
                self._push_font_settings()

    def render_markdown(self, text: str) -> None:
        """
        渲染 Markdown 文本

        如果页面尚未加载完成，会缓存文本等待就绪后渲染。
        文本与上次渲染一致时跳过（DOM 中已是对应内容）。
        """
        if not self._ready:
            self._ensure_loaded()
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

    def apply_font_settings(self, body_stack: str, mono_stack: str, size: int) -> None:
        """应用字体设置（body/mono 为完整字体栈，空串表示跟随主题）"""
        self._font_settings = (body_stack, mono_stack, size)
        if self._ready:
            self._push_font_settings()

    def _push_font_settings(self) -> None:
        body, mono, size = self._font_settings
        js_code = "applyFontSettings(%s, %s, %d);" % (
            json.dumps(body), json.dumps(mono), int(size))
        self.page().runJavaScript(js_code)

    def set_scroll_percent(self, percent: float) -> None:
        """设置预览区滚动位置（用于滚动同步）"""
        js_code = f"setScrollPercent({percent});"
        self.page().runJavaScript(js_code)

    def scroll_to_heading(self, heading_id: str) -> None:
        """滚动到指定标题"""
        js_code = f"scrollToHeading({json.dumps(heading_id)});"
        self.page().runJavaScript(js_code)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """
        覆盖 QWebEngineView 默认右键菜单。

        默认菜单里的 Back/Forward 在本应用中无意义；Reload 会丢失当前
        已渲染的 Markdown 内容；View Page Source 也不是应用需要的入口。
        这里只保留实际有用的复制/全选。
        """
        menu = QMenu(self)
        copy_action = menu.addAction("复制")
        copy_action.setEnabled(self.page().hasSelection())
        copy_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.Copy)
        )
        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.SelectAll)
        )
        menu.exec_(event.globalPos())
        event.accept()

    def get_rendered_html(self, callback) -> None:
        """获取渲染后的 HTML（异步，通过 callback 返回）"""
        self._ensure_loaded()
        self.page().runJavaScript("getRenderedHtml()", callback)

    def is_ready(self) -> bool:
        return self._ready
