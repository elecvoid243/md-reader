### Task 4: icons.py 新增 4 枚线性图标

**Files:**
- Modify: `app/icons.py`（新增 4 个绘制函数 + 注册到 `_DRAW`）

**Interfaces:**
- Consumes: 现有 `_STROKE`、`_pixmap`、`make_icon`、`build_icons`（签名不变）
- Produces: `NAMES` 增加 `"open"`, `"save"`, `"export"`, `"theme"`；`build_icons(palette)` 返回字典含新键（Task 2 冒烟脚本依赖）

- [ ] **Step 1: 在 `_draw_pane_dual` 之后追加 4 个绘制函数**

```python
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


def _draw_theme(p: QPainter, color: str) -> None:
    """半满圆：主题切换（亮暗通用）"""
    p.setPen(QPen(QColor(color), _STROKE, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QPointF(12, 12), 8, 8)
    # 右半填充（startAngle 90° = 正上方，span -180° 顺时针扫过右半圆）
    half = QPainterPath()
    half.moveTo(12, 12)
    half.arcTo(QRectF(4, 4, 16, 16), 90, -180)
    half.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(color)))
    p.drawPath(half)
```

- [ ] **Step 2: 注册到 `_DRAW`**

将 `_DRAW` 字典替换为：
```python
_DRAW = {
    "reading": _draw_reading,
    "instant": _draw_instant,
    "source": _draw_source,
    "pane_single": _draw_pane_single,
    "pane_dual": _draw_pane_dual,
    "open": _draw_open,
    "save": _draw_save,
    "export": _draw_export,
    "theme": _draw_theme,
}
```

- [ ] **Step 3: 静态检查 + 冒烟（图标断言应通过，dock 断言仍失败）**

Run: `code_check app/icons.py`
Run: `python scripts\ui_smoke.py`
Expected: 无 "缺少图标" 断言；dock 位置断言仍失败（预期）

- [ ] **Step 4: Commit**

```bash
git add app/icons.py
git commit -m "新增: 工具栏4枚线性图标(打开/保存/导出/主题)"
```

---
