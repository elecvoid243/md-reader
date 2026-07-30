"""
theme_manager.py — 主题管理

管理亮色/暗色主题的切换，同步应用到：
- 编辑器 (QPlainTextEdit 样式)
- 预览区 (JS 端 CSS 切换)
- 主窗口 (QSS 样式表)
"""

from __future__ import annotations

from PyQt5.QtWidgets import QApplication

from .config import Config

# 编辑器亮色主题样式
EDITOR_LIGHT_STYLE = """
QPlainTextEdit {
    background-color: #ffffff;
    color: #24292e;
    selection-background-color: #b3d7ff;
    selection-color: #24292e;
}
"""

# 编辑器暗色主题样式
EDITOR_DARK_STYLE = """
QPlainTextEdit {
    background-color: #1e1e1e;
    color: #d4d4d4;
    selection-background-color: #264f78;
    selection-color: #d4d4d4;
}
"""

# 主窗口亮色 QSS
WINDOW_LIGHT_QSS = """
QMainWindow, QWidget {
    background-color: #f5f5f5;
    color: #333333;
}
QMenuBar {
    background-color: #f0f0f0;
    color: #333333;
}
QMenuBar::item:selected {
    background-color: #e0e0e0;
}
QMenu {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d0d0d0;
}
QMenu::item:selected {
    background-color: #e8f0fe;
}
QToolBar {
    background-color: #f0f0f0;
    border: none;
    spacing: 4px;
    padding: 2px;
}
QStatusBar {
    background-color: #f0f0f0;
    color: #666666;
}
QTabWidget::pane {
    border: 1px solid #d0d0d0;
}
QTabBar::tab {
    background-color: #e8e8e8;
    color: #555555;
    padding: 6px 16px;
    border: 1px solid #d0d0d0;
    border-bottom: none;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #333333;
}
QTabBar::tab:hover {
    background-color: #f0f0f0;
}
QTreeView {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d0d0d0;
}
QTreeView::item:selected {
    background-color: #e8f0fe;
}
QTreeWidget {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d0d0d0;
}
QTreeWidget::item:selected {
    background-color: #e8f0fe;
}
QSplitter::handle {
    background-color: #d0d0d0;
}
"""

# 主窗口暗色 QSS
WINDOW_DARK_QSS = """
QMainWindow, QWidget {
    background-color: #252526;
    color: #cccccc;
}
QMenuBar {
    background-color: #2d2d2d;
    color: #cccccc;
}
QMenuBar::item:selected {
    background-color: #3c3c3c;
}
QMenu {
    background-color: #2d2d2d;
    color: #cccccc;
    border: 1px solid #404040;
}
QMenu::item:selected {
    background-color: #094771;
}
QToolBar {
    background-color: #2d2d2d;
    border: none;
    spacing: 4px;
    padding: 2px;
}
QStatusBar {
    background-color: #007acc;
    color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #404040;
}
QTabBar::tab {
    background-color: #2d2d2d;
    color: #999999;
    padding: 6px 16px;
    border: 1px solid #404040;
    border-bottom: none;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #ffffff;
}
QTabBar::tab:hover {
    background-color: #333333;
}
QTreeView {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #404040;
}
QTreeView::item:selected {
    background-color: #094771;
}
QTreeWidget {
    background-color: #252526;
    color: #cccccc;
    border: 1px solid #404040;
}
QTreeWidget::item:selected {
    background-color: #094771;
}
QSplitter::handle {
    background-color: #404040;
}
QScrollBar:vertical {
    background-color: #1e1e1e;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #424242;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4f4f4f;
}
"""


class ThemeManager:
    """主题管理器"""

    def __init__(self) -> None:
        self._config = Config()
        self._current_theme: str = self._config.get("theme", "light")

    @property
    def current_theme(self) -> str:
        return self._current_theme

    def apply_theme(self, theme_name: str, app: QApplication) -> None:
        """应用主题到整个应用"""
        self._current_theme = theme_name
        self._config.set("theme", theme_name)

        if theme_name == "dark":
            app.setStyleSheet(WINDOW_DARK_QSS)
        else:
            app.setStyleSheet(WINDOW_LIGHT_QSS)

    def get_editor_style(self) -> str:
        """获取编辑器样式表"""
        if self._current_theme == "dark":
            return EDITOR_DARK_STYLE
        return EDITOR_LIGHT_STYLE

    def toggle(self, app: QApplication) -> str:
        """切换主题，返回新主题名"""
        new_theme = "dark" if self._current_theme == "light" else "light"
        self.apply_theme(new_theme, app)
        return new_theme
