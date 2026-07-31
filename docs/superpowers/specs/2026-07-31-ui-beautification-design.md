# MD Reader 界面美化设计 —— 「墨与纸 · 极简退隐」

- 作者：elecvoid243
- 日期：2026-07-31
- 状态：已获用户批准（含侧栏布局调整意见）
- 目标平台：Windows 7 SP1（含 32 位）/ Python 3.8 / PyQt5 5.15

## 1. 背景与目标

MD Reader 已具备「墨与纸」设计系统（暖纸色调 + 松绿主色 + 琥珀点睛，亮/暗双主题，
QSS 与预览 CSS 同源）。本次美化**不更换设计语言**，在现有调色板基础上做"极简退隐"
方向的全面精进：应用外壳（工具栏 / 标签页 / 侧栏 / 状态栏）降噪，让注意力回归文档本身。

### 用户已确认的决策

| 决策点 | 结论 |
|---|---|
| 总体方向 | 延续「墨与纸」，全面精进（不推翻重设计） |
| 范围优先级 | 应用外壳优先（工具栏 / 标签 / 侧栏），预览排版仅小修 |
| 结构改动 | 视觉为主，允许少量结构优化（复用已有 action，不改业务逻辑） |
| 美学走向 | 方案 2「极简退隐」—— Typora 式克制，外壳全面退后 |
| 侧栏布局 | **目录导航（TOC）固定在左侧，文件浏览器固定在右侧，两者均可隐藏** |

## 2. 硬约束（Win7 SP1 32 位兼容）

1. **零新依赖**：不引入任何新的 pip 包或 JS 库；`requirements.txt` 不变。
2. **仅使用 Qt 5.15 QSS + QPainter 自绘图标**：QSS 子集限 Qt 5.15 样式表引擎已支持的能力
   （项目现有用法即安全集）；不引入 QML、不引入 SVG 图标运行时。
3. **无动画**：QSS 无过渡能力；不引入 QPropertyAnimation（老旧 32 位机器上得不偿失）。
4. **字体**：仅用 Win7 自带字体 —— UI 用 `Segoe UI` / `Microsoft YaHei`，
   编辑器用 `Consolas`，预览标题衬线用 `Georgia` / `SimSun`（现有策略，不变）。
5. **Python 3.8 语法**：所有改动保持 `from __future__ import annotations` 模式，
   不使用 walrus / PEP 604 运行时求值 / match-case 等 3.9+ 特性。
6. **入口回归**：改动后须人工验证三种入口：无参启动、`python main.py file.md`、拖放打开。

## 3. 设计原则

- **少边框**：分隔只保留发丝级线条（hairline），去掉装饰性边框与堆叠阴影。
- **单色图标**：全部图标统一为 16px 网格、1.5px 笔触、圆角端点的线性风格；
  常态 `ink_muted`，hover 转 `ink_strong`。
- **主色克制**：松绿（accent）只出现在"当前状态"——选中标签下划线、当前模式、
  树选中指示条、开关勾选，共四处语义。
- **间距分级**：统一 4 / 8 / 12 / 16 px 梯度；圆角收敛为控件 6px、胶囊 9px、菜单 8px。

## 4. 详细改动

### 4.1 调色板微调（`app/theme_manager.py`）

- 两个主题的 `status_bg` / `status_ink` 改为与 `chrome` / `ink_muted` 一致
  （状态栏退为素色），并从调色板中删除这两个键，状态栏样式直接引用 `chrome` 系颜色。
- 其余颜色不变；`accent_soft` 继续承担选中底色的职责。

### 4.2 工具栏（`app/main_window.py` + `app/theme_manager.py`）

- 高度收窄：padding 调整为上下 5px。
- **新增 4 枚单色图标按钮**（复用已有 action，零业务改动）：
  打开（`_act_open`）、保存（`_act_save`）、导出（`_act_export_pdf`，图标按钮，
  点击直接触发 PDF 导出对话框）、主题切换（`_act_toggle_theme`）。
  按钮与模式胶囊之间用弹簧（`QWidget` + `QSizePolicy.Expanding`）隔开，
  模式胶囊保持在工具栏右侧。
- 模式胶囊 `mode_seg`：去掉外边框，仅保留 `inset` 底衬。
- QSS：`QToolBar` 去掉 `border-bottom`，仅保留与标签栏之间的一条 hairline
  （移到 QTabBar 区域管理，避免双线）。

### 4.3 图标重绘（`app/icons.py`）

- 现有图标按统一规范重绘：16px 视口、1.5px 笔触（按物理像素换算）、
  圆角端点与拐角（`Qt.RoundCap` / `Qt.RoundJoin`）。
- 新增图标：`open`（文件夹）、`save`（磁盘）、`export`（向上导出箭头）、
  `theme`（半满圆，亮暗通用）。
- 图标颜色仍由 `build_icons(palette)` 按主题重建，接口不变。

### 4.4 标签页（`app/theme_manager.py` + `app/tab_manager.py`）

- QSS：标签去左右边框与背景差异，选中态 = 2px 松绿下划线 + 字重 600 +
  `ink_strong` 文字；未选中 `ink_faint`，hover 转 `ink_muted`。
- **脏标记**：`TabManager` 标题中的 `*` 改为 `●`（琥珀色无法对单个字符上色，
  采用 QTabBar 文本 unicode 圆点 `●`，颜色随文字；视觉验收时如不满意，
  降级方案为保留 `*` 但改用更克制的字号）。实现入口仅限 `_make_title` 一处。

### 4.5 侧栏（`app/main_window.py` + `app/theme_manager.py`）

- **停靠位置交换**：`TocWidget` 的 dock 固定 `Qt.LeftDockWidgetArea`（默认可见），
  `FileTreeWidget` 的 dock 固定 `Qt.RightDockWidgetArea`（默认可见）。
  `setAllowedAreas` 收紧为各自一侧，避免用户误拖交换导致与菜单文案不符。
- 隐藏能力维持现状：视图菜单两个开关 + `show_toc` / `show_file_tree` 配置持久化，
  不新增逻辑。
- QSS：dock 标题维持小号大写字距样式；树控件选中项改为
  `accent_soft` 底 + 左侧 2px 松绿内阴影指示条
  （`QTreeView::item:selected { border-left: 2px solid accent; }`，
  QSS 在树项上支持 border-left）。
- 树分支箭头：保持现状（维持 `image: none` 的禁用处理，不新增自绘箭头）。

### 4.6 状态栏（`app/theme_manager.py`）

- QSS：`QStatusBar` 背景 `chrome`、文字 `ink_muted`、顶部 1px `hairline`；
  移除松绿整条配色。

### 4.7 滚动条与菜单（`app/theme_manager.py`）

- 滚动条宽度 11px → 8px，handle 圆角 4px，常态色再淡一级（`hairline` 与
  `scrollbar` 之间的中间值，直接复用 `scrollbar` 即可，不新增色键）。
- 菜单选中态保持 `accent_soft`；菜单 padding 微调对齐 4px 网格。

### 4.8 预览与编辑器（小修）

- `resources/css/theme-light.css` / `theme-dark.css`：仅统一 Web 端滚动条宽度为 8px
  与选区色变量引用，**排版不动**。
- `app/editor.py`：行号栏配色继续由 `get_editor_colors()` 驱动，不改代码；
  调色板中 `gutter_ink` 维持现值不变。

## 5. 改动文件清单

| 文件 | 改动性质 |
|---|---|
| `app/theme_manager.py` | 调色板微调 + QSS 全面更新（主战场） |
| `app/icons.py` | 图标重绘 + 新增 4 枚 |
| `app/main_window.py` | 工具栏补按钮；两个 dock 位置互换并锁定区域 |
| `app/tab_manager.py` | `_make_title` 脏标记 `*` → `●` |
| `resources/css/theme-light.css` | 滚动条 / 选区微调 |
| `resources/css/theme-dark.css` | 滚动条 / 选区微调 |

不改：`main.py`、`app/preview.py`、`app/vditor_pane.py`、`app/exporter.py`、
`app/file_tree.py`、`app/toc_widget.py`、`resources/css/markdown.css` 及所有 JS。

## 6. 错误处理与回归风险

- 所有改动为 QSS / QPainter / 布局层面，无文件 I/O、无异常路径变化。
- 风险点 1：QSS 对 `QTreeView::item` 的 `border-left` 在不同样式引擎下表现需人工验收，
  不生效则降级为仅 `accent_soft` 底色。
- 风险点 2：脏标记 `●` 的观感依赖字体，验收不满意则回退 `*`。
- 风险点 3：dock 锁定单侧区域后，用户无法自由拖放布局——这是有意为之
  （用户已确认布局固定），如后续有反馈再开放。

## 7. 验证计划

无自动化测试框架（项目现状），采用人工验证：

1. `python main.py` 无参启动：窗口、空状态、两侧栏位置（左 TOC / 右文件树）正确。
2. `python main.py examples\README.md`：标签打开、预览渲染、TOC 联动正常。
3. 拖放 `.md` 文件到窗口：正常打开。
4. 主题切换（Ctrl+Shift+D）：亮/暗两套外壳、图标、编辑器、预览同步刷新。
5. 侧栏开关：视图菜单分别隐藏/显示 TOC 与文件树，重启后状态保持。
6. 编辑 → 脏标记 `●` 出现；保存后消失。
7. 工具栏 4 枚新按钮功能与菜单等价。
8. `code_check`（ruff）对所有改动文件通过。

## 8. 不做的事（YAGNI）

- 不重做预览排版、不引入新主题（仍只有亮/暗两套）。
- 不加动画、不加自定义标题栏（保留系统标题栏，Win7 兼容最稳）。
- 不打包字体、不引入图标字体或 SVG 运行时。
- 不改动 Vditor 面板样式（独立第三方组件，风险收益不成比例）。
