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

约束：

- `class_id` 和 `join_code` 全局唯一。
- `class_name` 在同一老师名下不可重复；不同老师可以使用相同班级名。

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
    "class_id": "cs101",
    "assignment_weight": 1.0,
    "peer_review_enabled": true,
    "teacher_weight": 0.7,
    "peer_weight": 0.3,
    "bonus_threshold_1": 5
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
    "assignment_weight": 1.0,
    "peer_review_enabled": true,
    "peer_review_stage": "submission",
    "teacher_weight": 0.7,
    "peer_weight": 0.3,
    "peer_bonus_rule": "+1 when peer score is within 5 points of teacher score",
    "status": "open"
  }
}
```

约束：

- `action` 必须为 `CREATE_ASSIGNMENT`
- `assignment_id` 不允许重复
- `teacher_id` 写入服务端 `created_by`
- `class_id` 可为空；不为空时必须是该教师创建的班级
- 教师端会按北京时间把简写 deadline 规范化为 `YYYY-MM-DD HH:MM:SS`
- `assignment_weight` 是课程总评中的相对权重；默认 `1.0`，必须为非负数
- `peer_review_enabled` 建议在创建作业时决定；开启后初始阶段为 `submission`
- `teacher_weight` 和 `peer_weight` 不能为负数，且二者之和必须大于 0

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

## 7. 查询提交列表

```http
GET /v1/submissions?status=pending
```

`status` 支持：

- `pending`：待批改
- `graded` / `approved`：已评分
- `rejected`：已打回
- `all`：全部提交

也可以追加 `assignment_id=home_001` 只看某一次作业的提交。旧路径 `GET /v1/submissions/pending` 仍保留，等价于 `status=pending`。

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

模块 C 正式 HTTP 模式使用该接口渲染 pending / graded / all 列表。教师客户端下载提交包必须使用 `download_url` 或下载接口。

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
- `status` 只能为 `graded` 或 `rejected`
- `submission_id` 必须存在，且当前状态为 `pending`、`graded` 或 `rejected`
- 已评分提交允许重新评分，模块 B 会覆盖 `score`、`comment`、`status` 和反馈 Markdown
- 启用认证时，教师只能评分自己创建作业或自己班级下的提交
- 模块 B 负责生成或覆盖 Markdown 反馈文件

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

主流程建议在创建作业时通过 `peer_review_enabled` 决定是否开启互评。本接口保留为兼容入口，也可用于补配或调整已有作业的互评权重；调用后阶段会回到 `setup`。

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
    "bonus_value_1": 1,
    "bonus_threshold_2": 10,
    "bonus_value_2": 0,
    "bonus_threshold_3": 15,
    "bonus_value_3": 0
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
    "peer_review_stage": "setup",
    "teacher_weight": 0.7,
    "peer_weight": 0.3,
    "peer_bonus_rule": "+1 when peer score is within 5 points of teacher score"
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
| `bonus_value_1` | 兼容字段；当前奖励固定为命中一档时最多 `+1` |
| `bonus_threshold_2` | 二档奖励阈值 |
| `bonus_value_2` | 兼容字段；当前为 `0` |
| `bonus_threshold_3` | 三档奖励阈值 |
| `bonus_value_3` | 兼容字段；当前为 `0` |

约束：

- `action` 必须为 `CONFIG_PEER_REVIEW`
- `assignment_id` 必须存在
- `teacher_weight` 和 `peer_weight` 不能为负数
- `teacher_weight + peer_weight` 必须大于 0

## 12. 学生提交互评分

自动分配互评任务规则：

- 默认每个学生互评 2 份作业。
- 如果只有 2 个学生，则相互评 1 份。
- 只有 1 个学生无法分配互评任务。
- 自动分配按学生去重，使用每个学生该作业下最新一次提交作为互评对象。

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
- 作业阶段必须是 `peer_review` 或 `final_calculation`
- 学生必须拥有该提交对应的互评任务
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
| ≤ 5 分 | +1 |
| > 5 分 | +0 |

同一学生在同一作业内即使有多个互评任务命中接近条件，互评准确奖励也最多为 `+1`。

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
        "peer_bonus": 1.0,
        "final_score": 95.7,
        "assignment_weight": 1.0,
        "weighted_score": 95.7,
        "status": "graded"
      }
    ]
  }
}
```

说明：

- `teacher_score` 来自老师批改接口中的 `score`
- `peer_avg_score` 是其他学生对该提交的互评分平均值
- `peer_bonus` 是该学生给别人评分时，因为接近老师评分而获得的奖励；每个作业最多 `+1`
- `final_score` 为最终成绩
- `assignment_weight` / `weighted_score` 用于课程总评和归档中的加权成绩

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
        "peer_bonus": 1.0,
        "final_score": 95.7,
        "assignment_weight": 1.0,
        "weighted_score": 95.7,
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

查询单个提交的 AI 批改报告：

```http
GET /v1/submissions/{submission_id}/ai-grade-report
```

教师端可以通过请求头 `X-DeepSeek-API-Key` 提供老师自己的 DeepSeek key；如果没有该请求头，服务端读取 `DEEPSEEK_API_KEY` 或 `MODULE_B_DEEPSEEK_API_KEY`。未配置时返回本地结构化报告；配置后会调用 DeepSeek 并缓存结果。重新批改提交会清除该提交的缓存报告。

查询某个作业的成绩统计：

```http
GET /v1/assignments/{assignment_id}/score-stats
```

返回 `summary` 和 `scores`。统计使用 `final_score` 优先，没有最终成绩时使用教师批改分 `score`。`scores` 中包含 `teacher_score`、`peer_avg_score`、`peer_bonus`、`final_score`、`assignment_weight` 和 `weighted_score`。

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
    "include_db": false,
    "include_submissions": true,
    "include_feedback": false,
    "include_docs": false
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

归档内容（教师作业文件集合包）：

| 目录或文件 | 说明 |
| --- | --- |
| `assignment_<assignment_id>_homework_files/` | 单作业时的导出目录（扁平结构） |
| `assignment_all_homework_files/` | 多作业混合导出时的目录（扁平结构） |
| `scores/assignment_scores.csv` | 每次提交的教师分、互评分、奖励、最终分、作业权重和加权分 |
| `scores/course_final_scores.csv` | 按学生汇总的课程加权总评；权重按相对权重归一计算 |

导出规则：

- 只导出学生提交包中的作业文件，不打包数据库、反馈目录、文档目录、运行缓存目录。
- 每个文件导出后统一重命名为：`{assignment_id}_{student_id}_{submission_id}_{original_filename}`。
- 若重名冲突，会自动追加序号后缀（例如 `_2`）。
- 文件名会做安全化处理，仅保留跨平台安全字符。
- 排除：`__pycache__/`、`.git/`、`.venv/`、`node_modules/`、`.DS_Store`、`Thumbs.db`、`*.pyc`、`*.log`、`*.tmp`、`*.db`、`*.sqlite`、`*.zip`、`*.tar`、`*.gz`。
- 保留常见作业文件：`.py`、`.c`、`.cpp`、`.h`、`.java`、`.js`、`.html`、`.css`、`.md`、`.txt`、`.pdf`、`.docx`、`.xlsx`、`.ipynb`、`.png`、`.jpg`、`.jpeg`。

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
---

## 18. C → B：触发作业查重

### POST `/v1/plagiarism/check`

用于对某个作业进行查重。候选范围包括当前作业内同期提交之间的比较，以及当前作业提交与最近三年历史提交的交叉比较；同一学生自己的多次提交不会互相判为疑似。

当前支持 `token`、`hybrid`、`ai` 三种方式。

- `token`：只做本地 token 查重，不调用外部模型。
- `hybrid`：先做本地 token 预筛，再把高风险候选对交给 DeepSeek 复核，推荐日常使用。
- `ai`：仍先按本地分数排序和限流，再调用 DeepSeek；如需全量 AI 两两复核，可设置 `ai_prefilter=0` 并调大 `ai_limit`。

本地预筛会先对文本进行规范化处理，过滤数字、下划线和标点，只保留中文和英文 token，再计算相似度，避免因为数字或下划线相同导致误判。`hybrid` / `ai` 会把预筛后的候选对及其 `scope`、作业编号、提交编号发给 DeepSeek 复核。

教师端可以通过请求头 `X-DeepSeek-API-Key` 提供老师自己的 DeepSeek key；如果没有该请求头，服务端读取 `DEEPSEEK_API_KEY` 或 `MODULE_B_DEEPSEEK_API_KEY`。

### 请求示例

```bash
curl -X POST http://127.0.0.1:8000/v1/plagiarism/check \
  -H "Content-Type: application/json" \
  -H "X-DeepSeek-API-Key: your-deepseek-key" \
  -d '{
    "action": "CHECK_PLAGIARISM",
    "timestamp": 1710000000,
    "payload": {
      "assignment_id": "home_1",
      "threshold": 0.75,
      "method": "hybrid",
      "ai_prefilter": 0.45,
      "ai_limit": 12
    }
  }'
```

### 请求字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| action | string | 必须为 `CHECK_PLAGIARISM` |
| assignment_id | string | 作业编号 |
| threshold | float | 查重阈值，范围 `(0, 1]`，如 `0.75` |
| method | string | 支持 `token`、`hybrid`、`ai` |
| ai_prefilter | float | 可选，本地预筛阈值，默认读取 `DEEPSEEK_PREFILTER_SIMILARITY` |
| ai_limit | int | 可选，最多交给 DeepSeek 复核的候选对数量，默认读取 `DEEPSEEK_MAX_CANDIDATE_PAIRS` |

### 返回示例

```json
{
  "code": 200,
  "message": "plagiarism check finished",
  "payload": {
    "assignment_id": "home_1",
    "method": "hybrid",
    "threshold": 0.75,
    "note": "digits and underscores are ignored during tokenization; current assignment submissions are compared with each other and with submissions from the last three years; AI methods first prefilter by local token similarity for efficiency",
    "scope": "current_assignment_and_last_three_years",
    "submission_count": 2,
    "historical_submission_count": 8,
    "compared_document_count": 10,
    "candidate_pair_count": 9,
    "ai_enabled": true,
    "ai_model": "deepseek-v4-flash",
    "ai_prefilter": 0.45,
    "ai_limit": 12,
    "ai_reviewed_count": 1,
    "ai_error_count": 0,
    "suspected_pair_count": 1,
    "suspected_pairs": [
      {
        "student_a": "2024001",
        "submission_a": 21,
        "assignment_a": "home_1",
        "file_a": "2024001_home_1.tar.gz",
        "student_b": "2024002",
        "submission_b": 22,
        "assignment_b": "home_1",
        "file_b": "2024002_home_1.tar.gz",
        "scope": "current_assignment",
        "similarity": 0.92,
        "local_similarity": 0.83,
        "ai_similarity": 0.92,
        "ai_confidence": 0.88,
        "threshold": 0.75,
        "reason": "AI 判断两份提交存在相同核心循环结构。",
        "evidence": ["核心函数结构一致", "错误处理方式相同"]
      }
    ]
  }
}
```

### 说明

1. `token` 模式不调用 DeepSeek；
2. `hybrid` / `ai` 模式需要配置 `DEEPSEEK_API_KEY`；
3. `similarity >= threshold` 或 AI 明确判定疑似重复时，该提交对会被列入疑似重复；
4. `scope=current_assignment` 表示同期作业内比较，`scope=last_three_years` 表示当前提交和三年内历史提交比较；
5. 默认只把本地高风险候选交给 AI，避免全班所有提交两两调用模型；
6. 默认模型为 `deepseek-v4-flash`，后端会关闭 V4 thinking 模式以提升批量查重速度。

---

## 19. C / A → B：查询查重报告

### GET `/v1/plagiarism/reports/{assignment_id}`

用于查看某个作业的查重报告历史。

### 请求示例

```bash
curl http://127.0.0.1:8000/v1/plagiarism/reports/home_1
```

### 返回示例

```json
{
  "code": 200,
  "message": "plagiarism reports returned",
  "payload": {
    "assignment_id": "home_1",
    "reports": [
      {
        "report_id": 1,
        "assignment_id": "home_1",
        "method": "token",
        "threshold": 0.75,
        "created_at": "2026-06-06 05:20:07",
        "report_path": "/Hao/gongchuang/module_b_server/data/plagiarism_reports/plagiarism_home_1_xxx.json",
        "report": {
          "suspected_pair_count": 1,
          "suspected_pairs": []
        }
      }
    ]
  }
}
```

### 图形化界面对接说明

江浩的图形化界面可以直接调用：

```text
POST /v1/plagiarism/check
GET  /v1/plagiarism/reports/{assignment_id}
```

建议界面展示字段：

```text
student_a
student_b
submission_a
submission_b
similarity
threshold
reason
```
