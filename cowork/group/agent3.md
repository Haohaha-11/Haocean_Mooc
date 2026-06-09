# agent3 留言

时间：2026-06-08

## 我已经做过的事

1. 集成了 DeepSeek 使用小助手：
   - 新增 `module_a_client/module_a/ai_help.py`。
   - 新增命令入口 `haocean ai-help`。
   - 学生端也支持 `haocean-student ai-help`。
   - 小助手知道学生端、教师端、安装、登录、提交、批改、下载、查重、反馈等常用流程。
2. 命令命名做了边界处理：
   - 正式学生命令保持 `haocean-student`。
   - `haocean` 只作为 AI 帮助入口，不再作为学生端日常命令入口。
   - `module_a_client/pyproject.toml` 中 `haocean` 指向 `module_a.ai_help:main`，`haocean-student` 指向 `module_a.main:main`。
3. DeepSeek key 没有写入仓库：
   - 运行时读取 `DEEPSEEK_API_KEY`。
   - 兼容 `HAOCEAN_DEEPSEEK_API_KEY`。
   - 可用 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_TIMEOUT_SECONDS`、`DEEPSEEK_MAX_TOKENS` 覆盖默认配置。
   - 未配置 key 或调用失败时，输出本地帮助摘要，不直接崩溃。
4. 更新学生安装脚本：
   - `install-student.sh` 会安装正式命令 `haocean-student`。
   - 同时尽量建立 `haocean` 帮助入口。
   - 如果用户本机已有非本项目的 `haocean` 文件或不同指向的 symlink，脚本会跳过，不强行覆盖。
5. 确认邮件品牌：
   - 后端默认 `MODULE_B_SYSTEM_NAME` 是 `Haocean Mooc`。
   - `module_b_server/.env` 中也是 `Haocean Mooc`。
   - 没有发现旧字符串 `Haoceanlab course` 残留。
6. 更新了相关文档：
   - `README.md`
   - `module_a_client/README.md`
   - `docs/student_usage_guide.md`
   - `docs/project_spec_and_progress.md`
7. 调整根 `Makefile`：
   - `test-a` 改为用 `module_a_client/.venv/bin/python -m pytest -q`。
   - 原因是模块 A 已经有 pytest 风格测试，`unittest discover` 跑不到这些测试。

## 已跑过的验证

- `module_a_client/.venv/bin/python -m pytest -q`
  - 25 passed
- `module_b_server/.venv/bin/python -B -m unittest discover -s tests`
  - 11 passed
- `module_c_controller/.venv/bin/python -m pytest -q`
  - 24 passed
- 根目录 `make test` 通过：
  - 模块 A：25 passed
  - 模块 B：11 passed
  - 模块 C：24 passed
- 直接验证本地兜底帮助：
  - `from module_a.ai_help import main; main(["ai-help", "--local", "怎么提交作业？"])`
  - 输出了学生端/教师端常用命令摘要。

## 风险和注意事项

1. 当前工作区仍然有大量未提交协作改动，不全是我做的；不要直接 `git add .`。
2. 我新增的主要文件：
   - `module_a_client/module_a/ai_help.py`
   - `module_a_client/tests/test_ai_help.py`
   - `cowork/group/agent3.md`
3. 我改过的主要文件：
   - `Makefile`
   - `README.md`
   - `install-student.sh`
   - `module_a_client/README.md`
   - `module_a_client/module_a/main.py`
   - `module_a_client/pyproject.toml`
   - `docs/student_usage_guide.md`
   - `docs/project_spec_and_progress.md`
4. 现有 `module_a_client/.venv` 没有重装 editable 包，所以本地 `.venv/bin/haocean` 当前不存在；重新执行安装脚本或 `pip install -e module_a_client` 后才会生成新的 console script。
5. 用户之前在对话里暴露过 DeepSeek key，不要写入任何代码、文档或聊天记录；应该让用户去后台轮换 key，再通过环境变量使用。

## 最新更新：本地 DeepSeek 配置和真实测试

时间：2026-06-08

1. 按用户要求，已把 DeepSeek 配置写入本地忽略文件：
   - `module_a_client/.env`
   - `module_b_server/.env`
2. 没有把 key 明文写入源码、README、docs 或 cowork 群聊。
3. 两个 `.env` 文件已确认被 `.gitignore` 忽略，并已收紧为 `600` 权限。
4. AI 帮助已做真实 DeepSeek 联网测试：
   - `haocean ai-help` 的底层调用返回正常。
   - 测试问题是学生如何查看作业，模型返回了 `haocean-student list`。
5. AI 查重已做真实 DeepSeek 联网测试：
   - 直接调用 `module_b_server/app/main.py` 中的 `call_deepseek_plagiarism_judge`。
   - 示例两段小代码返回 `likely_plagiarism=False`，说明真实 API 调用链正常。
6. 修复了一个测试隔离问题：
   - 因为本机 `.env` 现在有 key，`module_a_client/tests/test_ai_help.py` 的无 key 兜底测试改为显式设置空环境变量。
   - 重跑 `module_a_client/.venv/bin/python -m pytest -q tests/test_ai_help.py`，结果 `4 passed`。
7. 注意：
   - 如果模块 B 服务已经在配置前启动，需要重启服务才能读到 `module_b_server/.env` 中的 DeepSeek 配置。
   - 这个 key 已经在聊天里暴露过，建议测试完成后轮换。

## 最新更新：真实环境安装入口

时间：2026-06-09

1. 用户在真实 VM 上执行学生端安装后，`haocean-student` 仍然 `command not found`。
2. 现象显示 pip 解析到了 GitHub `main`，但 venv 里可能已有旧版 `haocean-mooc-cli==0.1.0`，由于版本号未变，console script 没被刷新，导致 `~/.local/bin/haocean-student` 指向不存在的 venv 脚本。
3. 已修改安装脚本：
   - `install-student.sh` 的 pip 安装增加 `--force-reinstall --no-cache-dir`。
   - `install-teacher.sh` 的 pip 安装增加 `--force-reinstall --no-cache-dir`。
4. 新增组合安装脚本：
   - `install-all.sh`
   - 用于同一个 Linux 用户同时安装学生端、教师端和 `haocean ai-help`。
5. 注意：
   - 这些安装脚本改动当前仍在本地工作区；真实 VM 使用 GitHub raw URL 前，需要先提交并推送。
   - 推送前的临时修复方式是在真实 VM 上手动执行 pip `--force-reinstall` 并重建 symlink。

## 给其他 agent 的建议

- 如果继续处理命令命名，请保持口径：
  - 学生日常：`haocean-student`
  - 教师日常：`haocean-teacher`
  - AI 帮助：`haocean ai-help`
- 如果改安装脚本，注意不要覆盖用户本机已有的无关 `haocean` 命令。
- 如果要提交，建议先单独审查我列出的文件，再处理其他 agent 的大块后端/教师端改动。
- 如果需要继续真实调用 DeepSeek，使用本地忽略 `.env` 或 shell 环境变量；不要把 key 提交，也不要写进文档。
