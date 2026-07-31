"""
main_window.py — 主窗口

组装所有组件：菜单栏、工具栏、文件树、标签页、TOC 导航、状态栏。
处理文件打开/保存、主题切换、快捷键等全局操作。
"""

from __future__ import annotations

import os

from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStatusBar,
    QToolBar,
    QToolButton,
    QWidget,
)

from .config import Config
from .exporter import export_html, export_pdf
from .file_tree import FileTreeWidget
from .icons import build_icons
from .tab_manager import EditorPreviewPair, TabManager
from .theme_manager import ThemeManager
from .toc_widget import TocWidget

# 支持的文件扩展名
_MD_EXTENSIONS = {".md", ".markdown", ".mdown", ".txt"}

# 文件编码探测顺序
_ENCODINGS = ["utf-8", "utf-8-sig", "gbk", "gb2312", "gb18030", "latin-1"]


class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self) -> None:
        super().__init__()

        self._config = Config()
        self._theme_mgr = ThemeManager()

        # 视图模式状态（阅读/编辑 + 双栏）
        self._view_mode: str = self._config.get("view_mode", "reading")
        self._dual_pane: bool = self._config.get("dual_pane", True)

        self._setup_window()
        self._setup_components()
        self._setup_menu()
        self._init_icons()  # 菜单 action 创建后生成图标，供工具栏/菜单使用
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()

        # 应用保存的主题
        app = QApplication.instance()
        if app:
            self._theme_mgr.apply_theme(self._theme_mgr.current_theme, app)
            self._apply_editor_theme()

        # 始终保留一个标签页：启动即打开空白的「未命名」页，
        # 用户直接编辑后保存时会走"另存为"流程创建新文件
        self._new_tab()

    # ──────────────────────────────────────────
    #  窗口基础设置
    # ──────────────────────────────────────────

    def _setup_window(self) -> None:
        self.setWindowTitle("MD Reader — Markdown 阅读器")
        self.resize(
            self._config.get("window_width", 1280),
            self._config.get("window_height", 800),
        )
        self.move(
            self._config.get("window_x", 100),
            self._config.get("window_y", 100),
        )
        # 允许拖放文件到窗口
        self.setAcceptDrops(True)

    # ──────────────────────────────────────────
    #  组件布局
    # ──────────────────────────────────────────

    def _setup_components(self) -> None:
        # 中心区域：标签页管理器
        self._tabs = TabManager()
        self.setCentralWidget(self._tabs)

        # 左侧停靠：TOC 导航（布局固定，仅允许左侧）
        self._toc = TocWidget()
        self._toc_dock = QDockWidget("目录导航", self)
        self._toc_dock.setWidget(self._toc)
        self._toc_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._toc_dock)

        # 右侧停靠：文件树（布局固定，仅允许右侧）
        self._file_tree = FileTreeWidget()
        self._file_dock = QDockWidget("文件浏览器", self)
        self._file_dock.setWidget(self._file_tree)
        self._file_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self._file_dock)

        # 恢复侧边栏可见性
        self._file_dock.setVisible(self._config.get("show_file_tree", True))
        self._toc_dock.setVisible(self._config.get("show_toc", True))

        # 恢复上次打开的文件夹
        last_folder = self._config.get("last_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self._file_tree.set_root_path(last_folder)

    # ──────────────────────────────────────────
    #  菜单栏
    # ──────────────────────────────────────────

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # ── 文件菜单 ──
        file_menu = menubar.addMenu("文件(&F)")

        self._act_open = QAction("打开文件(&O)...", self)
        self._act_open.setShortcut(QKeySequence.Open)
        self._act_open.triggered.connect(self._open_file_dialog)
        file_menu.addAction(self._act_open)

        self._act_open_folder = QAction("打开文件夹(&F)...", self)
        self._act_open_folder.setShortcut("Ctrl+Shift+O")
        self._act_open_folder.triggered.connect(self._open_folder_dialog)
        file_menu.addAction(self._act_open_folder)

        file_menu.addSeparator()

        self._act_save = QAction("保存(&S)", self)
        self._act_save.setShortcut(QKeySequence.Save)
        self._act_save.triggered.connect(self._save_file)
        file_menu.addAction(self._act_save)

        self._act_save_as = QAction("另存为(&A)...", self)
        self._act_save_as.setShortcut("Ctrl+Shift+S")
        self._act_save_as.triggered.connect(self._save_file_as)
        file_menu.addAction(self._act_save_as)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("导出(&E)")

        self._act_export_html = QAction("导出为 HTML...", self)
        self._act_export_html.triggered.connect(self._export_html)
        export_menu.addAction(self._act_export_html)

        self._act_export_pdf = QAction("导出为 PDF...", self)
        self._act_export_pdf.triggered.connect(self._export_pdf)
        export_menu.addAction(self._act_export_pdf)

        file_menu.addSeparator()

        self._act_new_tab = QAction("新建标签页(&N)", self)
        self._act_new_tab.setShortcut(QKeySequence.New)
        self._act_new_tab.triggered.connect(self._new_tab)
        file_menu.addAction(self._act_new_tab)

        self._act_close_tab = QAction("关闭标签页(&W)", self)
        self._act_close_tab.setShortcut(QKeySequence("Ctrl+W"))
        self._act_close_tab.triggered.connect(self._close_current_tab)
        file_menu.addAction(self._act_close_tab)

        file_menu.addSeparator()

        self._act_exit = QAction("退出(&X)", self)
        self._act_exit.setShortcut("Alt+F4")
        self._act_exit.triggered.connect(self.close)
        file_menu.addAction(self._act_exit)

        # ── 视图菜单 ──
        view_menu = menubar.addMenu("视图(&V)")

        # 三种互斥的视图模式
        self._mode_group = QActionGroup(self)
        self._mode_group.setExclusive(True)

        self._act_mode_reading = QAction("阅读模式", self)
        self._act_mode_reading.setCheckable(True)
        self._act_mode_reading.setChecked(self._view_mode == "reading")
        self._act_mode_reading.setShortcut("Ctrl+Shift+R")
        self._act_mode_reading.setStatusTip("仅显示渲染结果（只读）")
        self._act_mode_reading.triggered.connect(lambda: self._set_mode("reading"))
        self._mode_group.addAction(self._act_mode_reading)
        view_menu.addAction(self._act_mode_reading)

        self._act_mode_instant = QAction("即时渲染", self)
        self._act_mode_instant.setCheckable(True)
        self._act_mode_instant.setChecked(self._view_mode == "instant")
        self._act_mode_instant.setShortcut("Ctrl+Shift+I")
        self._act_mode_instant.setStatusTip("在渲染视图中直接编辑（Typora 式）")
        self._act_mode_instant.triggered.connect(lambda: self._set_mode("instant"))
        self._mode_group.addAction(self._act_mode_instant)
        view_menu.addAction(self._act_mode_instant)

        self._act_mode_source = QAction("源码编辑", self)
        self._act_mode_source.setCheckable(True)
        self._act_mode_source.setChecked(self._view_mode == "edit")
        self._act_mode_source.setShortcut("Ctrl+Shift+M")
        self._act_mode_source.setStatusTip("编辑 Markdown 源码（可双栏预览）")
        self._act_mode_source.triggered.connect(lambda: self._set_mode("edit"))
        self._mode_group.addAction(self._act_mode_source)
        view_menu.addAction(self._act_mode_source)

        self._act_dual_pane = QAction("双栏预览", self)
        self._act_dual_pane.setCheckable(True)
        self._act_dual_pane.setChecked(self._dual_pane)
        self._act_dual_pane.setShortcut("Ctrl+Shift+P")
        self._act_dual_pane.setStatusTip("源码编辑模式下同时显示预览")
        self._act_dual_pane.setEnabled(self._view_mode == "edit")
        self._act_dual_pane.toggled.connect(self._on_dual_pane_toggled)
        view_menu.addAction(self._act_dual_pane)

        view_menu.addSeparator()

        self._act_toggle_file_tree = QAction("文件浏览器", self)
        self._act_toggle_file_tree.setCheckable(True)
        self._act_toggle_file_tree.setChecked(self._config.get("show_file_tree", True))
        self._act_toggle_file_tree.setShortcut("Ctrl+Shift+E")
        self._act_toggle_file_tree.toggled.connect(self._toggle_file_tree)
        view_menu.addAction(self._act_toggle_file_tree)

        self._act_toggle_toc = QAction("目录导航", self)
        self._act_toggle_toc.setCheckable(True)
        self._act_toggle_toc.setChecked(self._config.get("show_toc", True))
        self._act_toggle_toc.setShortcut("Ctrl+Shift+T")
        self._act_toggle_toc.toggled.connect(self._toggle_toc)
        view_menu.addAction(self._act_toggle_toc)

        view_menu.addSeparator()

        self._act_toggle_theme = QAction("切换深色/浅色主题", self)
        self._act_toggle_theme.setShortcut("Ctrl+Shift+D")
        self._act_toggle_theme.triggered.connect(self._toggle_theme)
        view_menu.addAction(self._act_toggle_theme)

        view_menu.addSeparator()

        self._act_scroll_sync = QAction("滚动同步", self)
        self._act_scroll_sync.setCheckable(True)
        self._act_scroll_sync.setChecked(self._config.get("scroll_sync", True))
        self._act_scroll_sync.toggled.connect(self._toggle_scroll_sync)
        view_menu.addAction(self._act_scroll_sync)

        # ── 帮助菜单 ──
        help_menu = menubar.addMenu("帮助(&H)")

        self._act_about = QAction("关于(&A)...", self)
        self._act_about.triggered.connect(self._show_about)
        help_menu.addAction(self._act_about)

    # ──────────────────────────────────────────
    #  工具栏
    # ──────────────────────────────────────────

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)

        # 左侧：常用操作（打开/保存/导出/主题），图标经 defaultAction 共享
        for act in (
            self._act_open,
            self._act_save,
            self._act_export_pdf,
            self._act_toggle_theme,
        ):
            toolbar.addAction(act)

        # 弹簧：把模式胶囊推到右侧
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # 右侧：模式切换分段控件
        toolbar.addWidget(self._build_mode_segment())

    def _init_icons(self) -> None:
        """生成图标并绑定到菜单 action（工具栏按钮经 defaultAction 共享）"""
        self._icons = build_icons(self._theme_mgr.palette)
        self._action_icon = {
            self._act_mode_reading: "reading",
            self._act_mode_instant: "instant",
            self._act_mode_source: "source",
            self._act_dual_pane: "pane_dual",
            self._act_open: "open",
            self._act_save: "save",
            self._act_export_pdf: "export",
            self._act_toggle_theme: "theme",
        }
        # 纯图标按钮的悬浮提示
        self._act_mode_reading.setToolTip("阅读模式 (Ctrl+Shift+R)")
        self._act_mode_instant.setToolTip("即时渲染 (Ctrl+Shift+I)")
        self._act_mode_source.setToolTip("源码编辑 (Ctrl+Shift+M)")
        self._act_dual_pane.setToolTip("双栏预览 (Ctrl+Shift+P)")
        self._act_open.setToolTip("打开文件 (Ctrl+O)")
        self._act_save.setToolTip("保存 (Ctrl+S)")
        self._act_export_pdf.setToolTip("导出为 PDF")
        self._act_toggle_theme.setToolTip("切换深色/浅色主题 (Ctrl+Shift+D)")
        self._apply_action_icons()

    def _apply_action_icons(self) -> None:
        for act, name in self._action_icon.items():
            act.setIcon(self._icons[name])

    def _refresh_icons(self) -> None:
        """主题切换后重建全部图标（含浮动控件）"""
        self._icons = build_icons(self._theme_mgr.palette)
        self._apply_action_icons()
        for i in range(self._tabs.count()):
            pair = self._tabs.widget(i)
            if isinstance(pair, EditorPreviewPair):
                pair.set_pane_icons(
                    self._icons["pane_single"], self._icons["pane_dual"]
                )

    def _build_mode_segment(self) -> QWidget:
        """构建模式切换分段控件（纯图标 + 胶囊槽）"""
        seg = QWidget()
        seg.setObjectName("mode_seg")
        lay = QHBoxLayout(seg)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)

        specs = [
            (self._act_mode_reading, "tb_mode_reading"),
            (self._act_mode_instant, "tb_mode_instant"),
            (self._act_mode_source, "tb_mode_source"),
        ]
        for act, obj_name in specs:
            tb = QToolButton()
            tb.setObjectName(obj_name)
            tb.setDefaultAction(act)
            tb.setAutoRaise(True)
            tb.setIconSize(QSize(18, 18))
            tb.setToolButtonStyle(Qt.ToolButtonIconOnly)
            lay.addWidget(tb)
        return seg

    def _request_dual_pane(self, checked: bool) -> None:
        """浮动控件点击 → 驱动全局双栏 action（单一真相源）"""
        self._act_dual_pane.setChecked(checked)

    # ──────────────────────────────────────────
    #  状态栏
    # ──────────────────────────────────────────

    def _setup_statusbar(self) -> None:
        self._status_file = QLabel("就绪")
        self._status_cursor = QLabel("")
        self._status_encoding = QLabel("UTF-8")

        statusbar = QStatusBar()
        statusbar.addWidget(self._status_file, 1)
        statusbar.addPermanentWidget(self._status_cursor)
        statusbar.addPermanentWidget(self._status_encoding)
        self.setStatusBar(statusbar)

    # ──────────────────────────────────────────
    #  信号连接
    # ──────────────────────────────────────────

    def _connect_signals(self) -> None:
        # 文件树 → 打开文件
        self._file_tree.file_opened.connect(self.open_file)

        # 标签页切换 → 更新 TOC / 状态栏
        self._tabs.current_pair_changed.connect(self._on_pair_changed)

        # 最后一个标签页关闭后 → 自动补一个空白占位页
        self._tabs.all_tabs_closed.connect(self._new_tab)

        # TOC 点击 → 预览滚动 + 编辑器跳转
        self._toc.heading_clicked.connect(self._on_heading_clicked)

    # ──────────────────────────────────────────
    #  文件操作
    # ──────────────────────────────────────────

    def open_file(self, file_path: str) -> None:
        """打开一个 Markdown 文件"""
        abs_path = os.path.abspath(file_path)

        # 如果已在标签页中打开，直接切换
        if self._tabs.switch_to_path(abs_path):
            return

        # 读取文件（多编码探测）
        content, encoding = self._read_file(abs_path)
        if content is None:
            QMessageBox.warning(self, "打开失败", f"无法读取文件：\n{abs_path}")
            return

        # 新建标签页
        pair = self._tabs.add_tab(file_path=abs_path, content=content)

        # 清理未动过的空白占位页（启动时自动创建的"未命名"）
        self._drop_placeholder_tab(except_pair=pair)

        # 连接 TOC 信号
        pair.preview.toc_updated.connect(self._toc.update_toc)

        # 应用当前视图模式（默认阅读模式）
        self._apply_view_mode_to_pair(pair)

        # 更新状态栏
        self._status_file.setText(abs_path)
        self._status_encoding.setText(encoding)

        # 更新窗口标题
        self.setWindowTitle(f"{os.path.basename(abs_path)} — MD Reader")

        # 记录最后打开的文件夹
        folder = os.path.dirname(abs_path)
        self._config.set("last_folder", folder)

    def _read_file(self, path: str) -> tuple[str | None, str]:
        """多编码探测读取文件"""
        for enc in _ENCODINGS:
            try:
                with open(path, encoding=enc) as f:
                    content = f.read()
                return content, enc.upper()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except OSError:
                return None, ""
        return None, ""

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开 Markdown 文件",
            self._config.get("last_folder", ""),
            "Markdown 文件 (*.md *.markdown *.mdown);;文本文件 (*.txt);;所有文件 (*)",
        )
        if path:
            self.open_file(path)

    def _open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "打开文件夹", self._config.get("last_folder", "")
        )
        if folder:
            self._file_tree.set_root_path(folder)
            self._config.set("last_folder", folder)
            if not self._file_dock.isVisible():
                self._file_dock.setVisible(True)
                self._act_toggle_file_tree.setChecked(True)

    def _save_file(self) -> None:
        self._tabs.save_current()

    def _save_file_as(self) -> None:
        pair = self._tabs.current_pair()
        if not pair:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为", "", "Markdown 文件 (*.md);;所有文件 (*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(pair.editor.get_text())
                pair.file_path = path
                pair.is_dirty = False
                self._tabs.update_title(self._tabs.currentIndex())
                self._status_file.setText(path)
            except OSError as e:
                QMessageBox.warning(self, "保存失败", str(e))

    def _new_tab(self) -> None:
        pair = self._tabs.add_tab()
        pair.preview.toc_updated.connect(self._toc.update_toc)
        self._apply_view_mode_to_pair(pair)

    @staticmethod
    def _is_placeholder(pair) -> bool:
        """未命名、未修改且内容为空的占位标签页"""
        return (
            pair.file_path is None
            and not pair.is_dirty
            and not pair.editor.get_text().strip()
        )

    def _drop_placeholder_tab(self, except_pair) -> None:
        """清理除 except_pair 外的第一个空白占位页"""
        for i in range(self._tabs.count()):
            widget = self._tabs.widget(i)
            if (
                isinstance(widget, EditorPreviewPair)
                and widget is not except_pair
                and self._is_placeholder(widget)
            ):
                self._tabs.discard_pair(widget)
                return

    def _close_current_tab(self) -> None:
        idx = self._tabs.currentIndex()
        if idx >= 0:
            self._tabs.close_tab(idx)

    # ──────────────────────────────────────────
    #  导出
    # ──────────────────────────────────────────

    def _export_html(self) -> None:
        pair = self._tabs.current_pair()
        if pair:
            export_html(pair.preview, self)

    def _export_pdf(self) -> None:
        pair = self._tabs.current_pair()
        if pair:
            export_pdf(pair.preview, self)

    # ──────────────────────────────────────────
    #  视图切换
    # ──────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        """切换视图模式（阅读 / 即时渲染 / 源码编辑）"""
        self._view_mode = mode
        self._config.set("view_mode", mode)
        # 显式同步分段控件选中态（QActionGroup exclusive 会自动取消其余），
        # 保证菜单/工具栏/快捷键/程序化调用四种入口的 UI 表征一致
        {
            "reading": self._act_mode_reading,
            "instant": self._act_mode_instant,
            "edit": self._act_mode_source,
        }[mode].setChecked(True)
        # 双栏开关仅在源码编辑模式下有意义
        self._act_dual_pane.setEnabled(mode == "edit")
        self._apply_view_mode()
        names = {"reading": "阅读模式", "instant": "即时渲染", "edit": "源码编辑"}
        self.statusBar().showMessage(names.get(mode, mode), 2500)

    def _on_dual_pane_toggled(self, checked: bool) -> None:
        """源码编辑模式下双栏预览开关"""
        self._dual_pane = checked
        self._config.set("dual_pane", checked)
        self._apply_view_mode()

    def _apply_view_mode(self) -> None:
        """将当前视图模式应用到所有标签页"""
        theme_name = self._theme_mgr.current_theme
        for i in range(self._tabs.count()):
            pair = self._tabs.widget(i)
            if isinstance(pair, EditorPreviewPair):
                pair.set_view_mode(self._view_mode, self._dual_pane)
                # 同步 Vditor 主题（若已创建）
                if pair.vditor_pane is not None:
                    pair.vditor_pane.set_theme(theme_name)
        # 预览可见时确保当前内容为最新渲染
        pair = self._tabs.current_pair()
        if pair and pair.is_preview_visible():
            pair.render_now()

    def _apply_view_mode_to_pair(self, pair: EditorPreviewPair) -> None:
        """将当前视图模式应用到单个新建标签页"""
        pair.set_view_mode(self._view_mode, self._dual_pane)
        pair.set_dual_pane_callback(self._request_dual_pane)
        pair.set_pane_icons(self._icons["pane_single"], self._icons["pane_dual"])
        if pair.vditor_pane is not None:
            pair.vditor_pane.set_theme(self._theme_mgr.current_theme)

    def _toggle_file_tree(self, visible: bool) -> None:
        self._file_dock.setVisible(visible)
        self._config.set("show_file_tree", visible)

    def _toggle_toc(self, visible: bool) -> None:
        self._toc_dock.setVisible(visible)
        self._config.set("show_toc", visible)

    def _toggle_theme(self) -> None:
        app = QApplication.instance()
        if app:
            new_theme = self._theme_mgr.toggle(app)
            self._apply_editor_theme()
            self._refresh_icons()  # 图标颜色随主题重建
            # 通知所有预览面板切换主题
            for i in range(self._tabs.count()):
                pair = self._tabs.widget(i)
                if isinstance(pair, EditorPreviewPair):
                    pair.preview.set_theme(new_theme)
            self._status_file.setText(f"主题: {new_theme}")

    def _apply_editor_theme(self) -> None:
        """将主题样式应用到所有编辑器（QSS + 绘制配色 + Vditor）"""
        style = self._theme_mgr.get_editor_style()
        colors = self._theme_mgr.get_editor_colors()
        theme_name = self._theme_mgr.current_theme
        for i in range(self._tabs.count()):
            pair = self._tabs.widget(i)
            if isinstance(pair, EditorPreviewPair):
                pair.editor.setStyleSheet(style)
                pair.editor.set_theme_colors(colors)
                if pair.vditor_pane is not None:
                    pair.vditor_pane.set_theme(theme_name)

    def _toggle_scroll_sync(self, enabled: bool) -> None:
        self._config.set("scroll_sync", enabled)
        for i in range(self._tabs.count()):
            pair = self._tabs.widget(i)
            if isinstance(pair, EditorPreviewPair):
                pair.set_scroll_sync_enabled(enabled)

    # ──────────────────────────────────────────
    #  标签页 / TOC 联动
    # ──────────────────────────────────────────

    def _on_pair_changed(self, pair) -> None:
        """标签页切换时更新关联组件"""
        if pair is None:
            self._toc.clear_toc()
            self._status_file.setText("就绪")
            self.setWindowTitle("MD Reader — Markdown 阅读器")
            return

        # 重新连接 TOC（断开旧的，连接新的）
        try:
            pair.preview.toc_updated.disconnect(self._toc.update_toc)
        except TypeError:
            pass
        pair.preview.toc_updated.connect(self._toc.update_toc)

        # 触发一次渲染以刷新 TOC
        pair.render_now()

        # 更新状态栏
        if pair.file_path:
            self._status_file.setText(pair.file_path)
            self.setWindowTitle(f"{os.path.basename(pair.file_path)} — MD Reader")
        else:
            self._status_file.setText("未保存的文档")
            self.setWindowTitle("未命名 — MD Reader")

        # 应用编辑器主题（QSS + 绘制配色）
        pair.editor.setStyleSheet(self._theme_mgr.get_editor_style())
        pair.editor.set_theme_colors(self._theme_mgr.get_editor_colors())

    def _on_heading_clicked(self, heading_id: str, level: int) -> None:
        """TOC 标题被点击"""
        pair = self._tabs.current_pair()
        if not pair:
            return

        # 预览区滚动到标题
        pair.preview.scroll_to_heading(heading_id)

        # 编辑器跳转到对应行（通过搜索标题文本）
        # 简单实现：搜索以 # 开头的匹配行
        text = pair.editor.get_text()
        lines = text.split("\n")
        target_prefix = "#" * level + " "
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(target_prefix):
                # 简单匹配：生成 id 比较
                heading_text = stripped[len(target_prefix) :].strip()
                generated_id = self._make_heading_id(heading_text)
                if generated_id == heading_id:
                    pair.editor.goto_line(i + 1)
                    break

    @staticmethod
    def _make_heading_id(text: str) -> str:
        """模拟 JS 端的标题 id 生成逻辑"""
        import re

        hid = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.lower())
        hid = hid.strip("-")
        return hid or "heading"

    # ──────────────────────────────────────────
    #  拖放支持
    # ──────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in _MD_EXTENSIONS:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            ext = os.path.splitext(path)[1].lower()
            if ext in _MD_EXTENSIONS:
                self.open_file(path)

    # ──────────────────────────────────────────
    #  关闭事件
    # ──────────────────────────────────────────

    def closeEvent(self, event) -> None:  # noqa: N802
        # 保存窗口几何
        geo = self.geometry()
        self._config.set("window_width", geo.width())
        self._config.set("window_height", geo.height())
        self._config.set("window_x", geo.x())
        self._config.set("window_y", geo.y())
        self._config.save()

        # 检查未保存的标签页
        for i in range(self._tabs.count()):
            pair = self._tabs.widget(i)
            if isinstance(pair, EditorPreviewPair) and pair.is_dirty:
                reply = QMessageBox.question(
                    self,
                    "退出确认",
                    "有未保存的更改，确定要退出吗？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return
                break

        event.accept()

    # ──────────────────────────────────────────
    #  关于对话框
    # ──────────────────────────────────────────

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于 MD Reader",
            "<h3>MD Reader</h3>"
            "<p>一款基于 PyQt5 的 Markdown 阅读器 / 编辑器</p>"
            "<p>功能特性：</p>"
            "<ul>"
            "<li>双栏编辑 + 实时预览</li>"
            "<li>LaTeX 公式渲染 (KaTeX)</li>"
            "<li>Mermaid 图表渲染</li>"
            "<li>代码语法高亮</li>"
            "<li>文件树浏览 / TOC 导航</li>"
            "<li>多标签页 / 深色模式</li>"
            "<li>导出 HTML / PDF</li>"
            "</ul>"
            "<p>技术栈：PyQt5 + QWebEngineView + marked.js + KaTeX + mermaid.js</p>"
            "<p>兼容 Windows 7+</p>",
        )
