"""
icons.py — 线性图标工厂

用 QPainter 在 24×24 逻辑网格上手绘一组极简线性图标，渲染为 QIcon。
- 矢量、抗锯齿、圆头线帽，风格统一专业
- 不依赖字体/emoji/SVG 引擎，Windows 7 兼容
- 每个图标生成 Off（未选中，中性墨色）与 On（选中，主色）两态，
  使 checkable 按钮在选中时图标自动变为主色，提供清晰的点击反馈

绘制函数签名统一：draw(painter, color)，坐标基于 24×24 逻辑窗口。
"""

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

# 逻辑绘图网格
_GRID = 24
# 线宽（逻辑单位，映射到物理像素后约 1.5px @20px 显示）
_STROKE = 1.9


# ──────────────────────────────────────────────
#  绘制函数（24×24 坐标）
# ──────────────────────────────────────────────


def _draw_reading(p: QPainter, color: str) -> None:
    """眼睛：阅读模式"""
    eye = QPainterPath()
    eye.moveTo(2, 12)
    eye.quadTo(12, 3.5, 22, 12)
    eye.quadTo(12, 20.5, 2, 12)
    eye.closeSubpath()
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(eye)
    # 瞳孔
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QPointF(12, 12), 2.7, 2.7)


def _draw_instant(p: QPainter, color: str) -> None:
    """铅笔：即时渲染（在内容上直接书写）"""
    body = QPainterPath()
    body.moveTo(14.5, 3.5)
    body.lineTo(20.5, 9.5)
    body.lineTo(9, 21)
    body.lineTo(3, 21)
    body.lineTo(3, 15)
    body.closeSubpath()
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(body)
    # 笔身分隔线
    p.drawLine(QPointF(12.5, 5.5), QPointF(18.5, 11.5))


def _draw_source(p: QPainter, color: str) -> None:
    """代码尖括号 </>：源码编辑"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    left = QPainterPath()
    left.moveTo(9, 7)
    left.lineTo(4, 12)
    left.lineTo(9, 17)
    p.drawPath(left)
    right = QPainterPath()
    right.moveTo(15, 7)
    right.lineTo(20, 12)
    right.lineTo(15, 17)
    p.drawPath(right)
    # 中间斜杠
    p.drawLine(QPointF(13.5, 6), QPointF(10.5, 18))


def _draw_pane_single(p: QPainter, color: str) -> None:
    """单栏：一个完整面板"""
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)


def _draw_pane_dual(p: QPainter, color: str) -> None:
    """双栏：面板中间分隔"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)
    p.drawLine(QPointF(12, 5), QPointF(12, 19))


def _draw_open(p: QPainter, color: str) -> None:
    """文件夹：打开文件"""
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    folder = QPainterPath()
    folder.moveTo(3, 19)
    folder.lineTo(3, 6.5)
    folder.quadTo(3, 5, 4.5, 5)
    folder.lineTo(9, 5)
    folder.lineTo(11.5, 8)
    folder.lineTo(19.5, 8)
    folder.quadTo(21, 8, 21, 9.5)
    folder.lineTo(21, 19)
    folder.closeSubpath()
    p.drawPath(folder)


def _draw_save(p: QPainter, color: str) -> None:
    """软盘：保存"""
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    body = QPainterPath()
    body.moveTo(5, 3.5)
    body.lineTo(15.5, 3.5)
    body.lineTo(20.5, 8.5)
    body.lineTo(20.5, 20.5)
    body.lineTo(5, 20.5)
    body.closeSubpath()
    p.drawPath(body)
    # 上部滑盖 + 下部存储槽
    p.drawRect(QRectF(8, 3.5, 8, 5.5))
    p.drawRect(QRectF(8, 13.5, 8, 7))


def _draw_export(p: QPainter, color: str) -> None:
    """向上导出箭头：导出"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # 托盘
    tray = QPainterPath()
    tray.moveTo(4, 14)
    tray.lineTo(4, 19)
    tray.quadTo(4, 20.5, 5.5, 20.5)
    tray.lineTo(18.5, 20.5)
    tray.quadTo(20, 20.5, 20, 19)
    tray.lineTo(20, 14)
    p.drawPath(tray)
    # 向上箭头
    p.drawLine(QPointF(12, 15.5), QPointF(12, 4.5))
    head = QPainterPath()
    head.moveTo(8, 8.5)
    head.lineTo(12, 4.5)
    head.lineTo(16, 8.5)
    p.drawPath(head)


def _draw_sidebar(p: QPainter, color: str, left: bool) -> None:
    """侧栏面板：外框 + 一侧填充（left=True 填充左侧）"""
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 2, 2)
    line_x = 9.5 if left else 14.5
    p.drawLine(QPointF(line_x, 5), QPointF(line_x, 19))
    # 侧栏区域填充（内缩避免与外框描边重叠）
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(color)))
    fill_x = 4.7 if left else 15.0
    p.drawRect(QRectF(fill_x, 6.5, 4.3, 11))


def _draw_sidebar_left(p: QPainter, color: str) -> None:
    """左侧栏显隐"""
    _draw_sidebar(p, color, left=True)


def _draw_sidebar_right(p: QPainter, color: str) -> None:
    """右侧栏显隐"""
    _draw_sidebar(p, color, left=False)


def _draw_search(p: QPainter, color: str) -> None:
    """放大镜：查找"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(10.5, 10.5), 6.2, 6.2)
    p.drawLine(QPointF(15.2, 15.2), QPointF(20.5, 20.5))


def _draw_chevron_up(p: QPainter, color: str) -> None:
    """上箭头：上一个匹配"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(6, 14.5)
    path.lineTo(12, 8.5)
    path.lineTo(18, 14.5)
    p.drawPath(path)


def _draw_chevron_down(p: QPainter, color: str) -> None:
    """下箭头：下一个匹配"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(6, 9.5)
    path.lineTo(12, 15.5)
    path.lineTo(18, 9.5)
    p.drawPath(path)


def _draw_close(p: QPainter, color: str) -> None:
    """关闭叉：退出查找"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawLine(QPointF(7, 7), QPointF(17, 17))
    p.drawLine(QPointF(17, 7), QPointF(7, 17))


def _draw_sync(p: QPainter, color: str) -> None:
    """上下双向箭头：滚动同步"""
    pen = QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    # 上箭头（左列）
    p.drawLine(QPointF(8, 18.5), QPointF(8, 6.5))
    head_up = QPainterPath()
    head_up.moveTo(4.6, 10)
    head_up.lineTo(8, 6.2)
    head_up.lineTo(11.4, 10)
    p.drawPath(head_up)
    # 下箭头（右列）
    p.drawLine(QPointF(16, 5.5), QPointF(16, 17.5))
    head_dn = QPainterPath()
    head_dn.moveTo(12.6, 14)
    head_dn.lineTo(16, 17.8)
    head_dn.lineTo(19.4, 14)
    p.drawPath(head_dn)


_DRAW = {
    "reading": _draw_reading,
    "instant": _draw_instant,
    "source": _draw_source,
    "pane_single": _draw_pane_single,
    "pane_dual": _draw_pane_dual,
    "open": _draw_open,
    "save": _draw_save,
    "export": _draw_export,
    "sidebar_left": _draw_sidebar_left,
    "sidebar_right": _draw_sidebar_right,
    "search": _draw_search,
    "chevron_up": _draw_chevron_up,
    "chevron_down": _draw_chevron_down,
    "close": _draw_close,
    "sync": _draw_sync,
}

NAMES = list(_DRAW)


# ──────────────────────────────────────────────
#  工厂
# ──────────────────────────────────────────────


def _pixmap(draw, color: str, phys: int) -> QPixmap:
    """在 phys×phys 物理像素上，用 24×24 逻辑窗口绘制单个图标"""
    pm = QPixmap(phys, phys)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.setViewport(0, 0, phys, phys)
    p.setWindow(0, 0, _GRID, _GRID)
    draw(p, color)
    p.end()
    return pm


def make_icon(name: str, color_off: str, color_on: str, phys: int = 40) -> QIcon:
    """生成双态图标：Off=未选中色，On=选中色"""
    draw = _DRAW[name]
    icon = QIcon()
    icon.addPixmap(_pixmap(draw, color_off, phys), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_pixmap(draw, color_on, phys), QIcon.Normal, QIcon.On)
    return icon


def build_icons(palette: dict, phys: int = 40) -> dict[str, QIcon]:
    """由调色板批量生成全部图标"""
    off = palette["ink_muted"]
    on = palette["accent"]
    return {name: make_icon(name, off, on, phys) for name in _DRAW}
