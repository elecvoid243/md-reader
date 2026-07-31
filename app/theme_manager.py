"""
theme_manager.py — 主题管理（「墨与纸 · 昼」设计系统，固定浅色）

以调色板 (palette) 为单一数据源，统一驱动：
- 主窗口 QSS 样式表（菜单栏/工具栏/标签页/停靠栏/状态栏）
- 编辑器配色（背景/行号栏/当前行/选区/光标）
- 预览区 CSS 主题（固定 theme-light.css）

调色板与 resources/css/theme-light.css 保持同一设计语言。
（2026-07-31 起移除深色模式，应用固定为浅色主题）
"""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication

# ══════════════════════════════════════════════
#  调色板定义（与 CSS 主题同源）
# ══════════════════════════════════════════════

LIGHT_PALETTE = {
    # 应用外壳
    "chrome": "#e9e6de",  # 窗口/工具栏底色
    "chrome_alt": "#e2ded4",  # 次级区域
    "surface": "#fcfbf7",  # 面板/纸面
    "inset": "#f3f0e8",  # 内嵌区域
    # 文本
    "ink": "#2b2822",
    "ink_strong": "#1c1a15",
    "ink_muted": "#7d7668",
    "ink_faint": "#b0a896",
    # 主色
    "accent": "#0e6b5a",
    "accent_strong": "#0a5546",
    "accent_soft": "#dcebe5",
    "amber": "#b8862b",
    # 线条
    "border": "#d8d2c2",
    "border_strong": "#c9c2ae",
    "hairline": "#e8e3d6",
    # 交互
    "hover": "#efebdf",
    "pressed": "#e4dfd0",
    "selection": "#cfe4db",
    # 编辑器
    "editor_bg": "#fcfbf7",
    "gutter_bg": "#f3f0e6",
    "gutter_ink": "#b3ab96",
    "current_line": "#f4f1e6",
    "caret": "#0e6b5a",
    # 滚动条
    "scrollbar": "#cbc4b2",
    "scrollbar_hov": "#b3ab96",
}

def _build_qss(p: dict) -> str:
    """由调色板生成整窗 QSS 样式表"""
    return f"""
/* ═══ 全局 ═══ */
QMainWindow, QDialog {{
    background-color: {p["chrome"]};
    color: {p["ink"]};
}}
QWidget {{
    color: {p["ink"]};
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}}

/* ═══ 菜单栏 ═══ */
QMenuBar {{
    background-color: {p["chrome"]};
    color: {p["ink_muted"]};
    border-bottom: 1px solid {p["border"]};
    padding: 2px;
    font-size: 13px;
}}
QMenuBar::item {{
    padding: 5px 10px;
    border-radius: 5px;
    background: transparent;
}}
QMenuBar::item:selected {{
    background-color: {p["hover"]};
    color: {p["ink_strong"]};
}}
QMenuBar::item:pressed {{
    background-color: {p["pressed"]};
}}
QMenu {{
    background-color: {p["surface"]};
    color: {p["ink"]};
    border: 1px solid {p["border"]};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{
    padding: 7px 28px 7px 24px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background-color: {p["accent_soft"]};
    color: {p["accent_strong"]};
}}
QMenu::separator {{
    height: 1px;
    background: {p["hairline"]};
    margin: 5px 12px;
}}
QMenu::indicator {{
    width: 14px;
    height: 14px;
    margin-left: 6px;
}}
QMenu::indicator:checked {{
    background: {p["accent"]};
    border-radius: 3px;
}}

/* ═══ 工具栏 ═══ */
QToolBar {{
    background-color: {p["chrome"]};
    border: none;
    border-bottom: 1px solid {p["border"]};
    spacing: 3px;
    padding: 2px 10px;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 3px 7px;
    color: {p["ink_muted"]};
    font-size: 13px;
}}
QToolButton:hover {{
    background-color: {p["hover"]};
    color: {p["ink_strong"]};
}}
QToolButton:pressed {{
    background-color: {p["pressed"]};
}}

/* ═══ 标签页（现代下划线风格） ═══ */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {p["border"]};
    background-color: {p["chrome_alt"]};
}}
QTabBar {{
    background-color: {p["chrome"]};
    qproperty-drawBase: 0;
}}
QTabBar::tab {{
    background: transparent;
    color: {p["ink_faint"]};
    padding: 9px 20px 8px;
    border: none;
    border-right: 1px solid {p["border"]};
    border-bottom: 2px solid transparent;
    font-size: 13px;
    min-width: 90px;
}}
QTabBar::tab:hover {{
    color: {p["ink_muted"]};
    background-color: {p["hover"]};
}}
QTabBar::tab:selected {{
    color: {p["ink_strong"]};
    border-bottom: 2px solid {p["accent"]};
    background: transparent;
    font-weight: 600;
}}
QTabBar::close-button {{
    border-radius: 4px;
    padding: 2px;
}}
QTabBar::close-button:hover {{
    background-color: {p["pressed"]};
}}

/* ═══ 停靠栏（文件树 / TOC） ═══ */
QDockWidget {{
    color: {p["ink_muted"]};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
    font-size: 12px;
}}
QDockWidget::title {{
    background-color: {p["chrome"]};
    color: {p["ink_muted"]};
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid {p["border"]};
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-size: 11px;
}}
QDockWidget::close-button, QDockWidget::float-button {{
    background: transparent;
    border: none;
    padding: 2px;
}}
QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
    background-color: {p["hover"]};
    border-radius: 4px;
}}

/* ═══ 树视图 ═══ */
QTreeView, QTreeWidget {{
    background-color: {p["surface"]};
    alternate-background-color: {p["inset"]};
    color: {p["ink"]};
    border: none;
    outline: none;
    font-size: 13px;
    padding: 4px;
}}
QTreeView::item, QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 5px;
    color: {p["ink"]};
}}
QTreeView::item:hover, QTreeWidget::item:hover {{
    background-color: {p["hover"]};
}}
QTreeView::item:selected, QTreeWidget::item:selected {{
    background-color: {p["accent_soft"]};
    color: {p["accent_strong"]};
    border-left: 2px solid {p["accent"]};
    border-radius: 0 5px 5px 0;
    padding-left: 4px;
}}
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings {{
    image: none;
}}

/* ═══ 分割条 ═══ */
QSplitter::handle {{
    background-color: {p["hairline"]};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}
QSplitter::handle:hover {{
    background-color: {p["accent"]};
}}

/* ═══ 主窗口分隔条（停靠栏与中央区之间，可拖拽调整宽度） ═══ */
QMainWindow::separator {{
    background-color: {p["border"]};
    width: 4px;
    height: 4px;
}}
QMainWindow::separator:hover {{
    background-color: {p["accent"]};
}}

/* ═══ 状态栏 ═══ */
QStatusBar {{
    background-color: {p["chrome"]};
    color: {p["ink_muted"]};
    font-size: 12px;
    border-top: 1px solid {p["border"]};
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    color: {p["ink_muted"]};
    padding: 0 10px;
}}

/* ═══ 滚动条（滑槽 + 把手，与扁平分隔条形成区分） ═══ */
QScrollBar:vertical {{
    background: {p["inset"]};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p["scrollbar"]};
    border-radius: 4px;
    min-height: 24px;
    margin: 2px;
}}
QScrollBar::handle:vertical:hover {{
    background: {p["scrollbar_hov"]};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {p["inset"]};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {p["scrollbar"]};
    border-radius: 4px;
    min-width: 24px;
    margin: 2px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {p["scrollbar_hov"]};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ═══ 消息框 / 对话框 ═══ */
QMessageBox {{
    background-color: {p["surface"]};
}}
QMessageBox QLabel {{
    color: {p["ink"]};
    font-size: 13px;
}}
QPushButton {{
    background-color: {p["inset"]};
    color: {p["ink"]};
    border: 1px solid {p["border"]};
    border-radius: 6px;
    padding: 6px 18px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {p["hover"]};
    border-color: {p["border_strong"]};
}}
QPushButton:pressed {{
    background-color: {p["pressed"]};
}}
QPushButton:default {{
    background-color: {p["accent"]};
    color: #ffffff;
    border-color: {p["accent_strong"]};
}}
QPushButton:default:hover {{
    background-color: {p["accent_strong"]};
}}

/* ═══ 模式分段控件（胶囊槽 + 选中滑块） ═══ */
QWidget#mode_seg {{
    background-color: {p["inset"]};
    border: none;
    border-radius: 9px;
}}
QWidget#mode_seg QToolButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 2px 10px;
    min-height: 18px;
    color: {p["ink_muted"]};
    font-size: 12.5px;
    font-weight: 600;
}}
QWidget#mode_seg QToolButton:hover {{
    background-color: {p["hover"]};
    color: {p["ink_strong"]};
}}
QWidget#mode_seg QToolButton:checked {{
    background-color: {p["accent_soft"]};
    color: {p["accent_strong"]};
}}
QWidget#mode_seg QToolButton:pressed {{
    background-color: {p["pressed"]};
}}

/* ═══ 右上角浮动 单/双栏 切换控件 ═══ */
QWidget#pane_toggle {{
    background-color: {p["surface"]};
    border: 1px solid {p["border_strong"]};
    border-radius: 8px;
}}
QWidget#pane_toggle QToolButton {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 7px;
    min-height: 18px;
}}
QWidget#pane_toggle QToolButton:hover {{
    background-color: {p["hover"]};
}}
QWidget#pane_toggle QToolButton:checked {{
    background-color: {p["accent_soft"]};
}}
"""


def _build_editor_qss(p: dict) -> str:
    """生成编辑器 QSS（背景/选区/光标）"""
    return f"""
QPlainTextEdit {{
    background-color: {p["editor_bg"]};
    color: {p["ink"]};
    selection-background-color: {p["selection"]};
    selection-color: {p["ink_strong"]};
    border: none;
    outline: none;
}}
"""


# ══════════════════════════════════════════════
#  主题管理器
# ══════════════════════════════════════════════


class ThemeManager:
    """主题管理器：以调色板驱动全应用样式（固定浅色「墨与纸 · 昼」）"""

    @property
    def current_theme(self) -> str:
        return "light"

    @property
    def palette(self) -> dict:
        """当前主题的调色板"""
        return LIGHT_PALETTE

    def apply_theme(self, app: QApplication) -> None:
        """应用主题到整个应用"""
        app.setStyleSheet(_build_qss(self.palette))

    def get_editor_style(self) -> str:
        """获取编辑器 QSS"""
        return _build_editor_qss(self.palette)

    def get_editor_colors(self) -> dict:
        """获取编辑器绘制用色（行号栏/当前行等，供 paintEvent 使用）"""
        p = self.palette
        return {
            "gutter_bg": p["gutter_bg"],
            "gutter_ink": p["gutter_ink"],
            "current_line": p["current_line"],
            "caret": p["caret"],
            "border": p["hairline"],
        }
