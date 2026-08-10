"""
tab_manager.py — 多标签页管理

每个标签页包含一对 (MarkdownEditor, PreviewPane)。
管理文件路径、修改状态、标签切换和关闭。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QToolButton,
    QWidget,
)

from .editor import MarkdownEditor
from .preview import PreviewPane
from .toc_widget import extract_headings
from .vditor_pane import VditorPane


class EditorPreviewPair(QWidget):
    """单个标签页：编辑器 + 预览的分割视图"""

    # 预览不可见时（即时渲染/单栏源码），TOC 需从源码提取更新
    headings_changed = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.file_path: str | None = None
        self.is_dirty: bool = False
        self.view_mode: str = "reading"  # reading / edit / instant
        self.dual_pane: bool = True  # 源码编辑模式下是否显示预览
        # 视图模式是否已真正应用过（防止 set_view_mode 的相同模式短路
        # 导致新标签页保持"编辑器+预览都可见"的初始状态）
        self._mode_applied: bool = False
        self._vditor_pane: VditorPane | None = None  # 懒加载

        # 分割器：左编辑 右预览
        self._splitter = QSplitter()
        self.editor = MarkdownEditor()
        self.preview = PreviewPane()
        self._splitter.addWidget(self.editor)
        self._splitter.addWidget(self.preview)
        self._splitter.setSizes([480, 520])

        from PyQt5.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        # 防抖定时器：编辑后延迟渲染
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_render)

        # Vditor → 编辑器 防抖同步定时器（即时渲染模式下保持编辑器为最新数据源）
        self._vditor_sync_timer = QTimer()
        self._vditor_sync_timer.setSingleShot(True)
        self._vditor_sync_timer.timeout.connect(self._sync_vditor_to_editor)

        # 编辑区文本变化 → 触发防抖渲染
        self.editor.textChanged.connect(self._on_text_changed)

        # 滚动同步
        self._sync_lock = False
        self.editor.scroll_percent_changed.connect(self._sync_preview_scroll)
        self.preview.scroll_updated.connect(self._sync_editor_scroll)

        # 右上角浮动 单/双栏 切换控件（仅源码编辑模式显示）
        self._dual_pane_cb = None
        self._build_pane_toggle()

    def _build_pane_toggle(self) -> None:
        """构建右上角浮动的单/双栏分段控件"""
        self._pane_toggle = QWidget(self)
        self._pane_toggle.setObjectName("pane_toggle")
        lay = QHBoxLayout(self._pane_toggle)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        self._btn_single = QToolButton()
        self._btn_single.setObjectName("pane_single")
        self._btn_single.setCheckable(True)
        self._btn_single.setAutoRaise(True)
        self._btn_single.setIconSize(QSize(16, 16))
        self._btn_single.setToolTip("单栏：仅显示编辑器")

        self._btn_dual = QToolButton()
        self._btn_dual.setObjectName("pane_dual")
        self._btn_dual.setCheckable(True)
        self._btn_dual.setAutoRaise(True)
        self._btn_dual.setIconSize(QSize(16, 16))
        self._btn_dual.setToolTip("双栏：编辑器 + 实时预览")

        group = QButtonGroup(self)
        group.setExclusive(True)
        group.addButton(self._btn_single)
        group.addButton(self._btn_dual)

        lay.addWidget(self._btn_single)
        lay.addWidget(self._btn_dual)

        self._btn_single.setChecked(not self.dual_pane)
        self._btn_dual.setChecked(self.dual_pane)
        self._btn_single.clicked.connect(lambda: self._request_pane(False))
        self._btn_dual.clicked.connect(lambda: self._request_pane(True))

        # 注意：不使用 QGraphicsDropShadowEffect —— GraphicsEffect 会强制该控件
        # 每次重绘走离屏 pixmap + 模糊，拖累其下方编辑区的重绘效率。
        # 悬浮感由 QSS 的 1px 边框 + 圆角（theme_manager #pane_toggle）承担。

        self._pane_toggle.hide()

    def set_dual_pane_callback(self, cb) -> None:
        """注入双栏切换回调（点击浮动按钮时通知主窗口更新全局状态）"""
        self._dual_pane_cb = cb

    def set_pane_icons(self, icon_single, icon_dual) -> None:
        """设置浮动按钮图标（随主题刷新）"""
        self._btn_single.setIcon(icon_single)
        self._btn_dual.setIcon(icon_dual)

    def _request_pane(self, dual: bool) -> None:
        """浮动按钮点击：通过回调驱动全局双栏状态"""
        if dual == self.dual_pane:
            return
        self._btn_dual.setChecked(dual)
        self._btn_single.setChecked(not dual)
        if self._dual_pane_cb is not None:
            self._dual_pane_cb(dual)

    def _reposition_pane_toggle(self) -> None:
        """将浮动控件定位到右上角"""
        self._pane_toggle.adjustSize()
        w = self._pane_toggle.width()
        self._pane_toggle.move(max(0, self.width() - w - 12), 10)
        self._pane_toggle.raise_()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._reposition_pane_toggle()

    def _on_text_changed(self) -> None:
        self.is_dirty = True
        self._debounce.start(300)  # 300ms 防抖

    def _do_render(self) -> None:
        # 预览不可见时（即时渲染 / 单栏源码）跳过渲染，
        # 但 TOC 仍需从源码提取更新
        if not self.is_preview_visible():
            self.headings_changed.emit(extract_headings(self.editor.get_text()))
            return
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

    def set_view_mode(self, mode: str, dual_pane: bool) -> None:
        """
        设置视图模式

        Args:
            mode: "reading"（仅预览）/ "edit"（源码编辑）/ "instant"（即时渲染）
            dual_pane: 源码编辑模式下是否同时显示预览
        """
        # 浮动单/双栏控件可见性必须始终与模式同步（即便下方提前返回）
        self._pane_toggle.setVisible(mode == "edit")

        if (
            self._mode_applied
            and mode == self.view_mode
            and dual_pane == self.dual_pane
        ):
            return

        # 离开即时渲染模式：需先异步取回 Vditor 内容，再切换
        if (
            self.view_mode == "instant"
            and mode != "instant"
            and self._vditor_pane is not None
        ):
            self.view_mode = mode
            self.dual_pane = dual_pane
            self._vditor_pane.get_content(
                lambda md: self._finish_leave_instant(md, mode, dual_pane)
            )
            return

        self._apply_mode(mode, dual_pane)

    def _finish_leave_instant(self, md: str | None, mode: str, dual_pane: bool) -> None:
        """从即时渲染切出：把 Vditor 内容同步回编辑器后再应用目标模式"""
        if md is not None:
            self.editor.set_text(md)
        self._apply_mode(mode, dual_pane)

    def _apply_mode(self, mode: str, dual_pane: bool) -> None:
        """实际应用模式：控制三个面板的显隐 + 浮动控件"""
        self.view_mode = mode
        self.dual_pane = dual_pane
        self._mode_applied = True

        # 浮动单/双栏控件仅在源码编辑模式显示
        show_pane = mode == "edit"
        self._pane_toggle.setVisible(show_pane)

        if mode == "reading":
            # 阅读模式：仅预览，全宽
            self._hide_vditor()
            self.editor.hide()
            self.preview.show()
            self.render_now()
        elif mode == "edit":
            # 源码编辑：编辑器可见，预览按 dual_pane 决定
            self._hide_vditor()
            self.editor.show()
            if dual_pane:
                self.preview.show()
                self._restore_split()
                self.render_now()
            else:
                self.preview.hide()
            # 同步浮动按钮选中态并定位
            self._btn_dual.setChecked(dual_pane)
            self._btn_single.setChecked(not dual_pane)
            self._reposition_pane_toggle()
        elif mode == "instant":
            # 即时渲染：仅 Vditor，把编辑器内容推入
            self.editor.hide()
            self.preview.hide()
            self._ensure_vditor()
            self._vditor_pane.show()
            self._vditor_pane.set_content(self.editor.get_text())

    def _ensure_vditor(self) -> None:
        """懒加载创建 VditorPane（首次进入即时渲染时）"""
        if self._vditor_pane is None:
            self._vditor_pane = VditorPane()
            self._splitter.addWidget(self._vditor_pane)
            self._vditor_pane.input_changed.connect(self._on_vditor_input)

    def _hide_vditor(self) -> None:
        if self._vditor_pane is not None:
            self._vditor_pane.hide()

    def _on_vditor_input(self) -> None:
        """Vditor 中用户输入 → 标记脏状态 + 启动防抖同步"""
        self.is_dirty = True
        self._vditor_sync_timer.start(600)

    def _sync_vditor_to_editor(self) -> None:
        """把 Vditor 内容同步回编辑器（保持编辑器为最新数据源）"""
        if self._vditor_pane is not None and self.view_mode == "instant":
            self._vditor_pane.get_content(self._apply_vditor_content)

    def _apply_vditor_content(self, md: str | None) -> None:
        if md is None:
            return
        # 内容一致时跳过：避免每次同步都全量 setPlainText
        # （会清空 undo 栈、触发全文重新高亮、重置光标）
        if md == self.editor.get_text():
            return
        # 阻断 textChanged 引发的脏标记/防抖渲染连锁（预览此时不可见）
        self.editor.blockSignals(True)
        try:
            self.editor.set_text(md)
        finally:
            self.editor.blockSignals(False)

    def get_current_content(self, callback) -> None:
        """
        获取当前内容（即时渲染模式从 Vditor 异步取，否则从编辑器同步取）。
        用于保存等需要精确内容的场景。
        """
        if self.view_mode == "instant" and self._vditor_pane is not None:
            self._vditor_pane.get_content(callback)
        else:
            callback(self.editor.get_text())

    @property
    def vditor_pane(self) -> VditorPane | None:
        return self._vditor_pane

    def _restore_split(self) -> None:
        """恢复双栏的合理分割比例"""
        width = self._splitter.width()
        if width > 0:
            self._splitter.setSizes([int(width * 0.46), int(width * 0.54)])
        else:
            self._splitter.setSizes([480, 520])

    def is_preview_visible(self) -> bool:
        """预览面板当前是否可见"""
        if self.view_mode == "reading":
            return True
        if self.view_mode == "edit":
            return self.dual_pane
        return False  # instant 模式不显示独立预览

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
    # 最后一个标签页被关闭时发出（用于保证始终保留一个标签页）
    all_tabs_closed = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(True)
        # 超长标签右侧省略（Qt 默认中间省略，不符合阅读习惯）
        self.setElideMode(Qt.ElideRight)

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
        # 悬浮提示完整路径（标签超长被省略时可查看）
        self.setTabToolTip(idx, file_path or "未保存的文档")
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
                # 保存完成后再关闭（即时渲染模式为异步）
                self._save_pair_then_close(pair)
                return

        self._remove_pair(pair)

    def _save_pair_then_close(self, pair: EditorPreviewPair) -> None:
        """保存（必要时先选路径）并在完成后关闭标签页"""
        if not pair.file_path:
            from PyQt5.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "Markdown 文件 (*.md);;所有文件 (*)"
            )
            if not path:
                return  # 取消则不关闭
            pair.file_path = path

        pair.get_current_content(lambda content: self._finish_close(pair, content))

    def _finish_close(self, pair: EditorPreviewPair, content: str | None) -> None:
        self._write_pair(pair, content)
        self._remove_pair(pair)

    def _remove_pair(self, pair: EditorPreviewPair) -> None:
        """从标签栏移除并销毁"""
        for i in range(self.count()):
            if self.widget(i) is pair:
                self.removeTab(i)
                break
        pair.deleteLater()
        if self.count() == 0:
            self.all_tabs_closed.emit()

    def discard_pair(self, pair: EditorPreviewPair) -> None:
        """无提示移除一个标签页（用于清理未动过的空白占位页）"""
        self._remove_pair(pair)

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
            # 另存为后路径可能变化，同步悬浮提示
            self.setTabToolTip(index, pair.file_path or "未保存的文档")

    def _on_current_changed(self, index: int) -> None:
        pair = self.current_pair()
        self.current_pair_changed.emit(pair)

    def _make_title(self, file_path: str | None) -> str:
        if file_path:
            return os.path.basename(file_path)
        return "未命名"

    def _save_pair(self, pair: EditorPreviewPair) -> bool:
        """保存标签页内容到文件（即时渲染模式下异步从 Vditor 取值）"""
        if not pair.file_path:
            from PyQt5.QtWidgets import QFileDialog

            path, _ = QFileDialog.getSaveFileName(
                self, "保存文件", "", "Markdown 文件 (*.md);;所有文件 (*)"
            )
            if not path:
                return False
            pair.file_path = path

        # 取当前内容后写入（即时渲染模式为异步回调）
        pair.get_current_content(lambda content: self._write_pair(pair, content))
        return True

    def _write_pair(self, pair: EditorPreviewPair, content: str | None) -> None:
        """实际写盘并更新状态"""
        if content is None or not pair.file_path:
            return
        try:
            with open(pair.file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError:
            return
        pair.is_dirty = False
        for i in range(self.count()):
            if self.widget(i) is pair:
                self.update_title(i)
                break

    def save_current(self) -> bool:
        """保存当前标签页"""
        pair = self.current_pair()
        if pair:
            return self._save_pair(pair)
        return False
