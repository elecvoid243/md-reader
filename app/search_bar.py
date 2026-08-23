"""
search_bar.py — 内容搜索组件

提供三样东西：
- SearchBar：通用搜索条 UI（输入框 + 大小写切换 + 计数 + 上/下一个 + 关闭），
  嵌在各个面板顶部布局中，默认隐藏
- WebSearchController：QWebEngineView 的搜索（阅读模式预览 / 即时渲染），
  封装 QWebEnginePage.findText，支持匹配计数与环绕
- EditorSearchController：QPlainTextEdit 的搜索（源码编辑），
  QTextDocument.find 扫描全部匹配并以 extra selections 高亮

交互约定：Enter/Shift+Enter = 下一个/上一个，Esc = 关闭。
"""

from __future__ import annotations

import json
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QWidget,
)

from .theme_manager import LIGHT_PALETTE

# 编辑器中全部匹配 / 当前匹配的高亮底色（与「墨与纸 · 昼」同源的暖黄系）
_MATCH_BG = LIGHT_PALETTE.get("search_match", "#f6e9a0")
_MATCH_BG_CURRENT = LIGHT_PALETTE.get("search_match_current", "#f2b24c")


class SearchBar(QWidget):
    """面板顶部的搜索条（纯 UI，不含查找逻辑）"""

    # 文本或大小写设置变化（增量搜索）
    search_changed = pyqtSignal(str)
    next_requested = pyqtSignal()
    prev_requested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("search_bar")
        self._icons = {}  # type: dict

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(4)

        self._hint = QLabel()
        self._hint.setObjectName("search_hint")
        lay.addWidget(self._hint)

        self._input = QLineEdit()
        self._input.setObjectName("search_input")
        self._input.setPlaceholderText("查找…")
        self._input.setClearButtonEnabled(True)
        self._input.setFixedWidth(220)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        lay.addWidget(self._input, 1)

        self._btn_case = QToolButton()
        self._btn_case.setText("Aa")
        self._btn_case.setToolTip("区分大小写")
        self._btn_case.setCheckable(True)
        self._btn_case.setAutoRaise(True)
        self._btn_case.clicked.connect(self._on_options_changed)
        lay.addWidget(self._btn_case)

        self._count = QLabel("")
        self._count.setObjectName("search_count")
        self._count.setMinimumWidth(48)
        self._count.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._count)

        self._btn_prev = QToolButton()
        self._btn_prev.setToolTip("上一个 (Shift+Enter)")
        self._btn_prev.setAutoRaise(True)
        self._btn_prev.clicked.connect(self.prev_requested.emit)
        lay.addWidget(self._btn_prev)

        self._btn_next = QToolButton()
        self._btn_next.setToolTip("下一个 (Enter)")
        self._btn_next.setAutoRaise(True)
        self._btn_next.clicked.connect(self.next_requested.emit)
        lay.addWidget(self._btn_next)

        self._btn_close = QToolButton()
        self._btn_close.setToolTip("关闭 (Esc)")
        self._btn_close.setAutoRaise(True)
        self._btn_close.clicked.connect(self.close_bar)
        lay.addWidget(self._btn_close)

        self.hide()

    # ── 外观注入 ──

    def set_icons(self, search, prev, next_, close) -> None:
        """注入主题图标（icons.py 产物）"""
        self._hint.setPixmap(search.pixmap(16, 16) if search else None)
        self._btn_prev.setIcon(prev)
        self._btn_next.setIcon(next_)
        self._btn_close.setIcon(close)

    # ── 状态查询 ──

    def is_open(self) -> bool:
        return self.isVisible()

    def text(self) -> str:
        return self._input.text()

    def case_sensitive(self) -> bool:
        return self._btn_case.isChecked()

    # ── 打开 / 关闭 ──

    def open_bar(self) -> None:
        self.show()
        self.raise_()
        self._input.setFocus()
        self._input.selectAll()

    def close_bar(self) -> None:
        if not self.isVisible():
            return
        self.hide()
        self.closed.emit()

    def set_result(self, current: int, total: int) -> None:
        """更新匹配计数显示。

        current > 0 时显示 "m/n"（编辑器搜索可定位当前序号）；
        仅知总数时显示 "N 处"（网页搜索的 Chromium 回调只给 bool）。
        """
        if total <= 0:
            self._count.setText(self.text() and "无结果" or "")
        elif current > 0:
            self._count.setText("%d/%d" % (current, total))
        else:
            self._count.setText("%d 处" % total)

    # ── 内部 ──

    def _on_text_changed(self, text: str) -> None:
        self.search_changed.emit(text)
        if not text:
            self._count.setText("")

    def _on_options_changed(self) -> None:
        self.search_changed.emit(self.text())

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self._input and event.type() == event.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    self.prev_requested.emit()
                else:
                    self.next_requested.emit()
                return True
            if key == Qt.Key_Escape:
                self.close_bar()
                return True
        return super().eventFilter(obj, event)


class WebSearchController(QObject):
    """QWebEngineView 搜索：封装 QWebEnginePage.findText。

    本环境（PyQt5 5.15 / Chromium 83）的两个限制：
    - findText 的回调重载只回传 bool（无 QWebEngineFindTextResult），
      匹配总数改由页面内 JS 统计（两套页面均内置 countSearchMatches，
      只读扫描文本节点，不修改 DOM，不影响导出）
    - 没有 FindWrapsAroundDocument 枚举，环绕由"清除锚点后同方向重搜"
      模拟：全新搜索从文档开头（向后）/末尾（向前）起步
    """

    def __init__(self, view: QWebEngineView, bar: SearchBar, parent=None) -> None:
        super().__init__(parent)
        self._view = view
        self._bar = bar
        self._cb_supported = True  # findText 回调重载是否可用（探测一次）

        bar.search_changed.connect(self._on_search_changed)
        bar.next_requested.connect(lambda: self.step(forward=True))
        bar.prev_requested.connect(lambda: self.step(forward=False))
        bar.closed.connect(self.clear)

    # ── 对外 ──

    def refresh(self) -> None:
        """内容重渲染后重跑当前搜索（高亮已随 DOM 重建丢失）"""
        if self._bar.is_open() and self._bar.text():
            self._on_search_changed(self._bar.text())

    def step(self, forward: bool) -> None:
        text = self._bar.text()
        if not text:
            return
        page = self._view.page()
        flags = self._flags(backward=not forward)

        def wrap_if_none(found) -> None:
            if not found:
                page.findText("")
                page.findText(text, flags)

        if self._cb_supported:
            try:
                page.findText(text, flags, wrap_if_none)
                return
            except TypeError:
                self._cb_supported = False
        page.findText(text, flags)

    def clear(self) -> None:
        self._view.page().findText("")
        self._bar.set_result(0, 0)

    # ── 内部 ──

    def _flags(self, backward: bool = False) -> QWebEnginePage.FindFlags:
        flags = QWebEnginePage.FindFlags()
        if backward:
            flags |= QWebEnginePage.FindBackward
        if self._bar.case_sensitive():
            flags |= QWebEnginePage.FindCaseSensitively
        return flags

    def _on_search_changed(self, text: str) -> None:
        if not text:
            self.clear()
            return
        self._view.page().findText(text, self._flags())
        self._count_async(text)

    def _count_async(self, text: str) -> None:
        sensitive = "true" if self._bar.case_sensitive() else "false"
        js = "countSearchMatches(%s, %s)" % (json.dumps(text), sensitive)
        self._view.page().runJavaScript(js, self._on_count)

    def _on_count(self, n) -> None:
        if not self._bar.is_open():
            return
        total = int(n) if isinstance(n, (int, float)) else 0
        self._bar.set_result(0, total)


class EditorSearchController(QObject):
    """QPlainTextEdit 搜索：全量扫描 + extra selections 高亮 + 导航"""

    def __init__(self, editor, bar: SearchBar, parent=None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._bar = bar
        self._positions: List[Tuple[int, int]] = []
        self._current = -1

        # 内容变化后延迟重扫（正在编辑时不跳动光标，仅刷新高亮）
        self._rescan_timer = QTimer()
        self._rescan_timer.setSingleShot(True)
        self._rescan_timer.setInterval(250)
        self._rescan_timer.timeout.connect(lambda: self._rescan(select_current=False))
        editor.textChanged.connect(self._schedule_rescan)

        bar.search_changed.connect(lambda _t: self._rescan(select_current=True))
        bar.next_requested.connect(lambda: self.step(forward=True))
        bar.prev_requested.connect(lambda: self.step(forward=False))
        bar.closed.connect(self.clear)

    # ── 对外 ──

    def refresh(self) -> None:
        if self._bar.is_open():
            self._rescan(select_current=False)

    def step(self, forward: bool) -> None:
        if not self._positions:
            return
        if self._current < 0:
            self._current = 0
        elif forward:
            self._current = (self._current + 1) % len(self._positions)
        else:
            self._current = (self._current - 1) % len(self._positions)
        self._apply_selections()
        self._bar.set_result(self._current + 1, len(self._positions))
        self._select_current()

    def clear(self) -> None:
        self._positions = []
        self._current = -1
        self._editor.set_search_selections([])
        self._bar.set_result(0, 0)

    # ── 内部 ──

    def _schedule_rescan(self) -> None:
        if self._bar.is_open() and self._bar.text():
            self._rescan_timer.start()

    def _flags(self) -> QTextDocument.FindFlags:
        if self._bar.case_sensitive():
            return QTextDocument.FindFlags(QTextDocument.FindCaseSensitively)
        return QTextDocument.FindFlags()

    def _rescan(self, select_current: bool) -> None:
        text = self._bar.text()
        if not self._bar.is_open() or not text:
            self.clear()
            return

        doc = self._editor.document()
        flags = self._flags()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)

        positions: List[Tuple[int, int]] = []
        while True:
            found = doc.find(text, cursor, flags)
            if found.isNull():
                break
            positions.append((found.selectionStart(), found.selectionEnd()))
            cursor = QTextCursor(doc)
            cursor.setPosition(found.selectionEnd())

        self._positions = positions
        if not positions:
            self._current = -1
            self._editor.set_search_selections([])
            self._bar.set_result(0, 0)
            return

        # 当前匹配：取距现有光标最近的（在其后第一个，否则最后一个）
        pos = self._editor.textCursor().position()
        self._current = len(positions) - 1
        for idx, (start, _end) in enumerate(positions):
            if start >= pos:
                self._current = idx
                break

        self._apply_selections()
        self._bar.set_result(self._current + 1, len(positions))
        if select_current:
            self._select_current()

    def _apply_selections(self) -> None:
        from PyQt5.QtWidgets import QTextEdit

        fmt_match = QTextCharFormat()
        fmt_match.setBackground(QColor(_MATCH_BG))
        fmt_current = QTextCharFormat()
        fmt_current.setBackground(QColor(_MATCH_BG_CURRENT))

        selections = []
        for idx, (start, end) in enumerate(self._positions):
            sel = QTextEdit.ExtraSelection()
            cursor = QTextCursor(self._editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            sel.cursor = cursor
            sel.format = fmt_current if idx == self._current else fmt_match
            selections.append(sel)
        self._editor.set_search_selections(selections)

    def _select_current(self) -> None:
        if self._current < 0 or self._current >= len(self._positions):
            return
        start, end = self._positions[self._current]
        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self._editor.setTextCursor(cursor)
