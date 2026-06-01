# Module C 与 Module B 正式接口契约

本文档记录模块 C 正式 HTTP 模式对模块 B 的依赖。模块 C 仍保留 SQLite Mock 模式用于本地演示和单元测试；正式联调时通过环境变量切换到 HTTP 模式。

## 1. 运行模式

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `CONTROLLER_SOURCE` | `sqlite` 或 `http` | `sqlite` |
| `CONTROLLER_API_BASE_URL` | 模块 B 服务地址 | `http://127.0.0.1:8000` |
| `CONTROLLER_TEACHER_ID` | 批改教师 ID | `T001` |
| `CONTROLLER_REQUEST_TIMEOUT_SECONDS` | HTTP 请求超时秒数 | `10` |

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

## 3. 查询待批改提交

模块 C 调用：

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
        "submit_time": "2026-05-28 10:10:00",
        "status": "pending"
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
| `assignment_id` | `assignment_title` |
| `file_name`、`file_path`、`md5` | `content` |
| `submit_time` | `created_at` |
| `status` | `status` |

模块 B 当前不提供学生姓名、作业标题文本和作业正文，模块 C 不得强依赖这些字段。

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
    "status": "graded",
    "feedback_path": "/Hao/gongchuang/module_b_server/data/feedback/2024001/home_001/submission_1_feedback.md"
  }
}
```

约束：

- `action` 必须为 `GRADE`
- `score` 必须是 0 到 100 的整数
- `status` 只能是 `graded` 或 `rejected`
- 只能批改 `pending` 提交；非 `pending` 返回 400
- 模块 B 生成 Markdown 反馈，模块 C HTTP 模式不再本地生成正式反馈文件

## 5. 当前错误响应格式

模块 B 当前业务错误使用 FastAPI `HTTPException`：

```json
{
  "detail": {
    "code": 400,
    "message": "submission is not pending"
  }
}
```

模块 C HTTP 客户端必须从 `detail.message` 读取错误信息。
