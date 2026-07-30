# MD Reader — Markdown 阅读器

一款基于 **PyQt5 + QWebEngineView** 的桌面 Markdown 阅读器 / 编辑器，仿照 Typora 的阅读体验，支持 Windows 7+。

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 双栏编辑 + 实时预览 | 左侧编辑 Markdown 源码，右侧实时渲染预览 |
| LaTeX 公式 | 行内 `$...$` 和块级 `$$...$$`，由 KaTeX 渲染 |
| Mermaid 图表 | 流程图、时序图、甘特图等，由 mermaid.js 渲染 |
| 代码高亮 | 100+ 语言语法高亮，由 highlight.js 驱动 |
| 文件树浏览 | 侧边栏浏览文件夹，双击打开 .md 文件 |
| TOC 目录导航 | 自动提取标题层级，点击跳转 |
| 多标签页 | 同时打开多个文件，支持拖拽排序 |
| 深色 / 浅色主题 | 一键切换，编辑器与预览同步 |
| 滚动同步 | 编辑区与预览区按比例同步滚动 |
| 导出 HTML / PDF | 将渲染结果导出为独立 HTML 或 PDF 文件 |
| 拖放打开 | 直接拖拽 .md 文件到窗口打开 |
| 多编码支持 | 自动探测 UTF-8 / GBK / GB2312 等编码 |

## 📋 系统要求

- **操作系统**: Windows 7 / 8 / 10 / 11
- **Python**: 3.8.x（最后支持 Win7 的版本）
- **内存**: 建议 4GB+（QWebEngineView 内嵌 Chromium）

## 🚀 快速开始

```bash
# 1. 确保使用 Python 3.8
python --version

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python main.py

# 或直接打开一个文件
python main.py README.md
```

## 📁 项目结构

```
md-reader/
├── main.py                 # 入口文件
├── requirements.txt        # Python 依赖
├── app/
│   ├── main_window.py      # 主窗口（菜单/工具栏/布局）
│   ├── editor.py           # Markdown 编辑器（行号+语法高亮）
│   ├── preview.py          # 预览引擎（QWebEngineView + JS Bridge）
│   ├── file_tree.py        # 文件树侧边栏
│   ├── toc_widget.py       # TOC 目录导航
│   ├── tab_manager.py      # 多标签页管理
│   ├── theme_manager.py    # 主题管理（亮/暗）
│   ├── exporter.py         # 导出 HTML / PDF
│   └── config.py           # 配置持久化
└── resources/
    ├── html/preview.html   # 预览页模板
    ├── js/                 # JS 库（marked/katex/mermaid/highlight）
    └── css/                # 样式（排版/主题/代码高亮）
```

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+O` | 打开文件 |
| `Ctrl+Shift+O` | 打开文件夹 |
| `Ctrl+S` | 保存 |
| `Ctrl+Shift+S` | 另存为 |
| `Ctrl+N` | 新建标签页 |
| `Ctrl+W` | 关闭标签页 |
| `Ctrl+Shift+E` | 切换文件树 |
| `Ctrl+Shift+T` | 切换目录导航 |
| `Ctrl+Shift+D` | 切换深色/浅色主题 |

## 🔧 技术架构

```
用户编辑 Markdown
       ↓
  EditorPane (QPlainTextEdit)
       ↓ 防抖 300ms
  Python 读取文本
       ↓ QWebChannel
  JS 渲染管线:
    marked.js → KaTeX → mermaid.js → highlight.js
       ↓
  PreviewPane (QWebEngineView / Chromium)
```

- **渲染全部在 JS 端完成**，Python 端只负责传递文本和接收 TOC 数据
- **JS 库全部本地打包**，无需联网即可使用
- 本质上与 Typora 的技术路线一致（Electron = Chromium + Node.js），我们用 PyQt5 替代 Electron

## 📦 打包为 EXE（可选）

```bash
pip install pyinstaller
pyinstaller --name "MDReader" --windowed --onefile main.py
```

> 注意：PyInstaller 打包 QWebEngineView 应用体积较大（~200MB），这是 Chromium 内核的固有开销。

## 📄 License

MIT
