# 跨平台课程管理终端 API 规范

本文档以当前模块 B FastAPI 实现和集成工作文档为准，描述模块 A、B、C 之间的正式接口契约。

## 1. 基础约定

- 本地开发默认地址：`http://127.0.0.1:8000`
- 学生公网入口：`https://student.haoceanlab.cn`
- 教师公网入口：`https://teacher.haoceanlab.cn`
- 字段命名：统一使用 `snake_case`
- JSON 请求：统一包含 `action`、`timestamp`、`payload`
- 成功响应：统一包含 `code`、`message`、`payload`
- 当前错误响应：FastAPI `HTTPException` 格式，即 `{"detail": {"code": 400, "message": "..."}}`
- 文件上传：使用 `multipart/form-data`，字段为 `metadata` 和 `file`
- 文件校验字段：统一使用 `md5`
- 作业 ID 字段：统一使用 `assignment_id`

## 2. 状态定义

| 状态 | 对象 | 说明 |
| --- | --- | --- |
| `open` | assignment | 作业开放，学生可以提交 |
| `pending` | submission | 提交已接收，等待批改 |
| `graded` | submission | 已批改且通过 |
| `rejected` | submission | 已批改但打回或拒绝 |

模块 C 的本地 SQLite Mock 仍可显示 `approved`，但正式 HTTP 接口必须使用模块 B 的 `graded`。

## 3. 健康检查

```http
GET /health
```

成功响应：

```json
{
  "code": 200,
  "message": "module_b_server is running",
  "db_path": "/Hao/gongchuang/module_b_server/data/db/engine.db",
  "time": "2026-05-28 10:00:00"
}
```

## 3.1 班级和加入码

教师创建班级：

```http
POST /v1/classes
Content-Type: application/json
```

请求：

```json
{
  "action": "CREATE_CLASS",
  "timestamp": 1760000000,
  "payload": {
    "teacher_id": "T001",
    "class_id": "cs101",
    "class_name": "CS101 Spring",
    "course_id": "course_cs",
    "course_title": "Computer Science",
    "join_code": "JOIN101"
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "class created",
  "payload": {
    "class_id": "cs101",
    "class_name": "CS101 Spring",
    "course_id": "course_cs",
    "course_title": "Computer Science",
    "join_code": "JOIN101",
    "teacher_id": "T001",
    "created_at": "2026-06-01 10:00:00",
    "status": "active"
  }
}
```

学生加入班级：

```http
POST /v1/classes/join
Content-Type: application/json
```

```json
{
  "action": "JOIN_CLASS",
  "timestamp": 1760000000,
  "payload": {
    "student_id": "2024001",
    "join_code": "JOIN101"
  }
}
```

学生查看自己已加入班级：

```http
GET /v1/classes/my
```

教师查看自己创建的班级：

```http
GET /v1/classes
```

## 4. 创建作业

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
    "deadline": "2026-06-01 23:59:59",
    "class_id": "cs101"
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
    "class_id": "cs101",
    "status": "open"
  }
}
```

约束：

- `action` 必须为 `CREATE_ASSIGNMENT`
- `assignment_id` 不允许重复
- `teacher_id` 写入服务端 `created_by`
- `class_id` 可为空；不为空时必须是该教师创建的班级

## 5. 查询开放作业

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
        "class_id": "cs101",
        "class_name": "CS101 Spring",
        "course_title": "Computer Science",
        "created_at": "2026-05-28 10:00:00",
        "status": "open"
      }
    ]
  }
}
```

启用认证时，学生只会看到全局作业以及自己已加入班级的开放作业；教师只会看到自己创建或自己班级下的开放作业。

## 6. 提交作业

```http
POST /v1/submissions
Content-Type: multipart/form-data
```

表单字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `metadata` | string | JSON 字符串 |
| `file` | file | 作业压缩包 |

`metadata`：

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

- `action` 必须为 `SUBMIT`
- `assignment_id` 必须存在且状态为 `open`
- 如果作业绑定了 `class_id`，认证学生必须已加入该班级
- 模块 B 会重新计算文件 MD5
- MD5 不一致时返回 400，并删除临时文件
- 上传文件名会通过 `Path(name).name` 清理路径部分

## 7. 查询待批改提交

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
        "assignment_title": "Homework 1",
        "class_id": "cs101",
        "class_name": "CS101 Spring",
        "file_name": "2024001_home_001.tar.gz",
        "file_path": "/Hao/gongchuang/module_b_server/data/submissions/2024001/home_001/1760000100_2024001_home_001.tar.gz",
        "md5": "abc123...",
        "submit_time": "2026-05-28 10:10:00",
        "status": "pending",
        "download_url": "/v1/submissions/1/download"
      }
    ]
  }
}
```

模块 C 正式 HTTP 模式使用该接口渲染 pending 列表。`file_path` 是服务端本地路径，只能用于审计展示；教师客户端下载提交包必须使用 `download_url`。

## 7.1 下载提交包

```http
GET /v1/submissions/{submission_id}/download
```

用于教师客户端下载某个提交包到本机。启用认证时，教师只能下载自己创建作业或自己班级下的提交。

## 8. 提交批改结果

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
- `status` 只能为 `graded` 或 `rejected`
- `submission_id` 必须存在且当前状态必须为 `pending`
- 非 `pending` 提交不能重复批改，返回 400
- 模块 B 负责生成 Markdown 反馈文件

## 9. 查询学生反馈

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
        "submit_time": "2026-05-28 10:10:00",
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

- 只返回当前 `student_id` 的反馈
- 只返回 `graded` 和 `rejected` 状态
- 反馈文件不存在时 `feedback_markdown` 为空字符串

## 10. 当前错误响应示例

```json
{
  "detail": {
    "code": 400,
    "message": "submission is not pending"
  }
}
```

## 11. 配置作业互评

```http
POST /v1/assignments/peer-review/config
Content-Type: application/json
```

用于给某个作业开启或关闭互评。普通作业可以不开启，期末大作业可以开启。

请求：

```json
{
  "action": "CONFIG_PEER_REVIEW",
  "timestamp": 1760000300,
  "payload": {
    "assignment_id": "home_final",
    "enabled": true,
    "teacher_weight": 0.7,
    "peer_weight": 0.3,
    "bonus_threshold_1": 5,
    "bonus_value_1": 5,
    "bonus_threshold_2": 10,
    "bonus_value_2": 3,
    "bonus_threshold_3": 15,
    "bonus_value_3": 1
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "peer review config updated",
  "payload": {
    "assignment_id": "home_final",
    "peer_review_enabled": true,
    "teacher_weight": 0.7,
    "peer_weight": 0.3
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `assignment_id` | 作业编号 |
| `enabled` | 是否开启互评 |
| `teacher_weight` | 老师评分占比 |
| `peer_weight` | 学生互评平均分占比 |
| `bonus_threshold_1` | 一档奖励阈值 |
| `bonus_value_1` | 一档奖励分 |
| `bonus_threshold_2` | 二档奖励阈值 |
| `bonus_value_2` | 二档奖励分 |
| `bonus_threshold_3` | 三档奖励阈值 |
| `bonus_value_3` | 三档奖励分 |

约束：

- `action` 必须为 `CONFIG_PEER_REVIEW`
- `assignment_id` 必须存在
- `teacher_weight` 和 `peer_weight` 不能为负数
- `teacher_weight + peer_weight` 必须大于 0

## 12. 学生提交互评分

```http
POST /v1/peer-reviews
Content-Type: application/json
```

用于学生给其他同学的提交评分。

请求：

```json
{
  "action": "SUBMIT_PEER_REVIEW",
  "timestamp": 1760000400,
  "payload": {
    "reviewer_student_id": "2024002",
    "submission_id": 21,
    "score": 94,
    "comment": "我认为该作业完成较好。"
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "peer review submitted",
  "payload": {
    "assignment_id": "home_final",
    "submission_id": 21,
    "reviewer_student_id": "2024002",
    "score": 94
  }
}
```

约束：

- `action` 必须为 `SUBMIT_PEER_REVIEW`
- `submission_id` 必须存在
- 作业必须已经开启互评
- 学生不能给自己的提交评分
- `score` 必须在 0 到 100 之间
- 同一个学生对同一个提交重复评分时，会覆盖旧评分

## 13. 计算最终成绩

```http
POST /v1/assignments/{assignment_id}/calculate-final-scores
```

用于计算某个作业的最终成绩。通常由模块 C 或管理员在互评结束后触发。

请求示例：

```bash
curl -X POST http://127.0.0.1:8000/v1/assignments/home_final/calculate-final-scores
```

计算规则：

```text
基础分 = 老师评分 × teacher_weight + 学生互评平均分 × peer_weight
最终分 = 基础分 + 互评准确奖励分
最终分最高不超过 100 分
```

如果某个提交没有学生互评分，则基础分直接使用老师评分。

互评准确奖励规则：

| 互评分与老师评分差距 | 奖励 |
| --- | --- |
| ≤ 5 分 | +5 |
| ≤ 10 分 | +3 |
| ≤ 15 分 | +1 |
| > 15 分 | +0 |

成功响应：

```json
{
  "code": 200,
  "message": "final scores calculated",
  "payload": {
    "assignment_id": "home_final",
    "results": [
      {
        "submission_id": 21,
        "student_id": "2024001",
        "assignment_id": "home_final",
        "teacher_score": 95,
        "peer_avg_score": 94.0,
        "peer_bonus": 3.0,
        "final_score": 97.7,
        "status": "graded"
      }
    ]
  }
}
```

说明：

- `teacher_score` 来自老师批改接口中的 `score`
- `peer_avg_score` 是其他学生对该提交的互评分平均值
- `peer_bonus` 是该学生给别人评分时，因为接近老师评分而获得的奖励
- `final_score` 为最终成绩

## 14. 查询最终成绩

```http
GET /v1/assignments/{assignment_id}/final-scores
```

用于查看某个作业所有学生的最终成绩。

请求示例：

```bash
curl http://127.0.0.1:8000/v1/assignments/home_final/final-scores
```

成功响应：

```json
{
  "code": 200,
  "message": "final scores returned",
  "payload": {
    "assignment_id": "home_final",
    "results": [
      {
        "submission_id": 21,
        "student_id": "2024001",
        "assignment_id": "home_final",
        "teacher_score": 95,
        "peer_avg_score": 94.0,
        "peer_bonus": 3.0,
        "final_score": 97.7,
        "status": "graded"
      }
    ]
  }
}
```

## 14.1 查重和成绩统计

查询某个作业的自动查重报告：

```http
GET /v1/assignments/{assignment_id}/plagiarism
```

成功响应包含 `reports` 列表，每项包括：

| 字段 | 说明 |
| --- | --- |
| `submission_id` | 当前提交编号 |
| `student_id` | 当前提交学生 |
| `plagiarism_rate` | 与最佳匹配提交的相似率，百分制 |
| `matched_submission_id` | 最相似提交编号 |
| `matched_student_id` | 最相似提交学生 |
| `matched_assignment_id` | 最相似提交所属作业 |
| `scope` | `current_assignment`、`last_three_years` 或 `none` |
| `checked_at` | 检测时间 |

查询单个提交的查重报告：

```http
GET /v1/submissions/{submission_id}/plagiarism
```

查询某个作业的成绩统计：

```http
GET /v1/assignments/{assignment_id}/score-stats
```

返回 `summary` 和 `scores`。统计使用 `final_score` 优先，没有最终成绩时使用教师批改分 `score`。

查询某个学生的历史成绩：

```http
GET /v1/students/{student_id}/score-history
```

启用认证时，学生只能查询自己的历史成绩；教师可查询任意学生。

## 15. 生成课程归档包

```http
POST /v1/archives/course
Content-Type: application/json
```

课程结束后，用于生成课程归档 zip 包。

请求：

```json
{
  "action": "CREATE_COURSE_ARCHIVE",
  "timestamp": 1760000500,
  "payload": {
    "archive_name": "course_archive.zip",
    "note": "课程结束归档",
    "include_db": true,
    "include_submissions": true,
    "include_feedback": true,
    "include_docs": true
  }
}
```

成功响应：

```json
{
  "code": 200,
  "message": "course archive created",
  "payload": {
    "archive_name": "course_archive.zip",
    "archive_path": "/Hao/gongchuang/module_b_server/data/archives/course_archive.zip",
    "download_url": "/v1/archives/download/course_archive.zip"
  }
}
```

归档内容：

| 目录或文件 | 说明 |
| --- | --- |
| `database/engine.db` | SQLite 数据库备份 |
| `submissions/` | 学生提交文件 |
| `feedback/` | 教师反馈 Markdown |
| `docs/` | 项目文档 |
| `README.md` | 模块 B 使用说明 |

约束：

- `action` 必须为 `CREATE_COURSE_ARCHIVE`
- `archive_name` 不允许重复
- `archive_name` 会经过文件名清理，防止路径穿越

## 16. 查询归档列表

```http
GET /v1/archives
```

用于查看已经生成过的课程归档包。

成功响应：

```json
{
  "code": 200,
  "message": "archives returned",
  "payload": {
    "archives": [
      {
        "archive_id": 1,
        "archive_name": "course_archive.zip",
        "archive_path": "/Hao/gongchuang/module_b_server/data/archives/course_archive.zip",
        "created_at": "2026-06-01 03:04:00",
        "note": "课程结束归档"
      }
    ]
  }
}
```

## 17. 下载归档包

```http
GET /v1/archives/download/{archive_name}
```

用于下载指定归档包。

请求示例：

```bash
curl -L -o course_archive.zip \
  http://127.0.0.1:8000/v1/archives/download/course_archive.zip
```

下载后可以用下面命令查看压缩包内容：

```bash
unzip -l course_archive.zip
```

错误示例：

```json
{
  "detail": {
    "code": 400,
    "message": "archive does not exist"
  }
}
```
