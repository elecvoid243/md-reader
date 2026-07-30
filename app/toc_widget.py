"""
toc_widget.py — 目录 (TOC) 导航面板

接收从 JS 端提取的标题层级数据，以树形结构展示。
点击标题项时发出 heading_clicked 信号，用于编辑器跳转和预览滚动。
"""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


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
