"""
single_instance.py — 单实例守护与进程间文件转发

首个进程通过 QLocalServer 监听命名管道成为主实例；后续进程作为客户端
连入，把命令行携带的文件路径转发给主实例后立即退出，由主实例打开文件
并激活窗口，避免"打开方式"每次拉起一个新进程。

Windows 命名管道随进程终止自动销毁，无残留清理问题。
"""

import ctypes
import getpass
import json
from typing import List, Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtWidgets import QWidget

# Windows: 允许任意进程取得前台权限（ASFW_ANY）。第二实例刚被用户启动、
# 持有前台权限，退出前转让给主实例，主实例的 SetForegroundWindow 才能生效
_ASFW_ANY = -1


def _server_key(base_name: str) -> str:
    """管道名加入当前用户名，避免多用户会话（如终端服务器）互相抢占"""
    try:
        user = getpass.getuser()
    except Exception:
        user = "default"
    return "%s-%s" % (base_name, user)


def bring_window_to_front(window: QWidget) -> None:
    """恢复并置前主窗口。

    Qt 的 raise_/activateWindow 在 Windows 上受前台锁定限制（后台进程
    只能闪任务栏），配合第二实例的 AllowSetForegroundWindow 授权，
    再补一次原生 SetForegroundWindow 才能真正抢到焦点。
    """
    window.showNormal()
    window.raise_()
    window.activateWindow()
    try:
        hwnd = int(window.winId())
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except (AttributeError, OSError, TypeError):
        pass  # 非 Windows 或句柄不可用时退化为 Qt 行为


class SingleInstanceGuard(QObject):
    """单实例守护。

    第二实例调用 acquire()：已有主实例则转发参数并返回 False（调用方
    应直接退出）；否则自己监听成为主实例并返回 True，此后通过
    pathsReceived 信号接收后续实例转发来的文件路径。
    """

    pathsReceived = pyqtSignal(list)

    def __init__(self, base_name: str, parent: QObject = None) -> None:
        super().__init__(parent)
        self._server_name = _server_key(base_name)
        self._server: Optional[QLocalServer] = None
        self._clients: List[QLocalSocket] = []

    # ── 第二实例侧 ──────────────────────────────

    def acquire(self, paths: List[str]) -> bool:
        """尝试成为主实例；已有实例在运行时转发 paths 并返回 False"""
        if self._forward_to_running(paths):
            return False

        QLocalServer.removeServer(self._server_name)
        server = QLocalServer()
        if not server.listen(self._server_name):
            # 与另一实例同时启动的竞态：listen 输的一方再尝试转发
            if self._forward_to_running(paths):
                return False
            # 极端情况（转发失败且无法监听）：降级为无守护多实例，
            # 不阻断用户使用
            print("[single_instance] 无法监听 %s: %s"
                  % (self._server_name, server.errorString()))
            return True

        self._server = server
        self._server.newConnection.connect(self._on_new_connection)
        return True

    def _forward_to_running(self, paths: List[str]) -> bool:
        """连接已存在的主实例并转发路径，成功返回 True"""
        socket = QLocalSocket()
        socket.connectToServer(self._server_name)
        if not socket.waitForConnected(1000):
            return False

        try:
            ctypes.windll.user32.AllowSetForegroundWindow(_ASFW_ANY)
        except (AttributeError, OSError):
            pass

        payload = json.dumps({"paths": paths}) + "\n"
        socket.write(payload.encode("utf-8"))
        socket.flush()
        socket.waitForBytesWritten(1000)
        socket.disconnectFromServer()
        return True

    # ── 主实例侧 ──────────────────────────────

    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            client = self._server.nextPendingConnection()
            client.readyRead.connect(lambda c=client: self._on_ready_read(c))
            client.disconnected.connect(lambda c=client: self._drop_client(c))
            self._clients.append(client)

    def _on_ready_read(self, client: QLocalSocket) -> None:
        chunk = bytes(client.readAll()).decode("utf-8", errors="replace")
        buffer = getattr(client, "_buffer", "") + chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            if line.strip():
                try:
                    payload = json.loads(line)
                    paths = [p for p in payload.get("paths", []) if p]
                    self.pathsReceived.emit(paths)
                except ValueError:
                    continue
        client._buffer = buffer

    def _drop_client(self, client: QLocalSocket) -> None:
        if client in self._clients:
            self._clients.remove(client)
        client.deleteLater()
