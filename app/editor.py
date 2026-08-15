"""
editor.py — Markdown 编辑器组件

基于 QPlainTextEdit，提供：
- 行号显示（gutter）
- Markdown 语法高亮
- 当前行高亮
- 可配置的字体和 Tab 宽度
"""

from __future__ import annotations

import re

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PyQt5.QtWidgets import (
    QApplication,
    QMenu,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)


# ──────────────────────────────────────────────
#  行号侧栏
# ──────────────────────────────────────────────
class LineNumberArea(QWidget):
    """编辑器左侧行号区域"""

    def __init__(self, editor: MarkdownEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802
        self._editor.line_number_area_paint_event(event)


# ──────────────────────────────────────────────
#  Markdown 语法高亮
# ──────────────────────────────────────────────
class MarkdownHighlighter(QSyntaxHighlighter):
    """轻量级 Markdown 语法高亮器"""

    def __init__(self, document) -> None:
        super().__init__(document)
        self._rules: list[tuple] = []
        self._setup_rules()

    def _fmt(
        self, color: str, bold: bool = False, italic: bool = False
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        # 源码编辑视图只做语法着色，不应用粗体/斜体等字体样式，
        # 避免 Markdown 语法在源码中被“实时渲染”（例如 *斜体* 变斜体）。
        return fmt

    def _setup_rules(self) -> None:
        # 每条规则: (正则, 格式, 触发条件)
        # 触发条件用于在执行正则前做廉价的前置过滤（不得误杀合法匹配）:
        #   ("line", chars) — 行首非空白字符必须属于 chars
        #   ("digit", None) — 行首非空白字符必须是数字
        #   ("any",  substr) — 行内必须包含子串 substr
        self._rules = [
            # 标题
            (
                re.compile(r"^#{1,6}\s.*$", re.MULTILINE),
                self._fmt("#005cc5", bold=True),
                ("line", "#"),
            ),
            # 粗体
            (re.compile(r"\*\*[^*]+\*\*"), self._fmt("#24292e", bold=True), ("any", "**")),
            (re.compile(r"__[^_]+__"), self._fmt("#24292e", bold=True), ("any", "__")),
            # 斜体
            (re.compile(r"\*[^*]+\*"), self._fmt("#24292e", italic=True), ("any", "*")),
            (re.compile(r"_[^_]+_"), self._fmt("#24292e", italic=True), ("any", "_")),
            # 行内代码
            (re.compile(r"`[^`]+`"), self._fmt("#e36209"), ("any", "`")),
            # 链接
            (re.compile(r"\[([^\]]*)\]\([^)]*\)"), self._fmt("#0366d6"), ("any", "](")),
            # 图片
            (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), self._fmt("#22863a"), ("any", "![")),
            # 引用
            (
                re.compile(r"^>\s.*$", re.MULTILINE),
                self._fmt("#6a737d", italic=True),
                ("line", ">"),
            ),
            # 无序列表标记
            (
                re.compile(r"^\s*[-*+]\s", re.MULTILINE),
                self._fmt("#d73a49", bold=True),
                ("line", "-*+"),
            ),
            # 有序列表标记
            (
                re.compile(r"^\s*\d+\.\s", re.MULTILINE),
                self._fmt("#d73a49", bold=True),
                ("digit", None),
            ),
            # 水平线
            (
                re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE),
                self._fmt("#e1e4e8"),
                ("line", "-*_"),
            ),
            # LaTeX 公式
            (re.compile(r"\$\$[^$]+\$\$"), self._fmt("#6f42c1"), ("any", "$$")),
            (re.compile(r"\$[^$]+\$"), self._fmt("#6f42c1"), ("any", "$")),
        ]
        # 代码块高亮格式（预建复用，避免每个 block 新建 QTextCharFormat）
        self._code_fmt = self._fmt("#e36209")

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        if text:
            stripped = text.lstrip()
            first = stripped[0] if stripped else ""
            for pattern, fmt, (kind, cond) in self._rules:
                # 前置过滤：纯文本行直接跳过绝大多数正则
                if kind == "line":
                    if first not in cond:
                        continue
                elif kind == "digit":
                    if not first.isdigit():
                        continue
                elif cond not in text:
                    continue
                for match in pattern.finditer(text):
                    start, end = match.span()
                    self.setFormat(start, end - start, fmt)

        # 多行代码块高亮（``` 围栏）
        self._handle_code_blocks(text)

    def _handle_code_blocks(self, text: str) -> None:
        code_fmt = self._code_fmt
        fence_pattern = "```"

        # 状态机：previousBlockState 0=正常, 1=代码块内
        start_idx = 0
        in_block = self.previousBlockState() == 1

        if in_block:
            # 检查是否结束
            end_idx = text.find(fence_pattern)
            if end_idx >= 0:
                self.setFormat(0, end_idx + 3, code_fmt)
                self.setCurrentBlockState(0)
            else:
                self.setFormat(0, len(text), code_fmt)
                self.setCurrentBlockState(1)
            return

        # 检查是否开始
        start_idx = text.find(fence_pattern)
        if start_idx >= 0:
            self.setFormat(start_idx, len(text) - start_idx, code_fmt)
            # 检查是否在同一行结束
            end_idx = text.find(fence_pattern, start_idx + 3)
            if end_idx >= 0:
                self.setCurrentBlockState(0)
            else:
                self.setCurrentBlockState(1)


# ──────────────────────────────────────────────
#  Markdown 编辑器主控件
# ──────────────────────────────────────────────
class MarkdownEditor(QPlainTextEdit):
    """Markdown 文本编辑器，带行号和语法高亮"""

    # 自定义信号
    scroll_percent_changed = pyqtSignal(float)  # 滚动比例变化

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # 主题配色（默认亮色，可被 set_theme_colors 覆盖）
        self._theme_colors = {
            "gutter_bg": "#f3f0e6",
            "gutter_ink": "#b3ab96",
            "current_line": "#f4f1e6",
            "caret": "#0e6b5a",
            "border": "#e8e3d6",
        }

        # 行号区域
        self._line_area = LineNumberArea(self)
        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self._update_line_area_width(0)

        # 当前行高亮
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._highlight_current_line()

        # 语法高亮
        self._highlighter = MarkdownHighlighter(self.document())

        # 默认字体
        self._setup_font("Consolas", 14)

        # 基础设置
        self.setTabStopDistance(40)
        self.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        # 注意：不使用 setCenterOnScroll(True) —— 它会让光标每次移动都尝试居中，
        # 导致打字时整屏视口 + 行号栏持续重绘（编辑卡顿的主要来源之一）

    def set_theme_colors(self, colors: dict) -> None:
        """更新主题配色并重绘（行号栏/当前行）"""
        self._theme_colors.update(colors)
        self._highlight_current_line()
        self._line_area.update()

    def _setup_font(self, family: str, size: int) -> None:
        font = QFont(family, size)
        font.setStyleHint(QFont.Monospace)
        font.setFixedPitch(True)
        self.setFont(font)

    def set_editor_font(self, family: str, size: int) -> None:
        self._setup_font(family, size)
        self._update_line_area_width(0)

    # ── 行号绘制 ──

    def line_number_area_width(self) -> int:
        digits = max(1, len(str(self.blockCount())))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def _resize_line_number_area(self) -> None:
        """把行号栏固定到编辑器内容区左侧，并占据 viewport 左边距"""
        rect = self.contentsRect()
        self._line_area.setGeometry(
            QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height())
        )

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._resize_line_number_area()

    def _update_line_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
        self._resize_line_number_area()

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self._line_area)
        # 行号栏背景
        painter.fillRect(event.rect(), QColor(self._theme_colors["gutter_bg"]))
        # 行号栏与编辑区之间的细分隔线
        painter.setPen(QColor(self._theme_colors["border"]))
        painter.drawLine(
            event.rect().right(),
            event.rect().top(),
            event.rect().right(),
            event.rect().bottom(),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setPen(QColor(self._theme_colors["gutter_ink"]))
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.drawText(
                    0,
                    top,
                    self._line_area.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()

    # ── 当前行高亮 ──

    def _highlight_current_line(self) -> None:
        selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(self._theme_colors["current_line"]))
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            selections.append(selection)
        self.setExtraSelections(selections)

    # ── 滚动同步 ──

    def scroll_percent(self) -> float:
        """返回当前滚动位置比例 [0, 1]"""
        vbar = self.verticalScrollBar()
        if vbar.maximum() == 0:
            return 0.0
        return vbar.value() / vbar.maximum()

    def set_scroll_percent(self, percent: float) -> None:
        """按比例设置滚动位置"""
        vbar = self.verticalScrollBar()
        vbar.setValue(int(vbar.maximum() * percent))

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """源码编辑区右键菜单：全部中文，并单独提供“粘贴并匹配样式”"""
        clipboard = QApplication.clipboard()
        cursor = self.textCursor()
        has_selection = cursor.hasSelection()

        menu = QMenu(self)

        undo_action = menu.addAction("撤销")
        undo_action.setEnabled(self.document().isUndoAvailable())
        undo_action.triggered.connect(self.undo)

        redo_action = menu.addAction("重做")
        redo_action.setEnabled(self.document().isRedoAvailable())
        redo_action.triggered.connect(self.redo)

        menu.addSeparator()

        cut_action = menu.addAction("剪切")
        cut_action.setEnabled(has_selection)
        cut_action.triggered.connect(self.cut)

        copy_action = menu.addAction("复制")
        copy_action.setEnabled(has_selection)
        copy_action.triggered.connect(self.copy)

        paste_action = menu.addAction("粘贴")
        paste_action.setEnabled(self.canPaste())
        paste_action.triggered.connect(self.paste)

        plain_paste_action = menu.addAction("粘贴并匹配样式")
        plain_paste_action.setEnabled(bool(clipboard.text()))
        plain_paste_action.triggered.connect(self._paste_plain_text)

        delete_action = menu.addAction("删除")
        delete_action.setEnabled(has_selection)
        delete_action.triggered.connect(self._delete_selection)

        menu.addSeparator()

        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.selectAll)

        menu.exec_(event.globalPos())
        event.accept()

    def _paste_plain_text(self) -> None:
        """以纯文本方式粘贴剪贴板内容，丢弃富文本格式"""
        text = QApplication.clipboard().text()
        if text:
            self.insertPlainText(text)

    def _delete_selection(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()

    def wheelEvent(self, event) -> None:  # noqa: N802
        super().wheelEvent(event)
        self.scroll_percent_changed.emit(self.scroll_percent())

    # ── 便捷方法 ──

    def get_text(self) -> str:
        return self.toPlainText()

    def set_text(self, text: str) -> None:
        self.setPlainText(text)

    def goto_line(self, line: int) -> None:
        """跳转到指定行（1-based）"""
        block = self.document().findBlockByNumber(max(0, line - 1))
        cursor = QTextCursor(block)
        self.setTextCursor(cursor)
        self.centerCursor()
