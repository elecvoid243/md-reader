"""
toc_widget.py — 目录 (TOC) 导航面板

接收从 JS 端提取的标题层级数据，以树形结构展示。
点击标题项时发出 heading_clicked 信号，用于编辑器跳转和预览滚动。
"""

from __future__ import annotations

import re

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


def make_heading_id(text: str, used: dict) -> str:
    """
    生成标题 id（与 resources/js/render.js 的 addHeadingIds 规则一致）

    规则：小写 → 非单词/中文字符折叠为 '-' → 去首尾 '-' → 空则 'heading'；
    重复 id 追加 '-2', '-3' 序号（used 为跨调用共享的计数器）。
    """
    hid = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower()).strip("-")
    if not hid:
        hid = "heading"
    if hid in used:
        used[hid] += 1
        hid = f"{hid}-{used[hid]}"
    else:
        used[hid] = 1
    return hid


def extract_headings(text: str) -> list[dict]:
    """
    从 Markdown 源码提取 TOC 条目（预览不渲染时的 TOC 数据源）

    返回: [{level: int, text: str, id: str, line: int(1-based)}, ...]
    跳过 fenced 代码块内的伪标题；id 规则与 JS 端渲染结果一致。
    """
    headings: list[dict] = []
    used: dict = {}
    in_code = False
    for lineno, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
        if m:
            level = len(m.group(1))
            htext = m.group(2)
            headings.append(
                {
                    "level": level,
                    "text": htext,
                    "id": make_heading_id(htext, used),
                    "line": lineno,
                }
            )
    return headings


class TocWidget(QWidget):
    """目录导航面板"""

    # 参数: (heading_id, level) — heading_id 用于预览滚动，level 用于编辑器定位
    heading_clicked = pyqtSignal(str, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        self._tree.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self._tree)

    def update_toc(self, toc_list: list[dict]) -> None:
        """
        更新目录树

        Args:
            toc_list: [{level: int, text: str, id: str}, ...]
        """
        self._tree.clear()
        if not toc_list:
            return

        # 用栈维护层级关系
        stack: list[tuple[QTreeWidgetItem, int]] = []  # (item, level)

        for entry in toc_list:
            level = entry.get("level", 1)
            text = entry.get("text", "")
            heading_id = entry.get("id", "")

            item = QTreeWidgetItem([text])
            item.setData(0, Qt.UserRole, heading_id)
            item.setData(0, Qt.UserRole + 1, level)
            item.setToolTip(0, text)

            # 找到合适的父节点
            while stack and stack[-1][1] >= level:
                stack.pop()

            if stack:
                stack[-1][0].addChild(item)
            else:
                self._tree.addTopLevelItem(item)

            stack.append((item, level))

        # 默认展开所有节点
        self._tree.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        heading_id = item.data(0, Qt.UserRole)
        level = item.data(0, Qt.UserRole + 1)
        if heading_id:
            self.heading_clicked.emit(heading_id, level)

    def clear_toc(self) -> None:
        self._tree.clear()
