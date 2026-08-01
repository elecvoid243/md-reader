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
