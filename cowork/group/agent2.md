# agent2 留言

时间：2026-06-08

## 我已经做过的事

1. 梳理了当前查重逻辑：
   - 自动查重：学生提交后写入 `plagiarism_reports`，老师端原 `plagiarism` 命令读取这张表。
   - 手动查重：`POST /v1/plagiarism/check` 写入 `plagiarism_check_reports`。
2. 在模块 B 引入 DeepSeek AI 查重：
   - `method=token`：保持原本本地 token 查重。
   - `method=hybrid`：推荐模式，先本地 token 预筛，再把高风险提交对发给 DeepSeek。
   - `method=ai`：仍先排序/限流，再走 DeepSeek；如需全量 AI，可把 `ai_prefilter=0` 并调大 `ai_limit`。
3. DeepSeek 配置改为环境变量读取：
   - `DEEPSEEK_API_KEY` 或 `MODULE_B_DEEPSEEK_API_KEY`
   - `DEEPSEEK_MODEL`
   - `DEEPSEEK_PREFILTER_SIMILARITY`
   - `DEEPSEEK_MAX_CANDIDATE_PAIRS`
   - `DEEPSEEK_MAX_CHARS_PER_SUBMISSION`
4. 已把 DeepSeek key 配到本地 `module_b_server/.env`。该文件被 `.gitignore` 忽略，不应提交；不要在群聊、日志、commit message 中写出 key。
5. 默认模型使用 `deepseek-v4-flash`，并关闭 V4 thinking 模式，优先保证批量查重速度和成本可控。
6. 教师端新增触发命令：

```bash
haocean-teacher plagiarism home_001 --check --method hybrid --threshold 0.75
```

不加 `--check` 时，仍保持原来只查看自动查重报告。

## 已跑过的验证

- 模块 B：`11 passed`，只有 FastAPI `on_event` deprecation warning。
- 模块 C：`24 passed`。
- `git diff --check` 通过。
- 模块 B / C 关键文件 `py_compile` 通过。
- `haocean-teacher plagiarism --help` 已确认能看到：
  - `--check`
  - `--method {token,hybrid,ai}`
  - `--threshold`
  - `--ai-prefilter`
  - `--ai-limit`

## 风险和注意事项

1. 运行中的模块 B 服务需要重启后才会重新读取 `.env` 里的 DeepSeek key。
2. 目前 AI 查重不会自动在每次学生提交时调用 DeepSeek；默认只在老师触发 `/v1/plagiarism/check` 或 CLI `--check` 时调用，避免提交接口变慢。
3. `hybrid` 默认只复核本地相似度较高的候选对，效率高，但极端改写可能漏掉；需要更严格时可降低 `ai_prefilter` 或增大 `ai_limit`。
4. 当前工作区已有大量未提交改动，提交前要按模块审查 diff，避免把备份文件、运行数据或 secret 带进 Git。

## 给其他 agent 的建议

- 继续改查重时优先看：
  - `module_b_server/app/main.py`
  - `module_c_controller/controller/api_client.py`
  - `module_c_controller/controller/main.py`
  - `module_b_server/tests/test_plagiarism_and_stats.py`
  - `module_c_controller/tests/test_api_client.py`
- 不要把 `module_b_server/.env` 加入版本控制。
- 如果要做真实联调，先重启模块 B，再用老师端命令触发 `--check`。

## 追加记录：学生端互评任务列表

时间：2026-06-08

- 已补齐学生端互评任务查看：
  - `haocean-student peer-review`：列出当前学生待互评任务。
  - `haocean-student peer-review --assignment-id home_001`：按作业筛选任务。
  - `haocean-student peer-review <submission_id> <score> --comment "..."`：保留原提交互评分用法。
- 新增 `ModuleBClient.list_peer_review_tasks()`，调用后端 `GET /v1/peer-review/tasks/my`。
- 已跑验证：
  - 模块 A：`26 passed`
  - `py_compile` 通过
  - `haocean-student peer-review --help` 输出正常
  - `git diff --check` 通过

## 追加记录：老师端查看已发布作业

时间：2026-06-09

- 已补齐老师端作业列表命令：

```bash
haocean-teacher assignment list
```

- 该命令调用后端 `GET /v1/assignments/open`，在 teacher token 下会返回该老师创建或自己班级下的开放作业。
- 输出字段包括：
  - Assignment
  - Title
  - Class
  - Weight
  - Deadline
  - Created
  - Status
- 已跑验证：
  - 模块 C：`42 passed`
  - `py_compile` 通过
  - `haocean-teacher assignment --help` 已显示 `list`
  - `git diff --check` 通过
