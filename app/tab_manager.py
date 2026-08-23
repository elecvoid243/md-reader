"""
tab_manager.py — 多标签页管理

每个标签页包含一对 (MarkdownEditor, PreviewPane)。
管理文件路径、修改状态、标签切换和关闭。
"""

from __future__ import annotations

import os
import time

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QScrollBar,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .editor import MarkdownEditor
from .preview import PreviewPane
from .search_bar import EditorSearchController, SearchBar, WebSearchController
from .toc_widget import extract_headings
from .vditor_pane import VditorPane


class EditorPreviewPair(QWidget):
    """单个标签页：编辑器 + 预览的分割视图"""

    # 预览不可见时（即时渲染/单栏源码），TOC 需从源码提取更新
    headings_changed = pyqtSignal(list)
    # 脏状态翻转时发出（用于实时刷新标签标题圆点）
    dirty_changed = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.file_path: str | None = None
        self.is_dirty: bool = False
        # 最近一次「加载/保存」时的内容快照，作为内容级脏检测的基准：
        # 仅当当前文本与快照不一致时才视为有未保存更改（改回原样=干净）。
        self._saved_content: str = ""
        self.view_mode: str = "reading"  # reading / edit / instant
        self.dual_pane: bool = True  # 源码编辑模式下是否显示预览
        # 视图模式是否已真正应用过（防止 set_view_mode 的相同模式短路
        # 导致新标签页保持"编辑器+预览都可见"的初始状态）
        self._mode_applied: bool = False
        self._vditor_pane: VditorPane | None = None  # 懒加载

        # 分割器：左编辑 右预览（预览右侧挂原生滚动条，仅阅读模式显示）
        self._splitter = QSplitter()
        self.editor = MarkdownEditor()
        self.preview = PreviewPane()
        self._reading_scrollbar = QScrollBar(Qt.Vertical)
        self._reading_scrollbar.setFixedWidth(10)
        self._reading_scrollbar.hide()
        self.preview.attach_native_scrollbar(self._reading_scrollbar)

        # 编辑器面板：搜索条（默认隐藏）+ 编辑器
        self._editor_search_bar = SearchBar()
        self._editor_search = EditorSearchController(self.editor, self._editor_search_bar)
        self._editor_host = QWidget()
        editor_layout = QVBoxLayout(self._editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        editor_layout.addWidget(self._editor_search_bar)
        editor_layout.addWidget(self.editor)

        # 预览面板：搜索条（默认隐藏）+ (预览 + 原生滚动条)
        self._preview_search_bar = SearchBar()
        self._preview_search = WebSearchController(self.preview, self._preview_search_bar)
        self._preview_host = QWidget()
        preview_outer = QVBoxLayout(self._preview_host)
        preview_outer.setContentsMargins(0, 0, 0, 0)
        preview_outer.setSpacing(0)
        preview_outer.addWidget(self._preview_search_bar)
        preview_inner = QHBoxLayout()
        preview_inner.setContentsMargins(0, 0, 0, 0)
        preview_inner.setSpacing(0)
        preview_inner.addWidget(self.preview, 1)
        preview_inner.addWidget(self._reading_scrollbar)
        preview_outer.addLayout(preview_inner)

        # 即时渲染面板的搜索条（VditorPane 懒加载，控制器随之创建）
        self._vditor_search_bar = SearchBar()
        self._vditor_search: WebSearchController | None = None
        self._vditor_host: QWidget | None = None

        self._splitter.addWidget(self._editor_host)
        self._splitter.addWidget(self._preview_host)
        self._splitter.setSizes([480, 520])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)

        # 内容重渲染会清掉 Chromium 的查找高亮，渲染完成后按需重跑
        self.preview.render_finished.connect(self._preview_search.refresh)

        # 防抖定时器：编辑后延迟渲染
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._do_render)

        # Vditor → 编辑器 防抖同步定时器（Vditor 已自带 500ms 级防抖，
        # 这里只做最后一次合并，避免瞬时多次 setPlainText）
        self._vditor_sync_timer = QTimer()
        self._vditor_sync_timer.setSingleShot(True)
        self._vditor_sync_timer.timeout.connect(self._sync_vditor_to_editor)
        self._pending_vditor_text: str | None = None

        # 编辑区文本变化 → 触发防抖渲染
        self.editor.textChanged.connect(self._on_text_changed)

        # 滚动同步
        self._sync_lock = False
        # 双栏同步节流：编辑器滚轮事件频率可达每秒数十次，
        # 每次都 runJavaScript 往返会放大主线程负载，限制到 ~30Hz，
        # 被丢弃的事件在尾沿补发最后一次位置
        self._last_preview_sync = -1.0
        self._pending_preview_percent: float | None = None
        self._preview_sync_timer = QTimer()
        self._preview_sync_timer.setSingleShot(True)
        self._preview_sync_timer.setInterval(40)
        self._preview_sync_timer.timeout.connect(self._flush_pending_preview_sync)
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

    def _set_dirty(self, dirty: bool) -> None:
        """统一脏标记更新入口：仅在状态翻转时发出 dirty_changed 信号。"""
        if dirty == self.is_dirty:
            return
        self.is_dirty = dirty
        self.dirty_changed.emit(dirty)

    def _recompute_dirty(self) -> None:
        """按编辑器当前文本与已保存快照的差异更新脏标记（内容级检测）。

        先用 O(1) 的字符数比较做快速路径：大文档下每次按键都调用
        toPlainText() 做全文提取会带来可感知延迟（5MB 文档约 19ms）。
        QTextDocument 末尾隐含一个块分隔符，故字符数需减 1 对齐。
        """
        doc_len = self.editor.document().characterCount() - 1
        if doc_len != len(self._saved_content):
            self._set_dirty(True)
            return
        self._set_dirty(self.editor.get_text() != self._saved_content)

    def _on_text_changed(self) -> None:
        self._recompute_dirty()
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
            # 回声锁期间不发送，但记录最新位置，锁释放时补发
            self._pending_preview_percent = percent
            return
        now = time.monotonic()
        if (now - self._last_preview_sync) * 1000 < 33:
            self._pending_preview_percent = percent
            self._preview_sync_timer.start()
            return
        self._do_preview_sync(percent)

    def _do_preview_sync(self, percent: float) -> None:
        self._last_preview_sync = time.monotonic()
        self._sync_lock = True
        self.preview.set_scroll_percent(percent)
        QTimer.singleShot(100, self._release_sync_lock)

    def _flush_pending_preview_sync(self) -> None:
        """节流窗口结束后补发最后一次滚轮位置（尾沿更新）"""
        percent = self._pending_preview_percent
        self._pending_preview_percent = None
        if percent is not None and not self._sync_lock:
            self._do_preview_sync(percent)

    def _sync_editor_scroll(self, percent: float) -> None:
        # 阅读模式下编辑器隐藏，跳过无谓的滚动条更新，
        # 减少滚动过程中 QWebChannel 回传后的 Python/Qt 开销
        if self._sync_lock or self.view_mode == "reading":
            return
        self._sync_lock = True
        self.editor.set_scroll_percent(percent)
        QTimer.singleShot(100, self._release_sync_lock)

    def _release_sync_lock(self) -> None:
        self._sync_lock = False
        # 锁释放时补发积压的最新预览位置（编辑器滚动持续时保持跟踪）
        percent = self._pending_preview_percent
        self._pending_preview_percent = None
        if percent is not None:
            now = time.monotonic()
            if (now - self._last_preview_sync) * 1000 < 33:
                self._preview_sync_timer.start()
            else:
                self._do_preview_sync(percent)

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
        if md is not None and self.is_dirty:
            # 干净状态跳过回写：Vditor 的 getValue() 会对 Markdown 做归一化
            # （表格分隔符、代码块空行等），回写会污染编辑器并触发
            # _recompute_dirty 把归一化差异误判为未保存更改
            self.editor.set_text(md)
        self._apply_mode(mode, dual_pane)

    def _apply_mode(self, mode: str, dual_pane: bool) -> None:
        """实际应用模式：控制三个面板的显隐 + 浮动控件"""
        # 切换模式时面板显隐变化、内容重渲染，关闭所有搜索状态
        self.close_searches()
        self.view_mode = mode
        self.dual_pane = dual_pane
        self._mode_applied = True

        # 浮动单/双栏控件仅在源码编辑模式显示
        show_pane = mode == "edit"
        self._pane_toggle.setVisible(show_pane)

        if mode == "reading":
            # 阅读模式：仅预览，全宽；网页滚动条隐藏，由右侧原生滚动条代理
            # 注意显隐控制的是 splitter 的子项 host 容器：只隐藏内部控件
            # 会让空 host 留在分割器里，出现半屏空白和可拖动的分割条
            self._hide_vditor()
            self._editor_host.hide()
            self._preview_host.show()
            self._reading_scrollbar.hide()
            self.preview.set_native_scroll_proxy_enabled(True)
            self.render_now()
        elif mode == "edit":
            # 源码编辑：编辑器可见，预览按 dual_pane 决定
            self._hide_vditor()
            self._editor_host.show()
            if dual_pane:
                self._preview_host.show()
                self._reading_scrollbar.hide()
                self.preview.set_native_scroll_proxy_enabled(False)
                self._restore_split()
                self.render_now()
            else:
                self._preview_host.hide()
                self._reading_scrollbar.hide()
                self.preview.set_native_scroll_proxy_enabled(False)
            # 同步浮动按钮选中态并定位
            self._btn_dual.setChecked(dual_pane)
            self._btn_single.setChecked(not dual_pane)
            self._reposition_pane_toggle()
        elif mode == "instant":
            # 即时渲染：仅 Vditor，把编辑器内容推入
            self._editor_host.hide()
            self._preview_host.hide()
            self._reading_scrollbar.hide()
            self.preview.set_native_scroll_proxy_enabled(False)
            self._ensure_vditor()
            self._vditor_host.show()
            self._vditor_pane.show()
            self._vditor_pane.set_content(self.editor.get_text())

    def _ensure_vditor(self) -> None:
        """懒加载创建 VditorPane（首次进入即时渲染时）"""
        if self._vditor_pane is None:
            self._vditor_pane = VditorPane()
            self._vditor_search = WebSearchController(
                self._vditor_pane, self._vditor_search_bar
            )
            self._vditor_host = QWidget()
            host_layout = QVBoxLayout(self._vditor_host)
            host_layout.setContentsMargins(0, 0, 0, 0)
            host_layout.setSpacing(0)
            host_layout.addWidget(self._vditor_search_bar)
            host_layout.addWidget(self._vditor_pane)
            self._splitter.addWidget(self._vditor_host)
            self._vditor_pane.input_changed.connect(self._on_vditor_input)

            # IR 内容重绘是异步的，输入停顿后重跑搜索恢复高亮
            self._vditor_search_timer = QTimer()
            self._vditor_search_timer.setSingleShot(True)
            self._vditor_search_timer.setInterval(400)
            self._vditor_search_timer.timeout.connect(
                lambda: self._vditor_search.refresh() if self._vditor_search else None
            )
            self._vditor_pane.input_changed.connect(
                lambda _t: self._vditor_search_timer.start()
                if self._vditor_search_bar.is_open()
                else None
            )

    def _hide_vditor(self) -> None:
        self._vditor_sync_timer.stop()
        self._pending_vditor_text = None
        if self._vditor_host is not None:
            self._vditor_host.hide()
        if self._vditor_pane is not None:
            self._vditor_pane.hide()

    def _on_vditor_input(self, text: str) -> None:
        """Vditor 中用户输入 → 内容级标记脏状态 + 缓存最新 Markdown"""
        # 直接与快照比较：避免进入即时渲染时 set_content 触发的回显被误判为修改
        self._set_dirty(text != self._saved_content)
        self._pending_vditor_text = text
        # 只做本地合并，不再从这里发起第二次 getVditorContent()
        self._vditor_sync_timer.start(150)

    def _sync_vditor_to_editor(self) -> None:
        """把 Vditor 最近一次 input 回调给出的 Markdown 同步回编辑器"""
        if self._vditor_pane is None or self.view_mode != "instant":
            return
        text = self._pending_vditor_text
        self._pending_vditor_text = None
        if text is not None:
            self._apply_vditor_content(text)

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

    # ──────────────────────────────────────────
    #  面板搜索（阅读 = 预览；即时渲染 = Vditor；源码编辑 = 编辑器/预览双栏）
    # ──────────────────────────────────────────

    def open_search(self, kind: str) -> None:
        """打开指定面板的搜索条；目标面板不可见时回退到编辑器"""
        if kind == "preview" and not self.is_preview_visible():
            kind = "editor"
        if kind == "vditor" and self._vditor_pane is None:
            kind = "editor"

        if kind == "preview":
            self._preview_search.refresh()
            self._preview_search_bar.open_bar()
        elif kind == "vditor":
            if self._vditor_search is not None:
                self._vditor_search.refresh()
            self._vditor_search_bar.open_bar()
        else:
            self._editor_search.refresh()
            self._editor_search_bar.open_bar()

    def step_search(self, forward: bool) -> None:
        """在当前打开的搜索条中跳到上/下一个匹配"""
        for bar, ctrl in (
            (self._editor_search_bar, self._editor_search),
            (self._preview_search_bar, self._preview_search),
            (self._vditor_search_bar, self._vditor_search),
        ):
            if bar.is_open() and ctrl is not None:
                ctrl.step(forward)

    def close_searches(self) -> None:
        """关闭全部搜索条并清除高亮"""
        for bar in (
            self._editor_search_bar,
            self._preview_search_bar,
            self._vditor_search_bar,
        ):
            bar.close_bar()

    def set_search_icons(self, search_icon, prev_icon, next_icon, close_icon) -> None:
        """设置搜索条图标（随主题刷新）"""
        for bar in (
            self._editor_search_bar,
            self._preview_search_bar,
            self._vditor_search_bar,
        ):
            bar.set_icons(search_icon, prev_icon, next_icon, close_icon)

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
        # 脏状态翻转 → 实时刷新标签标题（● 前缀）
        pair.dirty_changed.connect(lambda _dirty, p=pair: self._on_pair_dirty_changed(p))

        if content:
            # 先记录快照再填充编辑器：set_text 触发 textChanged → _recompute_dirty，
            # 快照已就位时比较结果即为「干净」，下方再显式清零以双保险。
            pair._saved_content = content
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

    def _on_pair_dirty_changed(self, pair: EditorPreviewPair) -> None:
        """脏状态翻转 → 实时刷新标签标题（● 前缀）"""
        for i in range(self.count()):
            if self.widget(i) is pair:
                self.update_title(i)
                break

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
        # 写盘成功后同步快照，作为后续内容级脏检测的基准
        pair._saved_content = content
        pair._set_dirty(False)
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
