"""
vditor_pane.py — Vditor 即时渲染编辑面板

基于 QWebEngineView 承载 Vditor（IR 即时渲染模式），提供 Typora 式的
"在渲染视图中直接编辑"体验。通过 QWebChannel 与 JS 端通信。

设计要点：
- Vditor 异步加载（lute/katex/mermaid 懒加载），用 _ready 标志 + 待处理内容队列处理
- Vditor 的 input 回调携带最新 Markdown 文本，Python 直接复用，避免二次全量取值；
  切换模式 / 保存等需要精确内容的场景仍按需拉取
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable

from PyQt5.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import QApplication, QMenu

_RESOURCES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources"
)
_VDITOR_HTML = os.path.join(_RESOURCES_DIR, "html", "vditor.html")


class VditorBridge(QObject):
    """Python ↔ Vditor(JS) 通信桥"""

    ready = pyqtSignal()  # Vditor 初始化完成
    input_changed = pyqtSignal(str)  # 内容发生变化（用户输入，携带最新 Markdown）

    @pyqtSlot()
    def onReady(self) -> None:  # noqa: N802
        self.ready.emit()

    @pyqtSlot(str)
    def onInput(self, text: str) -> None:  # noqa: N802
        self.input_changed.emit(text)


class VditorPane(QWebEngineView):
    """Vditor 即时渲染面板"""

    ready = pyqtSignal()
    input_changed = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._bridge = VditorBridge()
        self._ready = False
        self._pending_content: str | None = None
        # 字体设置（body 栈, mono 栈, 字号）；就绪后补发
        self._font_settings: tuple[str, str, int] | None = None

        # 转发信号
        self._bridge.ready.connect(self._on_ready)
        self._bridge.input_changed.connect(self.input_changed)

        # QWebChannel
        self._channel = QWebChannel()
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        # 加载宿主页面
        self.loadFinished.connect(self._on_load_finished)
        self.load(QUrl.fromLocalFile(_VDITOR_HTML))

    def _on_load_finished(self, ok: bool) -> None:
        # 页面加载完成后，等待 Vditor 自身初始化（after 回调触发 onReady）
        if not ok:
            print("[VditorPane] 页面加载失败")

    def _on_ready(self) -> None:
        self._ready = True
        # 冲刷待处理内容
        if self._pending_content is not None:
            content = self._pending_content
            self._pending_content = None
            self.set_content(content)
        if self._font_settings is not None:
            self._push_font_settings()
        self.ready.emit()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """
        覆盖 QWebEngineView 默认英文右键菜单，只保留 Vditor 编辑所需操作。

        “粘贴并匹配样式”不使用 Chromium 默认动作，而是直接读取 Qt 剪贴板
        纯文本后用 insertText 插入，确保与普通“粘贴”行为真正不同。
        """
        clipboard = QApplication.clipboard()
        has_selection = self.page().hasSelection()
        has_text = clipboard.mimeData().hasText()

        menu = QMenu(self)

        cut_action = menu.addAction("剪切")
        cut_action.setEnabled(has_selection)
        cut_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.Cut)
        )

        copy_action = menu.addAction("复制")
        copy_action.setEnabled(has_selection)
        copy_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.Copy)
        )

        paste_action = menu.addAction("粘贴")
        paste_action.setEnabled(has_text)
        paste_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.Paste)
        )

        plain_paste_action = menu.addAction("粘贴并匹配样式")
        plain_paste_action.setEnabled(has_text)
        plain_paste_action.triggered.connect(self._paste_plain_text)

        menu.addSeparator()

        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(
            lambda: self.page().triggerAction(QWebEnginePage.SelectAll)
        )

        menu.exec_(event.globalPos())
        event.accept()

    def _paste_plain_text(self) -> None:
        """以纯文本方式插入剪贴板内容，绕过 HTML 粘贴逻辑"""
        text = QApplication.clipboard().text()
        if not text:
            return
        js_code = (
            "focusVditor(); document.execCommand('insertText', false, %s);"
            % json.dumps(text)
        )
        self.page().runJavaScript(js_code)

    def set_content(self, md: str) -> None:
        """设置 Markdown 内容（未就绪时缓存）"""
        if not self._ready:
            self._pending_content = md
            return
        js = f"setVditorContent({json.dumps(md)});"
        self.page().runJavaScript(js)

    def get_content(self, callback: Callable[[str], None]) -> None:
        """异步获取当前 Markdown 内容"""
        self.page().runJavaScript("getVditorContent()", callback)

    def set_theme(self, theme_name: str) -> None:
        """切换主题（'light' / 'dark'）"""
        js = f"setVditorTheme({json.dumps(theme_name)});"
        self.page().runJavaScript(js)

    def apply_font_settings(self, body_stack: str, mono_stack: str, size: int) -> None:
        """应用字体设置（body/mono 为完整字体栈，空串表示跟随主题）"""
        self._font_settings = (body_stack, mono_stack, size)
        if self._ready:
            self._push_font_settings()

    def _push_font_settings(self) -> None:
        body, mono, size = self._font_settings
        js = "applyFontSettings(%s, %s, %d);" % (
            json.dumps(body), json.dumps(mono), int(size))
        self.page().runJavaScript(js)

    def scroll_to_heading(self, text: str) -> None:
        """滚动到指定文本的标题（即时渲染模式的 TOC 跳转）"""
        js = f"scrollVditorToHeading({json.dumps(text)});"
        self.page().runJavaScript(js)

    def focus_editor(self) -> None:
        """聚焦编辑器"""
        self.page().runJavaScript("focusVditor();")

    def is_ready(self) -> bool:
        return self._ready
