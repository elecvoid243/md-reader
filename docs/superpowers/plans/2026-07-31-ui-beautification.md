# MD Reader 界面美化（墨与纸 · 极简退隐）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不更换设计语言、不引入新依赖的前提下，将应用外壳（工具栏/标签页/侧栏/状态栏）按「极简退隐」方向全面精进。

**Architecture:** 以 `app/theme_manager.py` 的调色板 + QSS 为单一数据源更新外壳样式；`app/icons.py` 增补 4 枚同风格线性图标；`app/main_window.py` 补充工具栏按钮并交换两个 dock 的位置；Web 端仅收窄滚动条。项目无测试框架，验证采用 ruff 静态检查 + offscreen 冒烟脚本 + 人工运行核对。

**Tech Stack:** Python 3.8 / PyQt5 5.15 / Qt Style Sheets / QPainter / CSS (Chromium 87)

**Spec:** `docs/superpowers/specs/2026-07-31-ui-beautification-design.md`（commit 0a7f0a1）

## Global Constraints

- 目标平台 **Windows 7 SP1 32 位**：零新 pip 依赖、无动画、仅用 Win7 自带字体（Segoe UI / Microsoft YaHei / Consolas）
- Python 3.8 语法：保留 `from __future__ import annotations`，禁止 walrus / match-case / 运行时 PEP 604
- QSS 仅用 Qt 5.15 样式表引擎已支持的能力（现有用法即安全集）
- 主色松绿只出现在"当前状态"：选中标签下划线、当前模式、树选中指示条、开关勾选
- 侧栏布局：**TOC 固定左侧、文件浏览器固定右侧**，两者均可隐藏（沿用现有开关与配置）
- 提交信息格式 `<类型>: <描述>`；一次提交只做一件事；**只本地提交，禁止推送远端**
- 每个任务结束跑 `code_check`（ruff）+ offscreen 冒烟脚本
- 最终人工验证三种入口：无参启动 / `python main.py file.md` / 拖放打开

## 与 spec 的两处偏差（已确认，按实际代码执行）

1. 标签页脏标记已是 `●`（`app/tab_manager.py` 的 `update_title`），**无需改动**，仅在验收环节确认。
2. Web 端滚动条宽度定义在 `resources/css/markdown.css:384` 与 `resources/css/vditor-theme.css:198`（均 10px），不在 `theme-*.css`。滚动条收窄改这两个文件；`theme-*.css` 不动。

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `app/theme_manager.py` | 调色板 + 全局 QSS | 删除 status 色键；状态栏/工具栏/标签/树/滚动条/mode_seg QSS 更新 |
| `app/icons.py` | 线性图标工厂 | 新增 open/save/export/theme 四个绘制函数 |
| `app/main_window.py` | 主窗口装配 | 工具栏补 4 按钮 + 弹簧；dock 左右互换并锁定区域 |
| `resources/css/markdown.css` | 预览排版 | 滚动条 10px → 8px |
| `resources/css/vditor-theme.css` | Vditor 主题 | 滚动条 10px → 8px |
| `scripts/ui_smoke.py` | offscreen 冒烟验证 | 新建（验证资产，可长期保留） |

---

### Task 1: 环境验证与 git worktree 建立

**Files:**
- Create: worktree 目录 `F:\github\md-reader-wt\ui-beauty`（分支 `feat/ui-minimal-retreat`）

**Interfaces:**
- Consumes: 无
- Produces: 后续所有任务在 `F:\github\md-reader-wt\ui-beauty` 中执行（下文路径均相对该 worktree 根）

- [ ] **Step 1: 验证本机可运行项目**

Run: `cd /d F:\github\md-reader && python -c "import PyQt5.QtWebEngineWidgets, PyQt5.QtWidgets; print('env ok')"`
Expected: 输出 `env ok`（若失败说明本机缺依赖，先 `pip install -r requirements.txt`，本机为 64 位环境仅用于开发验证）

- [ ] **Step 2: 建立 worktree**

```bash
cd /d F:\github\md-reader
git worktree add F:\github\md-reader-wt\ui-beauty -b feat/ui-minimal-retreat
```

Expected: 输出 `Preparing worktree (new branch 'feat/ui-minimal-retreat')` 等字样

- [ ] **Step 3: 确认 worktree 可用**

Run: `cd /d F:\github\md-reader-wt\ui-beauty && git status --short && python main.py --help 2>nul & echo started`
Expected: 工作区干净；`main.py` 可被 Python 加载（无 import 报错即可，随后手动关闭窗口）

---

### Task 2: 创建 offscreen 冒烟验证脚本

**Files:**
- Create: `scripts/ui_smoke.py`

**Interfaces:**
- Consumes: `app.main_window.MainWindow`、`app.theme_manager.ThemeManager`、`app.icons.build_icons`
- Produces: `python scripts\ui_smoke.py` 退出码 0 = 通过；后续每个任务完成后运行

> 说明：项目无 pytest。本脚本以 `QT_QPA_PLATFORM=offscreen` 无头实例化主窗口、
> 应用两套主题、构建全部图标、打开一个示例文件，作为全部视觉任务的自动化回归。

- [ ] **Step 1: 编写脚本**

```python
"""
ui_smoke.py — 界面冒烟验证（offscreen 无头模式）

作者: elecvoid243
日期: 2026-07-31

验证项:
1. MainWindow 可实例化（含工具栏/双 dock/标签管理器）
2. dock 位置: TOC 在左、文件浏览器在右
3. 两套主题均可应用（QSS 构建无 KeyError）
4. 全部图标可构建（含新增的 open/save/export/theme）
5. 打开示例文件后标签页创建成功

用法: python scripts\\ui_smoke.py   (退出码 0 = 通过)
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngineWidgets 必须在 QCoreApplication 创建之前导入（同 main.py）
import PyQt5.QtWebEngineWidgets  # noqa: F401, E402

from PyQt5.QtWidgets import QApplication  # noqa: E402

# 保证可以 import app 包（脚本位于 scripts/ 下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.icons import NAMES, build_icons  # noqa: E402
from app.main_window import MainWindow  # noqa: E402
from app.theme_manager import DARK_PALETTE, LIGHT_PALETTE  # noqa: E402

EXPECTED_ICONS = {
    "reading", "instant", "source", "pane_single", "pane_dual",
    "open", "save", "export", "theme",
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

    # 2. 两套主题应用（QSS 构建不抛 KeyError）
    window._theme_mgr.apply_theme("light", app)
    window._theme_mgr.apply_theme("dark", app)
    window._theme_mgr.apply_theme("light", app)

    # 3. 图标全集
    missing = EXPECTED_ICONS - set(NAMES)
    assert not missing, f"缺少图标: {missing}"
    icons = build_icons(LIGHT_PALETTE)
    assert set(icons) >= EXPECTED_ICONS
    assert not icons["open"].isNull()
    build_icons(DARK_PALETTE)

    # 4. 工具栏包含 4 个常用 action（且均有图标）
    from PyQt5.QtWidgets import QToolBar

    bars = window.findChildren(QToolBar)
    assert bars, "应存在主工具栏"
    bar_actions = bars[0].actions()
    for attr in ("_act_open", "_act_save", "_act_export_pdf", "_act_toggle_theme"):
        act = getattr(window, attr)
        assert not act.icon().isNull(), f"{attr} 缺少图标"
        assert act in bar_actions, f"{attr} 应出现在工具栏"

    # 5. 打开示例文件
    sample = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "examples", "README.md",
    )
    if os.path.isfile(sample):
        window.open_file(sample)
        assert window._tabs.count() == 1, "示例文件应打开 1 个标签页"

    print("ui_smoke: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 运行确认当前基线（预期在 dock 位置断言处失败）**

Run: `cd /d F:\github\md-reader-wt\ui-beauty && python scripts\ui_smoke.py`
Expected: FAIL，断言 "TOC 应在左侧"（当前 TOC 在右）——证明脚本有效

- [ ] **Step 3: Commit**

```bash
git add scripts/ui_smoke.py
git commit -m "测试: 新增 offscreen 界面冒烟验证脚本"
```

---

### Task 3: theme_manager.py 调色板与 QSS 更新

**Files:**
- Modify: `app/theme_manager.py`（调色板两处 + `_build_qss` 六处）

**Interfaces:**
- Consumes: 无
- Produces: 调色板删除 `status_bg` / `status_ink` 两键（两个主题都删）；QSS 选择器与属性如下。外部接口（`apply_theme` / `palette` / `get_editor_style` / `get_editor_colors`）签名不变

- [ ] **Step 1: 删除调色板中的状态栏色键**

在 `LIGHT_PALETTE` 中删除：
```python
    # 状态栏
    "status_bg": "#0e6b5a",
    "status_ink": "#eaf4f0",
```
在 `DARK_PALETTE` 中删除：
```python
    # 状态栏
    "status_bg": "#0f5a4c",
    "status_ink": "#dcefe9",
```

- [ ] **Step 2: QSS —— 状态栏退为素色**

将 `_build_qss` 中：
```css
QStatusBar {{
    background-color: {p["status_bg"]};
    color: {p["status_ink"]};
    font-size: 12px;
    border-top: none;
}}
QStatusBar QLabel {{
    color: {p["status_ink"]};
    padding: 0 10px;
}}
```
替换为：
```css
QStatusBar {{
    background-color: {p["chrome"]};
    color: {p["ink_muted"]};
    font-size: 12px;
    border-top: 1px solid {p["hairline"]};
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    color: {p["ink_muted"]};
    padding: 0 10px;
}}
```

- [ ] **Step 3: QSS —— 工具栏收窄 + 合并重复定义**

将第一段工具栏定义：
```css
QToolBar {{
    background-color: {p["chrome"]};
    border: none;
    border-bottom: 1px solid {p["hairline"]};
    spacing: 3px;
    padding: 4px 6px;
}}
```
替换为：
```css
QToolBar {{
    background-color: {p["chrome"]};
    border: none;
    border-bottom: 1px solid {p["hairline"]};
    spacing: 4px;
    padding: 5px 10px;
}}
```
并**删除**文件后部重复的：
```css
/* ═══ 工具栏 ═══ */
QToolBar {{
    padding: 7px 14px;
    spacing: 10px;
}}
```

- [ ] **Step 4: QSS —— 标签页去背景、仅保留下划线**

将 `QTabBar::tab:selected` 块：
```css
QTabBar::tab:selected {{
    color: {p["ink_strong"]};
    border-bottom: 2px solid {p["accent"]};
    background-color: {p["chrome_alt"]};
    font-weight: 600;
}}
```
替换为：
```css
QTabBar::tab:selected {{
    color: {p["ink_strong"]};
    border-bottom: 2px solid {p["accent"]};
    background: transparent;
    font-weight: 600;
}}
```

- [ ] **Step 5: QSS —— 树选中项加左侧指示条（QTreeView 与 QTreeWidget 同步）**

将：
```css
QTreeView::item:selected {{
    background-color: {p["accent_soft"]};
    color: {p["accent_strong"]};
}}
```
替换为（注意补齐 `QTreeWidget::item` 系列，使右侧 TOC 树同样生效）：
```css
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
```
同时删除原有单独的 `QTreeView::item` / `QTreeView::item:hover` 两段（已被上方合并块覆盖，保留会重复）。
> 验收注意：若 `border-left` 在树项上不生效，降级为仅 `accent_soft` 底色（spec §6 风险点 1）。

- [ ] **Step 6: QSS —— 滚动条收窄至 8px**

将垂直滚动条块中 `width: 11px;` 改为 `width: 8px;`，handle 的 `border-radius: 5px;` 改为 `border-radius: 4px;`；
水平滚动条块中 `height: 11px;` 改为 `height: 8px;`，handle 同样 `border-radius: 4px;`。

- [ ] **Step 7: QSS —— 模式胶囊去外框**

将：
```css
QWidget#mode_seg {{
    background-color: {p["inset"]};
    border: 1px solid {p["border"]};
    border-radius: 9px;
}}
```
替换为：
```css
QWidget#mode_seg {{
    background-color: {p["inset"]};
    border: none;
    border-radius: 9px;
}}
```

- [ ] **Step 8: 静态检查 + 冒烟**

Run: `code_check app/theme_manager.py`（或 ruff）
Run: `python scripts\ui_smoke.py`
Expected: 静态检查通过；冒烟仍在 dock 断言失败（属预期，Task 5 修复），但不得出现 `KeyError: 'status_bg'` 等异常

- [ ] **Step 9: Commit**

```bash
git add app/theme_manager.py
git commit -m "样式: 外壳 QSS 极简退隐(状态栏素色/工具栏收窄/标签下划线/树指示条/滚动条8px/胶囊去框)"
```

---

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

### Task 5: main_window.py 工具栏补按钮 + dock 换位锁定

**Files:**
- Modify: `app/main_window.py`（`_setup_toolbar`、`_init_icons`、`_setup_components`、imports）

**Interfaces:**
- Consumes: Task 4 的图标名 `"open"/"save"/"export"/"theme"`；已有 action `_act_open`/`_act_save`/`_act_export_pdf`/`_act_toggle_theme`
- Produces: dock 布局契约 = TOC 左 / 文件树右 / 各锁定单侧（Task 2 冒烟脚本断言目标）

- [ ] **Step 1: 补充 QSizePolicy 导入**

在 `from PyQt5.QtWidgets import (...)` 导入块中按字母序加入 `QSizePolicy`（与现有 `QSize` 等并列，注意 `QSize` 在 `QtCore` 导入中，`QSizePolicy` 属于 `QtWidgets`）。

- [ ] **Step 2: dock 左右互换并锁定单侧区域**

将 `_setup_components` 中的侧栏段落：
```python
        # 左侧停靠：文件树
        self._file_tree = FileTreeWidget()
        self._file_dock = QDockWidget("文件浏览器", self)
        self._file_dock.setWidget(self._file_tree)
        self._file_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, self._file_dock)

        # 右侧停靠：TOC 导航
        self._toc = TocWidget()
        self._toc_dock = QDockWidget("目录导航", self)
        self._toc_dock.setWidget(self._toc)
        self._toc_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, self._toc_dock)
```
替换为：
```python
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
```

- [ ] **Step 3: 图标映射补充 4 个 action + 悬浮提示**

将 `_init_icons` 中：
```python
        self._action_icon = {
            self._act_mode_reading: "reading",
            self._act_mode_instant: "instant",
            self._act_mode_source: "source",
            self._act_dual_pane: "pane_dual",
        }
```
替换为：
```python
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
```
并在同一方法中现有 `setToolTip` 语句后追加：
```python
        self._act_open.setToolTip("打开文件 (Ctrl+O)")
        self._act_save.setToolTip("保存 (Ctrl+S)")
        self._act_export_pdf.setToolTip("导出为 PDF")
        self._act_toggle_theme.setToolTip("切换深色/浅色主题 (Ctrl+Shift+D)")
```

- [ ] **Step 4: 工具栏装配 4 按钮 + 弹簧 + 模式胶囊**

将 `_setup_toolbar` 整体替换为：
```python
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
```

- [ ] **Step 5: 静态检查 + 冒烟（应全部通过）**

Run: `code_check app/main_window.py`
Run: `python scripts\ui_smoke.py`
Expected: 输出 `ui_smoke: OK`，退出码 0

- [ ] **Step 6: Commit**

```bash
git add app/main_window.py
git commit -m "新增: 工具栏常用操作按钮 + 侧栏布局互换(左TOC/右文件树)并锁定"
```

---

### Task 6: Web 端滚动条收窄

**Files:**
- Modify: `resources/css/markdown.css:384`
- Modify: `resources/css/vditor-theme.css:198`

**Interfaces:**
- Consumes: 无
- Produces: 预览与 Vditor 滚动条宽度 8px，与 Qt 侧一致

- [ ] **Step 1: markdown.css**

将：
```css
::-webkit-scrollbar { width: 10px; height: 10px; }
```
替换为：
```css
::-webkit-scrollbar { width: 8px; height: 8px; }
```

- [ ] **Step 2: vditor-theme.css**

将：
```css
.vditor-ir .vditor-reset::-webkit-scrollbar { width: 10px; height: 10px; }
```
替换为：
```css
.vditor-ir .vditor-reset::-webkit-scrollbar { width: 8px; height: 8px; }
```

- [ ] **Step 3: Commit**

```bash
git add resources/css/markdown.css resources/css/vditor-theme.css
git commit -m "样式: Web端滚动条收窄至8px与外壳一致"
```

---

### Task 7: 人工视觉验收 + 合并回 main

**Files:**
- 无代码改动；产出验收结论与合并提交

**Interfaces:**
- Consumes: Task 2-6 全部产物
- Produces: `main` 分支包含全部改动（本地合并，不推送）

- [ ] **Step 1: 三入口验证（在 worktree 中）**

```bash
cd /d F:\github\md-reader-wt\ui-beauty
python main.py                       :: 无参启动：空窗口、左TOC/右文件树
python main.py examples\README.md    :: 带参启动：渲染、TOC联动正常
```
另手动拖放一个 `.md` 到窗口验证第三种入口。

- [ ] **Step 2: 视觉核对清单（对照 spec §4 逐项）**

1. 状态栏 = 素色 + 顶部发丝线（不再是松绿整条）
2. 工具栏 4 枚单色图标在左、模式胶囊在右且无外框；hover 有反馈
3. 标签页：选中 = 松绿下划线 + 加粗，无背景块
4. 编辑后标签出现 `●` 脏标记，保存后消失（既有行为，确认未被破坏）
5. 文件树/TOC 选中项 = 浅松绿底 + 左侧指示条（若 border-left 不生效，按 spec §6 降级）
6. 滚动条 Qt 侧与 Web 侧均为 8px
7. Ctrl+Shift+D 切换暗色主题：以上 1-6 在暗色下同样成立
8. 视图菜单分别隐藏/显示两个侧栏，重启后可见性保持

- [ ] **Step 3: 全量静态检查**

Run: `code_check` 对 `app/theme_manager.py` `app/icons.py` `app/main_window.py` `scripts/ui_smoke.py`
Expected: 全部通过

- [ ] **Step 4: 合并回 main 并清理 worktree**

```bash
cd /d F:\github\md-reader
git merge --no-ff feat/ui-minimal-retreat -m "合并: 界面美化(墨与纸·极简退隐)"
git worktree remove F:\github\md-reader-wt\ui-beauty
git branch -d feat/ui-minimal-retreat
```

> 合并仅限本地，禁止 `git push`。

---

## Self-Review 记录

- Spec 覆盖：§4.1→Task3 Step1-2；§4.2→Task3 Step3/7 + Task5 Step3-4；§4.3→Task4；§4.4→Task3 Step4（脏标记已存在，Task7 清单第4项验收）；§4.5→Task5 Step2 + Task3 Step5；§4.6→Task3 Step2；§4.7→Task3 Step3/6；§4.8→Task6。§7 验证计划→Task2 + Task7。全覆盖。
- 占位符扫描：无 TBD/TODO；所有代码步骤含完整代码。
- 类型/命名一致性：图标名 `open/save/export/theme` 在 Task2 冒烟脚本、Task4 `_DRAW`、Task5 `_action_icon` 三处一致；action 名与 `main_window.py` 现有定义一致。
