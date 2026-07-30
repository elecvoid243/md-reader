# MD Reader 功能演示

这是一个用于测试 MD Reader 所有功能的示例文档。

## 文本格式

这是 **粗体文本**，这是 *斜体文本*，这是 `行内代码`。

这是一个 [链接示例](https://github.com)。

> 这是一段引用文字。
> 可以有多行。

---

## 列表

### 无序列表
- 第一项
- 第二项
  - 嵌套项 A
  - 嵌套项 B
- 第三项

### 有序列表
1. 步骤一
2. 步骤二
3. 步骤三

### 任务列表
- [x] 已完成的任务
- [ ] 待完成的任务
- [ ] 另一个待办

## 代码高亮

```python
def fibonacci(n: int) -> list[int]:
    """生成斐波那契数列"""
    fib = [0, 1]
    for i in range(2, n):
        fib.append(fib[i - 1] + fib[i - 2])
    return fib[:n]

print(fibonacci(10))
```

```javascript
const greet = (name) => {
    console.log(`Hello, ${name}!`);
};
greet("MD Reader");
```

## LaTeX 公式

行内公式：质能方程 $E = mc^2$，欧拉公式 $e^{i\pi} + 1 = 0$。

块级公式：

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$

$$
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}
$$

矩阵：

$$
\begin{pmatrix}
a_{11} & a_{12} \\
a_{21} & a_{22}
\end{pmatrix}
\begin{pmatrix}
x_1 \\
x_2
\end{pmatrix}
=
\begin{pmatrix}
b_1 \\
b_2
\end{pmatrix}
$$

## Mermaid 图表

### 流程图

```mermaid
graph TD
    A[开始] --> B{是否安装依赖?}
    B -->|是| C[运行 python main.py]
    B -->|否| D[pip install -r requirements.txt]
    D --> C
    C --> E[打开 .md 文件]
    E --> F[享受阅读!]
```

### 时序图

```mermaid
sequenceDiagram
    participant U as 用户
    participant E as 编辑器
    participant P as 预览引擎
    participant JS as JS渲染管线

    U->>E: 输入 Markdown
    E->>P: 文本变化(防抖300ms)
    P->>JS: renderMarkdown(text)
    JS->>JS: marked.js 解析
    JS->>JS: KaTeX 渲染公式
    JS->>JS: mermaid.js 渲染图表
    JS->>JS: highlight.js 代码高亮
    JS-->>P: 更新 DOM
    P-->>U: 显示预览
```

### 甘特图

```mermaid
gantt
    title 项目开发计划
    dateFormat  YYYY-MM-DD
    section 设计
    需求分析           :done,    des1, 2024-01-01, 7d
    架构设计           :done,    des2, after des1, 5d
    section 开发
    前端资源           :active,  dev1, after des2, 3d
    Python 模块        :         dev2, after des2, 7d
    section 测试
    功能测试           :         test1, after dev2, 5d
    发布               :         rel1, after test1, 2d
```

## 表格

| 功能 | 状态 | 优先级 |
|------|------|--------|
| 双栏编辑+预览 | ✅ 完成 | P0 |
| LaTeX 公式 | ✅ 完成 | P0 |
| Mermaid 图表 | ✅ 完成 | P0 |
| 代码高亮 | ✅ 完成 | P0 |
| 文件树 | ✅ 完成 | P1 |
| TOC 导航 | ✅ 完成 | P1 |
| 多标签页 | ✅ 完成 | P1 |
| 深色模式 | ✅ 完成 | P2 |
| 导出 HTML/PDF | ✅ 完成 | P2 |

## 图片

（此处可插入本地或网络图片）

![示例图片](https://via.placeholder.com/400x200?text=MD+Reader)

---

*由 MD Reader 渲染 — 基于 PyQt5 + QWebEngineView*
