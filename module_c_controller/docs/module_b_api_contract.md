# Module C 与 Module B 正式接口契约

本文档记录模块 C 正式 HTTP 模式对模块 B 的依赖。模块 C 仍保留 SQLite Mock 模式用于本地演示和单元测试；正式联调时通过环境变量切换到 HTTP 模式。

## 1. 运行模式

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `CONTROLLER_SOURCE` | `sqlite` 或 `http` | `sqlite` |
| `CONTROLLER_API_BASE_URL` | 模块 B 服务地址 | `http://127.0.0.1:8000` |
| `CONTROLLER_TEACHER_ID` | 批改教师 ID | `T001` |
| `CONTROLLER_REQUEST_TIMEOUT_SECONDS` | HTTP 请求超时秒数 | `60` |

正式联调示例：

```bash
CONTROLLER_SOURCE=http python scripts/run_controller.py
```

## 2. 状态映射

模块 B 的服务端状态是正式状态：

| 模块 B 状态 | 模块 C UI 展示 | 说明 |
| --- | --- | --- |
| `pending` | `pending` | 待批改 |
| `graded` | `approved` | 已批改通过，兼容 C 端原有 approved 视图 |
| `rejected` | `rejected` | 已打回或拒绝 |

模块 C 允许本地 SQLite Mock 继续保存 `approved`，但 HTTP 请求中必须向模块 B 提交 `graded` 或 `rejected`。

## 3. 查询提交

模块 C 调用：

```http
GET /v1/submissions?status=pending
```

`status` 可为 `pending`、`graded`、`rejected`、`all`。模块 C 的 `approved` 视图映射到模块 B 的 `graded`。旧路径 `GET /v1/submissions/pending` 保留为兼容入口。

成功响应：

```json
{
  "code": 200,
  "message": "submissions returned",
  "payload": {
    "status": "pending",
    "assignment_id": null,
    "summary": {
      "total": 1,
      "pending": 1,
      "graded": 0,
      "rejected": 0
    },
    "submissions": [
      {
        "submission_id": 1,
        "student_id": "2024001",
        "assignment_id": "home_001",
        "assignment_title": "Homework 1",
        "class_id": "cs101",
        "class_name": "CS101 Spring",
        "file_name": "2024001_home_001.tar.gz",
        "md5": "abc123...",
        "submit_time": "2026-05-28 10:10:00",
        "status": "pending",
        "score": null,
        "comment": null,
        "feedback_path": null,
        "download_url": "/v1/submissions/1/download"
      }
    ]
  }
}
```

字段映射：

| 模块 B 字段 | 模块 C `Submission` 字段 |
| --- | --- |
| `submission_id` | `id` |
| `student_id` | `student_id`、`student_name` fallback |
| `assignment_id` | `assignment_id` |
| `assignment_title` | `assignment_title` |
| `class_id`、`class_name` | `class_id`、`class_name` |
| `file_name`、`download_url`、`md5` | `content` |
| `submit_time` | `created_at` |
| `status` | `status` |
| `score`、`comment`、`feedback_path` | 评分详情 |

模块 B 不直接把服务器本地提交路径作为教师端操作入口；模块 C 下载提交包时必须使用 `download_url` 或 `/v1/submissions/{submission_id}/download`。

## 4. 提交批改结果

模块 C 调用：

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
    "comment": "完成较好，结构清晰。",
    "status": "graded",
    "feedback_path": "/Hao/gongchuang/module_b_server/data/feedback/2024001/home_001/submission_1_feedback.md",
    "graded_at": "2026-05-28 10:20:00"
  }
}
```

约束：

- `action` 必须为 `GRADE`
- `score` 必须是 0 到 100 的整数
- `status` 只能是 `graded` 或 `rejected`
- `pending`、`graded`、`rejected` 提交都可评分；重复评分会覆盖分数、评语、状态和反馈 Markdown
- 启用认证时，教师只能评分自己创建作业或自己班级下的提交
- 模块 B 生成 Markdown 反馈，模块 C HTTP 模式不再本地生成正式反馈文件

## 5. 当前错误响应格式

模块 B 当前业务错误使用 FastAPI `HTTPException`：

```json
{
  "detail": {
    "code": 400,
    "message": "score must be between 0 and 100"
  }
}
```

模块 C HTTP 客户端必须从 `detail.message` 读取错误信息。

## 6. 创建作业与互评开关

模块 C 发布作业时调用：

```http
POST /v1/assignments
Content-Type: application/json
```

请求 payload 除 `assignment_id`、`title`、`description`、`deadline`、`class_id` 外，还可传：

| 字段 | 说明 |
| --- | --- |
| `assignment_weight` | 课程总评相对权重，默认 `1.0` |
| `peer_review_enabled` | 是否在发布阶段开启互评 |
| `teacher_weight` | 开启互评时教师分权重，默认 `0.7` |
| `peer_weight` | 开启互评时互评分权重，默认 `0.3` |

如果 `peer_review_enabled=true`，模块 B 返回的 `peer_review_stage` 初始为 `submission`。提交结束后再调用阶段切换和自动分配任务接口，学生才会看到互评任务。
