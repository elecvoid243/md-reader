"""
file_tree.py — 文件树侧边栏

基于 QTreeView + QFileSystemModel，浏览文件夹中的 Markdown 文件。
双击 .md 文件时发出 file_opened 信号。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QDir, QModelIndex, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFileSystemModel,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


class FileTreeWidget(QWidget):
    """文件树侧边栏组件"""

    file_opened = pyqtSignal(str)  # 双击文件时发出，参数为文件绝对路径

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 文件系统模型
        self._model = QFileSystemModel()
        self._model.setFilter(QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot)
        self._model.setNameFilters(["*.md", "*.markdown", "*.mdown", "*.txt"])
        self._model.setNameFilterDisables(False)  # 隐藏不匹配的文件

        # 树视图
        self._tree = QTreeView()
        self._tree.setModel(self._model)
        self._tree.setAnimated(True)
        self._tree.setIndentation(16)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(0, Qt.AscendingOrder)
        self._tree.setHeaderHidden(True)

        # 双击打开文件
        self._tree.doubleClicked.connect(self._on_double_click)

        layout.addWidget(self._tree)

    def set_root_path(self, path: str) -> None:
        """设置文件树的根目录"""
        if not os.path.isdir(path):
            return
        self._model.setRootPath(path)
        self._tree.setRootIndex(self._model.index(path))

        # 展开根目录
        root_index = self._model.index(path)
        self._tree.expand(root_index)

    def _on_double_click(self, index: QModelIndex) -> None:
        path = self._model.filePath(index)
        if path and os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in (".md", ".markdown", ".mdown", ".txt"):
                self.file_opened.emit(os.path.abspath(path))

    def current_root(self) -> str:
        return self._model.rootPath()
