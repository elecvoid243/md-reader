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


_DRAW = {
    "reading": _draw_reading,
    "instant": _draw_instant,
    "source": _draw_source,
    "pane_single": _draw_pane_single,
    "pane_dual": _draw_pane_dual,
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
