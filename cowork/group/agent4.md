# agent4 留言

时间：2026-06-08

## 我已经做过的事

1. 教师端已支持多组本地 profile：
   - `haocean-teacher setup --profile <name>` 创建或更新一组老师身份。
   - 不传 `--profile` 时默认使用 `Teacher ID` 作为 profile 名。
   - `haocean-teacher profiles` 列出本地所有老师身份。
   - `haocean-teacher login` 会先选择 profile，再发送邮箱验证码。
   - 每个 profile 使用独立 token 文件，默认路径是 `~/.haocean-teacher/auth_tokens/<profile>`。
2. 保持旧单配置兼容：
   - 旧的 `~/.haocean-teacher/config.json` 平铺结构仍能读取。
   - 需要写入 profile 时会迁移为 `{active_profile, profiles}` 结构。
3. 修复了新 profile 复用旧身份信息的问题：
   - 创建新 profile 时不会自动套用当前 active profile 的 Name / Email。
   - 只有更新当前 active profile 时才沿用已有默认值。
4. 同步教程文档：
   - `docs/local_teacher_usage_guide.md`
   - `docs/teacher_usage_guide.md`
   - `docs/project_spec_and_progress.md`
   - `module_c_controller/README.md`
   - 根 `README.md`

## 已跑过的验证

- 模块 C 全量测试：

```bash
module_c_controller/.venv/bin/python -m pytest -q module_c_controller/tests
```

结果：`29 passed`。

- 项目级测试：

```bash
make test
```

结果：
  - 模块 A：`27 passed`
  - 模块 B：`14 tests OK`
  - 模块 C：`29 passed`

- 真实本地 CLI profile smoke：

```bash
HAOCEAN_TEACHER_HOME=/tmp/haocean-profile-test-20260608 \
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py setup \
  --profile local-t1 --teacher-id T101 --name TeacherOne --email t1@example.com \
  --api-base-url http://127.0.0.1:8000

HAOCEAN_TEACHER_HOME=/tmp/haocean-profile-test-20260608 \
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py setup \
  --profile local-t2 --teacher-id T102 --name TeacherTwo --email t2@example.com \
  --api-base-url http://127.0.0.1:9000

HAOCEAN_TEACHER_HOME=/tmp/haocean-profile-test-20260608 \
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py profiles
```

输出能看到 `local-t1` 和 active 的 `local-t2`。

## 风险和注意事项

1. 当前工作区仍有大量未提交协作改动，不要直接 `git add .`。
2. 教师端多 profile 是本地配置层改动，不改变服务端认证 API。
3. 如果文档里需要手动读取老师 token，新的默认路径是：

```bash
~/.haocean-teacher/auth_tokens/<profile>
```

本机指南示例使用：

```bash
/tmp/haocean-local-teacher/auth_tokens/local-t001
```

4. 学生端仍是单本地配置；本次只处理教师端多 profile。

## 追加修复：setup 改 Teacher ID 时必须补 Name / Email

时间：2026-06-08

用户复测时发现：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py setup
Teacher ID [Test_Local] : Hao_test_2
```

旧逻辑会直接复用当前 active profile 的 Name / Email 并创建 `Hao_test_2`，看起来只输入 Teacher ID 就通过了。

已修复：

- 不传 `--profile` 且输入的 Teacher ID 与当前 active profile 不同时，视为新 profile。
- 新 profile 必须重新输入 Name 和 Email。
- 只有 Teacher ID 没变，或者显式更新当前 profile 时，才复用旧 Name / Email 默认值。

新增回归测试：

- `test_teacher_setup_changed_teacher_id_without_profile_prompts_for_new_identity`

验证：

```bash
module_c_controller/.venv/bin/python -m pytest -q module_c_controller/tests
```

结果：`30 passed`。

## 追加修复：互评开关前移到发布作业阶段

时间：2026-06-08

用户确认流程时提出：互评是否开启应该在作业发表阶段决定。

已处理：

- `POST /v1/assignments` 支持 `peer_review_enabled`、`teacher_weight`、`peer_weight`，开启后 `peer_review_stage` 初始为 `submission`。
- 教师端 `publish` 增加 `--peer-review` / `--no-peer-review`，交互式发布会询问 `Peer Review`；`assignment create` 也支持 `--peer-review`。
- 提交结束后仍通过 stage API 切到 `peer_review`，再自动分配互评任务。
- 文档已同步：`docs/api_spec.md`、`docs/local_teacher_usage_guide.md`、`docs/teacher_usage_guide.md`、`docs/project_spec_and_progress.md`、`module_b_server/README.md`、`module_c_controller/README.md`、`module_c_controller/docs/module_b_api_contract.md`、根 `README.md`。

验证：

```bash
module_c_controller/.venv/bin/python -m pytest module_c_controller/tests
```

结果：`31 passed`。

```bash
cd module_b_server
../module_b_server/.venv/bin/python -m pytest tests
```

结果：`14 passed`。

## 追加修复：班级名唯一和选择解析

时间：2026-06-08

用户明确班级名不能重复。已处理：

- 模块 B 创建班级时拒绝同一老师名下重复 `class_name`，不同老师仍可使用相同班级名。
- 教师端 `select` 列表改为显示 `No/Class ID/Class Name/Course/Join Code`，选择时只接受左侧序号。
- `select` 成功后会打印完整班级信息，不再只打印一个 `class_id`。
- 文档已同步班级名唯一约束。

验证：

```bash
cd module_b_server
../module_b_server/.venv/bin/python -m pytest tests
```

结果：`15 passed`。

```bash
module_c_controller/.venv/bin/python -m pytest module_c_controller/tests
```

结果：`34 passed`。

## 追加修复：deadline 按北京时间解析

时间：2026-06-08

用户指出 deadline 不应只作为字符串保存，并确认业务时间应使用北京时间。

已处理：

- 模块 B `now_str()` 改为使用 `Asia/Shanghai`。
- 教师端 `publish` / `assignment create` 会把 deadline 规范化为 `YYYY-MM-DD HH:MM:SS`。
- 支持 `6.10`、`6.10 18:30`、`2026-06-10`、`2026-06-10 18:30`。
- 只写日期时默认 `23:59:59`；写到分钟时默认秒为 `00`。

验证：

```bash
module_c_controller/.venv/bin/python -m pytest module_c_controller/tests
cd module_b_server
../module_b_server/.venv/bin/python -m pytest tests
```

结果：

- Module C：`35 passed`
- Module B：`16 passed`

## 追加修复：互评默认每人两份

时间：2026-06-08

用户要求互评默认每个学生评 2 份；如果学生太少则相互评。

已处理：

- 自动分配互评任务改为按学生去重，使用该学生该作业下最新一次提交。
- 默认每个学生分配 2 份互评任务。
- 如果只有 2 个学生，则每人评对方 1 份。
- 如果只有 1 个学生，仍返回错误，无法分配互评任务。
- 自动分配响应新增 `student_count` 和 `reviews_per_student`。

验证：

```bash
cd module_b_server
../module_b_server/.venv/bin/python -m pytest tests
```

结果：`16 passed`。

## 追加修复：互评权重只问教师权重

时间：2026-06-08

用户指出交互式发布已输入 `Teacher Score Weight` 后，`Peer Score Weight` 应自动为 `1 - teacher_weight`。

已处理：

- `publish` 交互式开启互评后只询问 `Teacher Score Weight`。
- 未显式传 `--peer-weight` 时，`peer_weight = 1 - teacher_weight`。
- `--peer-weight` 仍保留为高级覆盖参数。
- 示例文档改为只展示 `--teacher-weight`。

验证：

```bash
module_c_controller/.venv/bin/python -m pytest module_c_controller/tests
```

结果：`33 passed`。
