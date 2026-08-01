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
