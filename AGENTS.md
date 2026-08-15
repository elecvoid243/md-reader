# AGENTS.md

本文件为在此代码库中工作的编程代理提供指引。请在贡献代码前仔细阅读。

## 项目概述

**MD Reader** 是一款基于 **PyQt5 + QWebEngineView** 的桌面 Markdown 阅读器 / 编辑器，仿照 Typora 的阅读体验，支持 Windows 7+。

主要技术栈:
- Python 3.8.x(最后支持 Win7 的版本)
- PyQt5 (>=5.15,<6.0)
- PyQtWebEngine (>=5.15,<6.0)
- 前端通过 QWebEngineView 内嵌 Chromium 渲染，使用 marked.js / highlight.js / katex / mermaid 等 JS 库

## 构建 / 安装命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用(开发模式)
python main.py

# 启动应用并直接打开某个 Markdown 文件
python main.py README.md
```

本项目**没有使用** MSBuild、setuptools、pyproject.toml 等构建系统，也未配置任何编译步骤。"构建"实际上仅指依赖安装。

## Lint / 测试命令

当前仓库**未配置**任何 linter(flake8 / pylint / ruff 等)和测试框架(unittest / pytest 等)。在引入新代码时:
- 如添加 linter，请同时在 `requirements.txt` 中声明开发依赖
- 如添加测试，请使用 `pytest`，并在下方补充对应命令

### 运行单个测试(模板，待 pytest 接入后启用)

```bash
# 暂未配置，预期格式如下:
# pytest tests/test_<module>.py::TestClass::test_method -v
```

## 项目结构

```
md-reader/
├── main.py                 # 程序入口
├── requirements.txt        # Python 依赖
├── app/                    # 应用核心代码
│   ├── __init__.py
│   ├── config.py           # 配置(路径、常量、QSS 等)
│   ├── editor.py           # 编辑器组件(QPlainTextEdit 子类)
│   ├── exporter.py         # HTML / PDF 导出
│   ├── file_tree.py        # 侧边栏文件树
│   ├── icons.py            # 图标加载与缓存
│   ├── main_window.py      # 主窗口(QMainWindow)
│   ├── preview.py          # 预览面板(QWebEngineView 封装)
│   ├── tab_manager.py      # 多标签页管理
│   ├── theme_manager.py    # 深色 / 浅色主题切换
│   ├── toc_widget.py       # 目录导航控件
│   └── vditor_pane.py      # Vditor 集成面板
├── resources/              # 静态资源
│   ├── css/                # 样式表
│   ├── html/               # 预览 HTML 模板
│   ├── icons/              # 图标
│   ├── js/                 # 前端 JS(marked / katex / mermaid 等)
│   └── vditor/             # Vditor 资源
├── docs/                   # 文档
├── examples/               # 示例 Markdown
└── README.md
```

## 代码风格指南

### 语言与版本
- Python **3.8** 兼容(不可使用 walrus `:=`、PEP 604 `X | Y` 联合类型语法、 `list[int]` 内置泛型等 3.9+ 特性)
- 所有源文件头部无需添加编码声明，默认 UTF-8

### 导入 (Imports)
- 导入顺序: 标准库 → 第三方 → 本地应用模块，三组之间用空行分隔
- 使用 **绝对导入**，例如 `from app.config import RESOURCE_DIR`
- 避免 `from module import *`
- 第三方依赖仅限 `PyQt5` / `PyQtWebEngine`，新依赖须评估是否真的必要并补充到 `requirements.txt`

```python
# 正确示例
import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QMainWindow

from app.config import RESOURCE_DIR
```

### 格式化
- 缩进: **4 空格**，不使用 Tab
- 行长: 建议不超过 **120 字符**
- 文件末尾保留 **一个** 空行
- 字符串引号: 优先使用 **双引号** `"`，仅在字符串本身包含双引号时使用单引号
- 中文 / 英文混排时，建议在英文与中文之间保留一个空格（如 `"打开 文件"`），但不强求

### 类型注解
- 鼓励使用类型注解，但**必须兼容 Python 3.8**
- 使用 `typing` 模块：`List`, `Dict`, `Optional`, `Tuple` 等，而非 PEP 585 / 604 内建泛型
- 公共方法签名必须标注；内部私有方法建议标注

```python
from typing import List, Optional

def open_files(self, paths: List[str]) -> Optional[str]:
    ...
```

### 命名约定
| 类别 | 规范 | 示例 |
|------|------|------|
| 模块名 | `snake_case` | `file_tree.py` |
| 类名 | `PascalCase` | `MainWindow`, `TabManager` |
| 函数 / 方法 | `snake_case` | `load_file`, `update_preview` |
| 变量 | `snake_case` | `current_path`, `is_dirty` |
| 常量 | `UPPER_SNAKE_CASE` | `RESOURCE_DIR`, `DEFAULT_THEME` |
| 私有成员 | 前缀单下划线 | `_internal_state` |
| Qt 控件 | 用途前缀 + 类型 | `self.btn_open`, `self.tree_files`, `self.editor` |
| 信号 | 动词过去式 / 名词 | `contentChanged`, `fileOpened` |
| 槽函数 | `on_<信号源>_<信号名>` 或 `slot_<动作>` | `on_editor_text_changed` |

### 类与结构
- 每个 Qt 窗口 / 组件类建议拆分为: `__init__` → `_init_ui` → `_init_signals` → `_init_state` → 业务方法
- 信号类属性集中在类顶部，紧随 `class` 声明之后
- 大型 UI 构建方法应拆分为多个以 `_build_xxx` 开头的私有方法
- 涉及资源路径加载，统一通过 `app.config` 中的常量获取，避免硬编码

### 错误处理
- GUI 顶层使用 `try / except` 捕获，避免崩溃；向用户弹出 `QMessageBox`
- 文件 I/O、编码探测等可能失败的操作必须处理异常；不要用裸 `except:`，至少指定异常类型
- 关键的逻辑分支(如编码解码失败回退)需记录日志(`print` 或后续引入 `logging`)
- 抛出异常时附带上下文信息，便于排查

```python
try:
    with open(path, "r", encoding=detected_encoding) as f:
        text = f.read()
except (OSError, UnicodeDecodeError) as e:
    QMessageBox.warning(self, "打开失败", f"无法读取文件:\n{e}")
    return
```

### 资源与路径
- 资源路径通过 `app.config` 模块中的常量访问，**禁止**在业务代码中写 `os.path.join("resources", ...)` 之类的硬编码
- 跨平台兼容: 使用 `pathlib.Path` 或 `os.path.join`，不要手动拼接 `/` 或 `\`
- 加载的 HTML / CSS / JS 优先使用 `QWebEngineView.setHtml()` 或 `QUrl.fromLocalFile()` 注入

### 线程与异步
- QWebEngineView 回调通过 `QObject` 信号跨线程通信，**不要**在非主线程直接操作 Qt 控件
- 长任务(大文件解析、PDF 导出等)建议使用 `QThread` 或 `QThreadPool`，避免阻塞 UI

### 主题 / 样式
- 颜色、字体、间距等视觉常量统一收敛在 `app/theme_manager.py` 与 `app/config.py`
- 切换主题需同步刷新: 编辑器样式、预览 HTML、CSS、图标等所有相关模块

### 国际化与编码
- 源码字符串仅使用 ASCII 或中文 UTF-8
- 读取用户 Markdown 文件时需做编码探测(UTF-8 → GBK → GB2312 回退)
- 写入文件默认 UTF-8，可选 `utf-8-sig` 兼容 BOM

### Git 提交建议
- 提交信息使用中文，格式: `<类型>: <简短描述>`，例如 `修复: 文件树展开后折叠状态丢失`
- 类型: `新增` / `修复` / `重构` / `文档` / `样式` / `测试`
- 一次提交只做一件事，避免把功能与重构混在一起

## 注意事项

- 此应用面向 **Windows 7+**，任何依赖升级都需确认是否兼容 Win7
- PyQt5 5.15 是最后支持 Win7 的版本，**禁止**升到 PyQt6
- `resources/` 下的 JS 库体积较大(mermaid / highlight.js / katex)，请勿在 PR 中无意义升级版本；如确需升级，需附上体积、性能、对照测试说明
- 修改 `app/config.py` 中的路径常量前，请确认所有引用方已同步更新
- 任何对 `main.py` 入口逻辑的改动都需手动验证: 无参数启动、`python main.py file.md`、拖放打开 三种入口都能正常工作
