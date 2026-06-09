# agent1 留言

时间：2026-06-08

## 我已经做过的事

1. 阅读并梳理了项目整体目标：这是一个终端版课程作业管理平台，包含学生端 `haocean-student`、教师端 `haocean-teacher`、FastAPI 服务端和运维验收脚本。
2. 新增项目级 Spec：
   - `docs/project_spec_and_progress.md`
3. 新增远程 Linux 机器使用指南：
   - `docs/teacher_usage_guide.md`
   - `docs/student_usage_guide.md`
4. 新增本机工作区测试指南：
   - `docs/local_teacher_usage_guide.md`
   - `docs/local_student_usage_guide.md`
5. 调整 setup/login 逻辑：
   - 学生端 setup 增加 `Name` 和可选 `Class Code`。
   - 教师端 setup 增加 `Name`。
   - login 会读取 setup 保存的信息；配置缺失时提示补齐。教师端后续已升级为多 profile，最新口径见 `cowork/group/agent4.md`。
   - login 现在会显示入场图案。
6. 调整教师端入场图案右侧使用指南，显示四个短命令：
   - `class`
   - `select`
   - `publish`
   - `grade`
7. 教师端新增短命令交互逻辑：
   - `haocean-teacher class`：交互式创建班级。
   - `haocean-teacher select`：选择当前班级并保存到配置。
   - `haocean-teacher publish`：交互式发布作业，默认使用当前班级。
   - `haocean-teacher grade`：展示作业工作台概览后进入批改 TUI。
8. 教师端 API 客户端错误提示已改善：如果 `/health` 返回空内容或非 JSON，会显示 URL、HTTP 状态和响应预览，不再直接甩 JSON traceback。
9. 安装脚本和 README 的 Next/使用说明已改成交互式 setup 口径。

## 已跑过的验证

- `make test` 通过：
  - 模块 A：19 个测试通过。
  - 模块 B：9 个测试通过。
  - 模块 C：23 个测试通过。
- 教师端 help 已确认能看到：
  - `class`
  - `select`
  - `publish`
  - `grade`
- C 端相关测试也单独跑过一次，15 个测试通过。

## 当前重要事实

- 本地 `HEAD` 与 `origin/main` 仍是同一个提交：`8cb459b`。
- 当前工作区有大量未提交修改，GitHub 上还没有这些改动。
- 另一台机器通过安装脚本拉到的是 GitHub 旧版本，不会包含当前本地修改。
- 在本机测试当前代码时，不要直接用 `haocean-teacher` 或 `haocean-student`，应使用：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py
```

## 风险和注意事项

1. 工作区很脏，提交前不要直接 `git add .`。
2. 有几个疑似临时备份文件，提交前要确认是否保留：
   - `module_b_server/app/main_before_plagiarism_backup.py`
   - `module_b_server/app/main_fix_plagiarism_conflict_backup.py`
   - `module_b_server/app/main_fix_plagiarism_table_backup.py`
3. 模块 B 当前固定使用 `module_b_server/data/db/engine.db`，本机测试会看到历史 smoke 数据。
4. 本机新增的本地测试指南使用 `/tmp/haocean-local-teacher` 和 `/tmp/haocean-local-student`，避免污染真实配置。
5. 如果后续要让另一台机器测试，必须先整理、commit、push 到 GitHub，再重新安装。

## 给其他 agent 的建议

- 如果你们继续改教师端 CLI，请先看 `module_c_controller/controller/main.py` 中新增的 `class/select/publish/grade` 逻辑。
- 如果你们继续改登录流程，请同步看 A/C 两边的 `config.py`、`main.py` 和 `auth.py`，现在 setup/login 口径已经调整过。
- 如果你们准备提交，请先分组审查 diff，排除临时 backup 文件。
- 如果你们跑本机联调，请优先按 `docs/local_teacher_usage_guide.md` 和 `docs/local_student_usage_guide.md` 操作。
