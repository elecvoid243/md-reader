"""
ui_smoke.py — 界面冒烟验证（offscreen 无头模式）

作者: elecvoid243
日期: 2026-07-31

验证项:
1. MainWindow 可实例化（含工具栏/双 dock/标签管理器）
2. dock 位置: TOC 在左、文件浏览器在右
3. 浅色主题可应用（QSS 构建无 KeyError；深色模式已移除）
4. 全部图标可构建（含新增的 open/save/export/sidebar_left/sidebar_right）
5. 工具栏包含 5 个常用 action（且均有图标）
6. 启动即有一个空白「未命名」占位标签页
7. 打开示例文件后占位页被替换，仅余 1 个文件标签页
8. 关闭最后一个标签页后自动补一个空白占位页

用法: python scripts\\ui_smoke.py   (退出码 0 = 通过)

注意: 不使用 QT_QPA_PLATFORM=offscreen —— 本机实测 offscreen 平台上
QWebEngineView.page()（惰性创建默认 QWebEnginePage/Profile）会原生崩溃
(0xC0000005)，而 windows 平台正常。脚本从不调用 show()，不会弹出窗口。
"""

from __future__ import annotations

import os
import sys

# QtWebEngineWidgets 必须在 QCoreApplication 创建之前导入（同 main.py）
import PyQt5.QtWebEngineWidgets  # noqa: F401, E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

# 保证可以 import app 包（脚本位于 scripts/ 下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.icons import NAMES, build_icons  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.theme_manager import LIGHT_PALETTE  # noqa: E402

EXPECTED_ICONS = {
    "reading",
    "instant",
    "source",
    "pane_single",
    "pane_dual",
    "open",
    "save",
    "export",
    "sidebar_left",
    "sidebar_right",
}


def main() -> int:
    app = QApplication([])
    window = MainWindow()

    # 1. dock 位置
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QDockWidget

    def dock_area(dock: QDockWidget) -> int:
        return int(window.dockWidgetArea(dock))

    assert dock_area(window._toc_dock) == int(Qt.LeftDockWidgetArea), "TOC 应在左侧"
    assert dock_area(window._file_dock) == int(Qt.RightDockWidgetArea), "文件树应在右侧"

    # 1b. dock 不可移动/不可浮动（仅可关闭，防止误拖为独立窗口）
    from PyQt5.QtWidgets import QDockWidget as _QDock

    fixed = int(_QDock.DockWidgetClosable)
    for dock in (window._toc_dock, window._file_dock):
        assert int(dock.features()) == fixed, "dock 应仅保留 Closable 特性"

    # 2. 浅色主题应用（QSS 构建不抛 KeyError；深色模式已移除）
    window._theme_mgr.apply_theme(app)

    # 3. 图标全集
    missing = EXPECTED_ICONS - set(NAMES)
    assert not missing, f"缺少图标: {missing}"
    icons = build_icons(LIGHT_PALETTE)
    assert set(icons) >= EXPECTED_ICONS
    assert not icons["open"].isNull()

    # 4. 工具栏包含 5 个常用 action（且均有图标）
    from PyQt5.QtWidgets import QToolBar

    bars = window.findChildren(QToolBar)
    assert bars, "应存在主工具栏"
    bar_actions = bars[0].actions()
    for attr in (
        "_act_open",
        "_act_save",
        "_act_export_pdf",
        "_act_toggle_toc",
        "_act_toggle_file_tree",
    ):
        act = getattr(window, attr)
        assert not act.icon().isNull(), f"{attr} 缺少图标"
        assert act in bar_actions, f"{attr} 应出现在工具栏"

    # 5. 启动即有空白占位标签页
    assert window._tabs.count() == 1, "启动应有 1 个占位标签页"
    placeholder = window._tabs.current_pair()
    assert placeholder is not None and placeholder.file_path is None

    # 6. 打开示例文件：占位页被替换
    sample = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples",
        "demo.md",
    )
    assert os.path.isfile(sample), f"示例文件不存在: {sample}"
    window.open_file(sample)
    assert window._tabs.count() == 1, "占位页应被替换，仅余 1 个标签页"
    pair = window._tabs.current_pair()
    assert pair is not None and pair.file_path == sample, "当前标签页应为示例文件"

    # 7. 关闭最后一个标签页 → 自动补空白占位页
    window._tabs.close_tab(0)
    assert window._tabs.count() == 1, "关闭最后标签页后应自动补占位页"
    reborn = window._tabs.current_pair()
    assert reborn is not None and reborn.file_path is None

    print("ui_smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
