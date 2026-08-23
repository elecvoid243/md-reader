"""
main.py — MD Reader 应用入口

启动 PyQt5 应用，初始化主窗口。
支持命令行参数直接打开文件；已运行实例时转发参数并复用（单实例）。

用法:
    python main.py              # 启动空窗口
    python main.py README.md    # 启动并打开指定文件
"""

import os
import sys

# 高 DPI 支持（必须在 QApplication 创建之前设置）
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

# QtWebEngineWidgets 必须在 QCoreApplication 创建之前导入
import PyQt5.QtWebEngineWidgets  # noqa: F401, E402

from PyQt5.QtCore import Qt  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from app.main_window import MainWindow  # noqa: E402
from app.single_instance import SingleInstanceGuard, bring_window_to_front  # noqa: E402


def main() -> None:
    # 启用高 DPI 缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # QtWebEngine 官方要求：必须在 QApplication 构造前开启，
    # 否则 WebGL 上下文无法共享，渲染进程可能初始化失败
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MD Reader")
    app.setOrganizationName("md-reader")

    # 单实例：已有实例在运行时转发文件路径后直接退出
    paths = []
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        paths = [os.path.abspath(sys.argv[1])]

    guard = SingleInstanceGuard("md-reader")
    if not guard.acquire(paths):
        return

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 后续实例转发来的文件：打开并置前窗口（无参数时仅置前）
    def on_paths_received(forwarded: list) -> None:
        for path in forwarded:
            window.open_file(path)
        bring_window_to_front(window)

    guard.pathsReceived.connect(on_paths_received)

    # 命令行参数：打开文件
    if paths:
        window.open_file(paths[0])

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
