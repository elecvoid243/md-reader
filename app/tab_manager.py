"""
tab_manager.py — 多标签页管理

每个标签页包含一对 (MarkdownEditor, PreviewPane)。
管理文件路径、修改状态、标签切换和关闭。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QTabWidget, QSplitter, QWidget

from .editor import MarkdownEditor
from .preview import PreviewPane


class EditorPreviewPair(QWidget):
    """单个标签页：编辑器 + 预览的分割视图"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.file_path: str | None = None
        self.is_dirty: bool = False

        # 分割器：左编辑 右预览
        self._splitter = QSplitter()
        self.editor = MarkdownEditor()
        self.preview = PreviewPane()
        self._splitter.addWidget(self.editor)
        self._splitter.addWidget(self.preview)
        self._splitter.setSizes([500, 500])

        from PyQt5.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        # 防抖定时器：编辑后延迟渲染
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_render)

        # 编辑区文本变化 → 触发防抖渲染
        self.editor.textChanged.connect(self._on_text_changed)

        # 滚动同步
        self._sync_lock = False
        self.editor.scroll_percent_changed.connect(self._sync_preview_scroll)
        self.preview.scroll_updated.connect(self._sync_editor_scroll)

    def _on_text_changed(self) -> None:
        self.is_dirty = True
        self._debounce.start(300)  # 300ms 防抖

    def _do_render(self) -> None:
        text = self.editor.get_text()
        self.preview.render_markdown(text)

    def _sync_preview_scroll(self, percent: float) -> None:
        if self._sync_lock:
            return
        self._sync_lock = True
        self.preview.set_scroll_percent(percent)
        QTimer.singleShot(100, self._release_sync_lock)

    def _sync_editor_scroll(self, percent: float) -> None:
        if self._sync_lock:
            return
        self._sync_lock = True
        self.editor.set_scroll_percent(percent)
        QTimer.singleShot(100, self._release_sync_lock)

    def _release_sync_lock(self) -> None:
        self._sync_lock = False

    def render_now(self) -> None:
        """立即渲染（跳过防抖）"""
        self._debounce.stop()
        self._do_render()

    def set_scroll_sync_enabled(self, enabled: bool) -> None:
        if enabled:
            self.editor.scroll_percent_changed.connect(self._sync_preview_scroll)
            self.preview.scroll_updated.connect(self._sync_editor_scroll)
        else:
            try:
                self.editor.scroll_percent_changed.disconnect(self._sync_preview_scroll)
                self.preview.scroll_updated.disconnect(self._sync_editor_scroll)
            except TypeError:
                pass


class TabManager(QTabWidget):
    """多标签页管理器"""

    # 当前标签页变化时发出，参数为 EditorPreviewPair 或 None
    current_pair_changed = pyqtSignal(object)
    # 标签页标题需要更新
    title_changed = pyqtSignal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)

        self.tabCloseRequested.connect(self.close_tab)
        self.currentChanged.connect(self._on_current_changed)

    def add_tab(
        self, file_path: str | None = None, content: str = ""
    ) -> EditorPreviewPair:
        """
        新建标签页

        Args:
            file_path: 文件路径（None 表示新建未保存文档）
            content: 初始文本内容
        """
        pair = EditorPreviewPair()
        pair.file_path = file_path

        if content:
            pair.editor.set_text(content)
            pair.is_dirty = False

        title = self._make_title(file_path)
        idx = self.addTab(pair, title)
        self.setCurrentIndex(idx)

        # 初始渲染
        if content:
            pair.render_now()

        return pair

    def find_tab_by_path(self, file_path: str) -> EditorPreviewPair | None:
        """查找已打开指定文件的标签页"""
        abs_path = os.path.abspath(file_path)
        for i in range(self.count()):
            pair = self.widget(i)
            if isinstance(pair, EditorPreviewPair) and pair.file_path:
                if os.path.abspath(pair.file_path) == abs_path:
                    return pair
        return None

    def switch_to_path(self, file_path: str) -> bool:
        """切换到已打开指定文件的标签页，成功返回 True"""
        abs_path = os.path.abspath(file_path)
        for i in range(self.count()):
            pair = self.widget(i)
            if isinstance(pair, EditorPreviewPair) and pair.file_path:
                if os.path.abspath(pair.file_path) == abs_path:
                    self.setCurrentIndex(i)
                    return True
        return False

    def close_tab(self, index: int) -> None:
        """关闭标签页（带未保存提示）"""
        pair = self.widget(index)
        if isinstance(pair, EditorPreviewPair) and pair.is_dirty:
            from PyQt5.QtWidgets import QMessageBox

            reply = QMessageBox.question(
                self,
                "未保存的更改",
                f"文件 [{self.tabText(index)}] 有未保存的更改，是否保存？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Cancel:
                return
            if reply == QMessageBox.Save:
                self._save_pair(pair)

        self.removeTab(index)
        pair.deleteLater()

    def current_pair(self) -> EditorPreviewPair | None:
        """获取当前标签页的 EditorPreviewPair"""
        widget = self.currentWidget()
        if isinstance(widget, EditorPreviewPair):
            return widget
        return None

    def update_title(self, index: int) -> None:
        """更新标签页标题（反映修改状态）"""
        pair = self.widget(index)
        if isinstance(pair, EditorPreviewPair):
            title = self._make_title(pair.file_path)
            if pair.is_dirty:
                title = "● " + title
            self.setTabText(index, title)

    def _on_current_changed(self, index: int) -> None:
        pair = self.current_pair()
        self.current_pair_changed.emit(pair)

    def _make_title(self, file_path: str | None) -> str:
        if file_path:
            return os.path.basename(file_path)
        return "未命名"

    def _save_pair(self, pair: EditorPreviewPair) -> bool:
        """保存标签页内容到文件"""
        if not pair.file_path:
            from PyQt5.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "Markdown 文件 (*.md);;所有文件 (*)"
            )
            if not path:
                return False
            pair.file_path = path

        try:
            with open(pair.file_path, "w", encoding="utf-8") as f:
                f.write(pair.editor.get_text())
            pair.is_dirty = False
            # 更新标题
            for i in range(self.count()):
                if self.widget(i) is pair:
                    self.update_title(i)
                    break
            return True
        except OSError:
            return False

    def save_current(self) -> bool:
        """保存当前标签页"""
        pair = self.current_pair()
        if pair:
            return self._save_pair(pair)
        return False
