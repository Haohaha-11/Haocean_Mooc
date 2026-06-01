# 跨平台课程管理终端项目工作文档

本文档是当前项目后续开发、联调、验收和答辩准备的权威工作依据。内容基于仓库中已经存在的需求文档、模块 B 服务端实现、模块 C 控制端实现、测试文件和交接文档整理。

未在本文档确认的字段、状态、路径和接口，不得作为模块间契约使用。

## 1. 当前仓库事实

### 1.1 有效输入文件

当前用于制定工作文档的有效文件范围：

- `/Hao/gongchuang/阅读/需求文档/task-specifications.md`
- `/Hao/gongchuang/阅读/需求文档/collaboration-and-api-development-guidelines.md`
- `/Hao/gongchuang/docs/api_spec.md`
- `/Hao/gongchuang/module_b_server/app/main.py`
- `/Hao/gongchuang/module_b_server/README.md`
- `/Hao/gongchuang/module_b_server/scripts/smoke_test.sh`
- `/Hao/gongchuang/module_c_controller/controller/*.py`
- `/Hao/gongchuang/module_c_controller/tests/*.py`
- `/Hao/gongchuang/module_c_controller/docs/*.md`
- `/Hao/gongchuang/module_c_controller/.env.example`

以下文件属于依赖、缓存、数据库或生成物，不作为接口契约来源：

- `.venv/`
- `__pycache__/`
- `.pytest_cache/`
- `data/*.db`
- `data/db/engine.db`
- PDF 原件

### 1.2 已确认的不一致点

| 冲突点 | 已确认事实 | 后续统一口径 |
| --- | --- | --- |
| 作业 ID 字段 | 需求示例曾使用 `task_id`，模块 B 真实代码使用 `assignment_id` | 统一使用 `assignment_id` |
| 校验字段 | 需求示例曾使用 `hash`，模块 B 真实代码使用 `md5` | 统一使用 `md5` |
| 批改动作 | 模块 C 交接文档使用 `APPROVE`，模块 B 真实代码使用 `GRADE` | 正式接口统一使用 `GRADE` |
| 批改后状态 | 模块 C Mock 使用 `approved`，模块 B 真实代码使用 `graded` 或 `rejected` | 正式服务状态统一使用 `pending`、`graded`、`rejected` |
| 待批改接口 | 需求文档提到 `/list/pending`，模块 B 真实代码提供 `/v1/submissions/pending` | 统一使用 `/v1/submissions/pending` |
| 模块 C 数据源 | 当前模块 C 读取本地 SQLite Mock，不调用模块 B HTTP API | 正式集成时新增 API 数据访问层替换 Mock |
| 错误响应结构 | 成功响应是顶层 `code/message/payload`，FastAPI 业务错误当前包在 `detail` 中 | 文档必须明确区分成功响应和当前错误响应 |
| 总 API 文档 | `/Hao/gongchuang/docs/api_spec.md` 当前内容不完整 | 本文档先作为权威依据，后续可拆分 API 专章回填到 `api_spec.md` |

## 2. 项目目标

项目目标是实现一个跨平台课程管理终端系统，覆盖作业发布、学生端无感提交、服务端校验归档、教师端终端批改、Markdown 反馈回传和最终一键验收。

核心验收链路：

1. 教师或助教通过模块 C 或脚本发布作业到模块 B。
2. 模块 A 获取开放作业列表。
3. 学生在本地工作区完成作业。
4. 模块 A 监控到文件稳定后自动打包、计算 MD5，并上传到模块 B。
5. 模块 B 重新计算 MD5，校验一致后归档文件并写入 SQLite。
6. 模块 C 查询待批改提交。
7. 教师或助教在 TUI 中评分并填写评语。
8. 模块 B 生成 Markdown 反馈并更新提交状态。
9. 模块 A 拉取反馈并展示或保存给学生。

## 3. 模块职责

### 3.1 模块 A：无感采集与客户端

当前仓库尚未发现模块 A 代码。模块 A 后续必须实现：

- 在学生 Ubuntu 环境后台运行。
- 监控作业工作区文件变化。
- 对频繁保存实现防抖，建议文件停止变化 3 秒后再触发打包。
- 将作业目录打包为压缩包。
- 计算压缩包 MD5。
- 调用模块 B 的开放作业、提交作业、查询反馈接口。
- 所有路径必须来自配置或相对项目根目录，不允许硬编码 `/home/username/...`。

### 3.2 模块 B：通信中枢与数据库

模块 B 已存在 FastAPI 实现，路径为 `/Hao/gongchuang/module_b_server/app/main.py`。

模块 B 当前负责：

- 初始化 SQLite 数据库。
- 维护 `assignments` 和 `submissions` 两张表。
- 提供作业发布接口。
- 提供开放作业查询接口。
- 接收学生作业上传。
- 重新计算 MD5 并拒绝损坏文件。
- 将合法提交保存到 `data/submissions/`。
- 提供待批改提交列表。
- 接收批改结果。
- 生成 Markdown 反馈文件。
- 提供学生反馈查询接口。

模块 B 是正式接口事实来源。

### 3.3 模块 C：审批终端与反馈闭环

模块 C 已存在 Textual TUI 和本地 SQLite Mock 实现，路径为 `/Hao/gongchuang/module_c_controller`。

模块 C 当前已实现：

- `pending`、`approved`、`all` 三种本地视图。
- `j/k` 上下选择。
- `Enter` 进入批改弹窗。
- `Ctrl+s` 提交批改。
- 本地生成 Markdown 反馈。
- 本地 SQLite 状态从 `pending` 更新为 `approved`。
- 单元测试覆盖数据库、配置、反馈生成和批改流程。

模块 C 当前未调用模块 B HTTP API。正式集成时必须新增数据访问层，例如 `controller/api_client.py`，并把本地 Mock 字段映射到模块 B 的正式接口字段。

### 3.4 模块 D：异常兜底与一键部署

当前仓库尚未发现模块 D 代码。模块 D 后续必须实现：

- 一键安装和验收脚本，优先使用 `Makefile`。
- 模块 B、模块 C、后续模块 A 的自动化测试入口。
- 断网、MD5 错误、非法字段、重复提交、重复批改等异常测试。
- 统一日志规范。
- 干净 Ubuntu 环境下的最终验收流程。

## 4. 统一接口规范

### 4.1 基础约定

- 模块间字段命名统一使用 `snake_case`。
- 请求 JSON 统一包含 `action`、`timestamp`、`payload`。
- 成功响应统一使用 `code`、`message`、`payload`。
- 当前模块 B 业务错误通过 `HTTPException` 返回，响应体格式为 `{"detail": {"code": 400, "message": "..."}}`。
- 文件上传接口使用 `multipart/form-data`，其中 `metadata` 是 JSON 字符串，`file` 是压缩包文件。
- 时间字段当前模块 B 使用本地时间字符串，例如 `YYYY-MM-DD HH:MM:SS`；模块 C Mock 使用 ISO 8601。正式联调时不得混用同一字段语义，建议后续统一为 ISO 8601 UTC。

### 4.2 状态定义

正式服务端状态以模块 B 为准：

| 状态 | 所属对象 | 含义 |
| --- | --- | --- |
| `open` | assignment | 作业开放，学生可以提交 |
| `pending` | submission | 提交已接收，等待批改 |
| `graded` | submission | 已批改且通过 |
| `rejected` | submission | 已批改但打回或拒绝 |

模块 C 当前本地 Mock 中的 `approved` 只允许作为 TUI 本地展示状态。接入模块 B 后，`approved` 视图应映射到服务端的 `graded` 状态。

### 4.3 成功响应格式

```json
{
  "code": 200,
  "message": "operation message",
  "payload": {}
}
```

### 4.4 当前错误响应格式

```json
{
  "detail": {
    "code": 400,
    "message": "error message"
  }
}
```

后续如需顶层错误响应，必须在模块 B 增加统一异常处理器后再修改文档和测试。

## 5. 模块 B 正式 API 契约

模块 B 默认服务地址：

```text
http://127.0.0.1:8000
```

### 5.1 健康检查

```http
GET /health
```

成功响应字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | 固定为 `200` |
| `message` | string | 服务运行状态 |
| `db_path` | string | 当前 SQLite 数据库路径 |
| `time` | string | 服务端当前时间 |

### 5.2 创建作业

```http
POST /v1/assignments
Content-Type: application/json
```

请求：

```json
{
  "action": "CREATE_ASSIGNMENT",
  "timestamp": 1760000000,
  "payload": {
    "teacher_id": "T001",
    "assignment_id": "home_001",
    "title": "Homework 1",
    "description": "Finish the required exercise.",
    "deadline": "2026-06-01 23:59:59"
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "assignment created",
  "payload": {
    "assignment_id": "home_001",
    "title": "Homework 1",
    "status": "open"
  }
}
```

约束：

- `action` 必须为 `CREATE_ASSIGNMENT`。
- `assignment_id` 是主键，不允许重复。
- `teacher_id` 会写入数据库字段 `created_by`。

### 5.3 查询开放作业

```http
GET /v1/assignments/open
```

成功响应：

```json
{
  "code": 200,
  "message": "open assignments returned",
  "payload": {
    "assignments": [
      {
        "assignment_id": "home_001",
        "title": "Homework 1",
        "description": "Finish the required exercise.",
        "deadline": "2026-06-01 23:59:59",
        "created_by": "T001",
        "created_at": "2026-05-27 10:00:00",
        "status": "open"
      }
    ]
  }
}
```

### 5.4 提交作业

```http
POST /v1/submissions
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | string | JSON 字符串 |
| `file` | file | 作业压缩包 |

`metadata` 内容：

```json
{
  "action": "SUBMIT",
  "timestamp": 1760000100,
  "payload": {
    "student_id": "2024001",
    "assignment_id": "home_001",
    "md5": "abc123...",
    "file_name": "2024001_home_001.tar.gz"
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "submission accepted",
  "payload": {
    "submission_id": 1,
    "student_id": "2024001",
    "assignment_id": "home_001",
    "file_name": "2024001_home_001.tar.gz",
    "md5": "abc123...",
    "status": "pending",
    "archive_path": "/Hao/gongchuang/module_b_server/data/submissions/2024001/home_001/1760000100_2024001_home_001.tar.gz"
  }
}
```

约束：

- `action` 必须为 `SUBMIT`。
- `assignment_id` 必须存在。
- 作业状态必须为 `open`。
- 模块 B 会重新计算文件 MD5。
- 如果实际 MD5 与 `metadata.payload.md5` 不一致，提交被拒绝。
- 上传文件先写入 `data/tmp/`，校验成功后移动到 `data/submissions/{student_id}/{assignment_id}/`。
- 文件名通过 `Path(name).name` 去掉路径部分，防止路径穿越。

### 5.5 查询待批改提交

```http
GET /v1/submissions/pending
```

成功响应：

```json
{
  "code": 200,
  "message": "pending submissions returned",
  "payload": {
    "submissions": [
      {
        "submission_id": 1,
        "student_id": "2024001",
        "assignment_id": "home_001",
        "file_name": "2024001_home_001.tar.gz",
        "file_path": "/Hao/gongchuang/module_b_server/data/submissions/2024001/home_001/1760000100_2024001_home_001.tar.gz",
        "md5": "abc123...",
        "submit_time": "2026-05-27 10:10:00",
        "status": "pending"
      }
    ]
  }
}
```

模块 C 正式接入时应使用该接口渲染待批改列表。

### 5.6 提交批改结果

```http
POST /v1/submissions/grade
Content-Type: application/json
```

请求：

```json
{
  "action": "GRADE",
  "timestamp": 1760000200,
  "payload": {
    "submission_id": 1,
    "teacher_id": "T001",
    "score": 95,
    "comment": "完成较好，结构清晰。",
    "status": "graded"
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "submission graded",
  "payload": {
    "submission_id": 1,
    "student_id": "2024001",
    "assignment_id": "home_001",
    "score": 95,
    "status": "graded",
    "feedback_path": "/Hao/gongchuang/module_b_server/data/feedback/2024001/home_001/submission_1_feedback.md"
  }
}
```

约束：

- `action` 必须为 `GRADE`。
- `score` 必须在 0 到 100 之间。
- `status` 只能为 `graded` 或 `rejected`。
- 模块 B 会生成 Markdown 反馈文件。
- 当前模块 B 未强制限制只能批改 `pending` 提交。后续应补充该校验，避免重复批改覆盖结果。

### 5.7 查询学生反馈

```http
GET /v1/feedback/{student_id}
```

成功响应：

```json
{
  "code": 200,
  "message": "feedback returned",
  "payload": {
    "student_id": "2024001",
    "feedback": [
      {
        "submission_id": 1,
        "student_id": "2024001",
        "assignment_id": "home_001",
        "file_name": "2024001_home_001.tar.gz",
        "submit_time": "2026-05-27 10:10:00",
        "status": "graded",
        "score": 95,
        "comment": "完成较好，结构清晰。",
        "feedback_path": "/Hao/gongchuang/module_b_server/data/feedback/2024001/home_001/submission_1_feedback.md",
        "feedback_markdown": "# 作业反馈\n..."
      }
    ]
  }
}
```

约束：

- 只返回状态为 `graded` 或 `rejected` 的提交。
- 如果反馈文件不存在，`feedback_markdown` 当前返回空字符串。

## 6. 数据库模型

### 6.1 模块 B `assignments`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `assignment_id` | TEXT PRIMARY KEY | 作业 ID |
| `title` | TEXT NOT NULL | 作业标题 |
| `description` | TEXT | 作业说明 |
| `deadline` | TEXT | 截止时间 |
| `created_by` | TEXT | 创建教师 ID |
| `created_at` | TEXT NOT NULL | 创建时间 |
| `status` | TEXT NOT NULL DEFAULT `open` | 作业状态 |

### 6.2 模块 B `submissions`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `submission_id` | INTEGER PRIMARY KEY AUTOINCREMENT | 提交 ID |
| `student_id` | TEXT NOT NULL | 学生 ID |
| `assignment_id` | TEXT NOT NULL | 作业 ID |
| `file_name` | TEXT NOT NULL | 上传文件名 |
| `file_path` | TEXT NOT NULL | 服务端归档路径 |
| `md5` | TEXT NOT NULL | 服务端确认后的 MD5 |
| `submit_time` | TEXT NOT NULL | 提交时间 |
| `status` | TEXT NOT NULL DEFAULT `pending` | 提交状态 |
| `score` | INTEGER | 分数 |
| `comment` | TEXT | 教师评语 |
| `feedback_path` | TEXT | Markdown 反馈路径 |

### 6.3 模块 C Mock `submissions`

| 字段 | 说明 | 正式接口映射 |
| --- | --- | --- |
| `id` | 本地提交 ID | `submission_id` |
| `student_id` | 学生 ID | `student_id` |
| `student_name` | 学生姓名 | 当前模块 B 不提供，正式接入时不能强依赖 |
| `assignment_title` | 作业标题 | 当前模块 B pending 接口不提供，正式接入时可用 `assignment_id` 替代或扩展 B |
| `content` | 作业正文 | 当前模块 B 不提供，正式接入时可显示 `file_name`、`file_path`、`md5` |
| `status` | 本地状态 | `pending` 可直连，`approved` 映射为 `graded` |
| `created_at` | 本地创建时间 | `submit_time` |
| `score` | 分数 | `score` |
| `comment` | 评语 | `comment` |
| `reviewed_at` | 本地批改时间 | 当前模块 B 不返回，后续可扩展 |
| `feedback_path` | 反馈路径 | `feedback_path` |

## 7. 集成工作流

### 7.1 作业发布

负责人：模块 B、模块 C。

流程：

1. 模块 C 或测试脚本调用 `POST /v1/assignments`。
2. 模块 B 写入 `assignments`。
3. 模块 A 调用 `GET /v1/assignments/open` 获取开放作业。

验收证据：

- 返回 `assignment_id` 和 `status=open`。
- `GET /v1/assignments/open` 能查到同一作业。

### 7.2 学生提交

负责人：模块 A、模块 B。

流程：

1. 模块 A 监控作业目录。
2. 文件停止变化后触发打包。
3. 模块 A 计算压缩包 MD5。
4. 模块 A 调用 `POST /v1/submissions`。
5. 模块 B 保存临时文件，重新计算 MD5。
6. MD5 一致则归档并写库。
7. MD5 不一致则删除临时文件并返回 400。

验收证据：

- 成功时返回 `submission_id` 和 `status=pending`。
- 失败时返回 MD5 mismatch 错误。
- 文件存在于 `data/submissions/{student_id}/{assignment_id}/`。

### 7.3 教师批改

负责人：模块 B、模块 C。

流程：

1. 模块 C 调用 `GET /v1/submissions/pending`。
2. TUI 展示待批改列表。
3. 教师输入分数和评语。
4. 模块 C 调用 `POST /v1/submissions/grade`。
5. 模块 B 更新状态为 `graded` 或 `rejected`。
6. 模块 B 生成 Markdown 反馈。

验收证据：

- 返回 `status=graded` 或 `status=rejected`。
- `feedback_path` 文件存在。
- 反馈文件包含提交编号、学生学号、作业编号、教师、时间、分数和评语。

### 7.4 学生反馈拉取

负责人：模块 A、模块 B。

流程：

1. 模块 A 定时或手动调用 `GET /v1/feedback/{student_id}`。
2. 模块 B 返回该学生已批改或打回的反馈。
3. 模块 A 保存或展示 `feedback_markdown`。

验收证据：

- 只返回当前学生的反馈。
- 只返回 `graded` 和 `rejected` 状态。
- 返回内容包含 `feedback_markdown`。

## 8. 工程规范

### 8.1 路径规范

- 不允许硬编码个人路径，例如 `/home/zhangsan/...`。
- 模块 B 当前基于 `Path(__file__).resolve().parents[1]` 计算项目路径。
- 模块 C 当前支持 `.env` 配置：
  - `CONTROLLER_DB`
  - `FEEDBACK_DIR`
  - `LOG_FILE`
- 模块 C 配置路径必须保持在项目根目录内。

### 8.2 依赖规范

- Python 版本要求：Python 3.10+。
- 模块 B 依赖记录在 `module_b_server/requirements.txt`。
- 模块 C 依赖记录在 `module_c_controller/requirements.txt`。
- 新增依赖必须写入对应模块的 `requirements.txt`。

### 8.3 日志规范

后续所有模块应统一日志格式：

```text
[时间] [模块名] [级别] 消息内容
```

示例：

```text
[2026-05-27 10:00:00] [Module_B] [INFO] submission accepted: submission_id=1
```

当前代码仍有命令行输出和未统一日志的位置，模块 D 应纳入整改。

### 8.4 安全和健壮性规范

- 文件上传必须校验 MD5。
- 文件名必须防路径穿越。
- 大文件接收必须先写临时目录，校验成功后再移动到正式目录。
- 网络请求必须设置 timeout。
- 模块 A 必须实现重试，不能因模块 B 暂时不可用而卡死。
- 模块 B 数据库连接必须设置合理超时，当前实现为 SQLite timeout 10 秒。
- 批改接口后续应禁止重复批改非 `pending` 提交。

## 9. 后续开发任务

### 9.1 必须完成

| 优先级 | 任务 | 负责人 | 验收标准 |
| --- | --- | --- | --- |
| P0 | 修复或重写 `docs/api_spec.md` | 模块 B | 与本文档第 5 节一致 |
| P0 | 模块 C 新增 HTTP API 数据访问层 | 模块 C | TUI 能从模块 B 读取 pending，并提交 GRADE |
| P0 | 模块 A 实现提交链路 | 模块 A | 能自动打包、计算 MD5、上传、拉取反馈 |
| P0 | 统一状态字段 | 模块 B/C | 正式接口不再使用 `approved` 表示服务端状态 |
| P0 | 模块 B 批改接口限制 pending | 模块 B | 非 pending 提交不能被重复批改 |
| P1 | 一键验收脚本 | 模块 D | 干净环境执行一条命令完成安装和 smoke test |
| P1 | 统一日志 | 模块 D/全体 | 所有模块输出可定位问题 |
| P1 | 异常测试 | 模块 D | 覆盖 MD5 错误、非法 action、重复 assignment_id、无效 submission_id |

### 9.2 模块 C 正式接入建议

模块 C 不应直接改 TUI 主逻辑来适配 HTTP。建议新增一层数据访问接口：

```text
controller/
├── repository.py      # 定义 list_submissions / get_submission / grade_submission 抽象
├── sqlite_repo.py     # 当前 Mock 实现
└── api_client.py      # 正式 HTTP 实现
```

TUI 只依赖统一的数据访问接口，不直接关心数据来自 SQLite 还是 HTTP。

### 9.3 模块 B 文档修复建议

`module_b_server/README.md` 当前缺少结尾代码围栏，导致后续脚本内容在阅读时可能被误认为 README 内容。后续应补齐 README，并把真实运行命令、接口示例、smoke test 用法分开。

`docs/api_spec.md` 当前未完整闭合代码块，也未覆盖所有接口。后续应以本文档第 5 节为依据重写。

## 10. 验收方案

### 10.1 模块 B 单模块验收

运行模块 B 服务后执行：

```bash
cd /Hao/gongchuang/module_b_server
bash scripts/smoke_test.sh
```

验收内容：

- `/health` 可访问。
- 可创建作业。
- 可查询开放作业。
- 可提交压缩包。
- 可查询 pending。
- 可批改。
- 可查询反馈。

### 10.2 模块 C 单模块验收

```bash
cd /Hao/gongchuang/module_c_controller
pytest -q
```

验收内容：

- 配置路径解析正确。
- Mock 数据库初始化正确。
- pending、approved、all 过滤正确。
- 批改后状态更新正确。
- Markdown 反馈生成正确。

### 10.3 全链路验收

最终验收必须覆盖：

1. 创建作业。
2. 学生端自动提交。
3. 服务端 MD5 校验。
4. 教师端 TUI 查看待批改。
5. 教师端批改。
6. 学生端拉取反馈。
7. 错误 MD5 被拒绝。
8. 非法 action 被拒绝。
9. 重复批改被拒绝。
10. 一键脚本可在干净 Ubuntu 环境执行。

## 11. 当前不可忽视的风险

| 风险 | 影响 | 处理方式 |
| --- | --- | --- |
| 模块 C 仍使用本地 Mock 数据 | 无法真实联调 B/C | 新增 HTTP 数据访问层 |
| 状态 `approved` 与 `graded` 不统一 | 批改结果无法跨模块理解 | 正式服务统一 `graded/rejected` |
| 错误响应被 FastAPI 包在 `detail` 中 | 客户端解析可能写错 | 客户端按当前格式处理，后续统一异常处理 |
| 模块 B 返回绝对文件路径 | 客户端可能依赖服务器本地路径 | 对外只把路径当展示信息，不作为下载协议 |
| 批改接口未限制 pending | 重复批改可能覆盖结果 | 模块 B 增加状态校验 |
| README/API 文档残缺 | 新成员可能按错接口开发 | 以本文档为准，重写 API 文档 |

## 12. 当前正式结论

后续所有模块开发必须以以下事实为准：

- 作业字段使用 `assignment_id`，不使用 `task_id`。
- 文件校验字段使用 `md5`，不使用 `hash`。
- 服务端提交状态使用 `pending`、`graded`、`rejected`。
- 模块 C 本地 `approved` 只是 Mock 阶段 UI 状态，正式接入时映射为 `graded`。
- 待批改接口使用 `GET /v1/submissions/pending`。
- 批改接口使用 `POST /v1/submissions/grade`，action 为 `GRADE`。
- 学生反馈接口使用 `GET /v1/feedback/{student_id}`。
- 本文档未确认的接口字段不得擅自加入正式契约。
