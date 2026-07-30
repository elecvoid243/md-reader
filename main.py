"""
main.py — MD Reader 应用入口

启动 PyQt5 应用，初始化主窗口。
支持命令行参数直接打开文件。

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


def main() -> None:
    # 启用高 DPI 缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("MD Reader")
    app.setOrganizationName("md-reader")

    # 创建主窗口
    window = MainWindow()
    window.show()

    # 命令行参数：打开文件
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            window.open_file(os.path.abspath(file_path))

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
