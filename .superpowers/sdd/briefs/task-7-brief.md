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
