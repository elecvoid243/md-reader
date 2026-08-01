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
