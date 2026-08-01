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
