"""
editor.py — Markdown 编辑器组件

基于 QPlainTextEdit，提供：
- 行号显示（gutter）
- Markdown 语法高亮
- 当前行高亮
- 可配置的字体和 Tab 宽度
"""

from __future__ import annotations

from PyQt5.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PyQt5.QtWidgets import QPlainTextEdit, QTextEdit, QWidget


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
        if bold:
            fmt.setFontWeight(QFont.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _setup_rules(self) -> None:
        import re

        # (正则, 格式) — 顺序决定优先级
        self._rules = [
            # 标题
            (
                re.compile(r"^#{1,6}\s.*$", re.MULTILINE),
                self._fmt("#005cc5", bold=True),
            ),
            # 粗体
            (re.compile(r"\*\*[^*]+\*\*"), self._fmt("#24292e", bold=True)),
            (re.compile(r"__[^_]+__"), self._fmt("#24292e", bold=True)),
            # 斜体
            (re.compile(r"\*[^*]+\*"), self._fmt("#24292e", italic=True)),
            (re.compile(r"_[^_]+_"), self._fmt("#24292e", italic=True)),
            # 行内代码
            (re.compile(r"`[^`]+`"), self._fmt("#e36209")),
            # 链接
            (re.compile(r"\[([^\]]*)\]\([^)]*\)"), self._fmt("#0366d6")),
            # 图片
            (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), self._fmt("#22863a")),
            # 引用
            (re.compile(r"^>\s.*$", re.MULTILINE), self._fmt("#6a737d", italic=True)),
            # 无序列表标记
            (re.compile(r"^\s*[-*+]\s", re.MULTILINE), self._fmt("#d73a49", bold=True)),
            # 有序列表标记
            (re.compile(r"^\s*\d+\.\s", re.MULTILINE), self._fmt("#d73a49", bold=True)),
            # 水平线
            (
                re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$", re.MULTILINE),
                self._fmt("#e1e4e8"),
            ),
            # LaTeX 公式
            (re.compile(r"\$\$[^$]+\$\$"), self._fmt("#6f42c1")),
            (re.compile(r"\$[^$]+\$"), self._fmt("#6f42c1")),
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

        # 多行代码块高亮（``` 围栏）
        self._handle_code_blocks(text)

    def _handle_code_blocks(self, text: str) -> None:
        code_fmt = self._fmt("#e36209")
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
        self.setCenterOnScroll(True)

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

    def _update_line_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def line_number_area_paint_event(self, event) -> None:
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor("#f0f0f0"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        painter.setPen(QColor("#999999"))
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
            selection.format.setBackground(QColor("#f5f5f5"))
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
