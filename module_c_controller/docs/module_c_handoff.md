# Module C Handoff

## 当前完成的功能

模块 C 的核心功能和工程化收尾已完成，当前版本包含：

- Textual TUI。
- `pending` / `approved` / `all` 三种视图。
- `j` / `k` 上下选择。
- `Enter` 进入批改。
- `Ctrl+s` 提交审批。
- `Esc` 取消。
- 自动生成 Markdown 反馈。
- 数据库状态从 `pending` 更新为 `approved`。
- 可以在 TUI 中查看已批改记录的 `score`、`comment`、`reviewed_at`、`feedback_path`。
- `pytest` 已通过。

## 运行方式

```bash
cd /Hao/gongchuang/module_c_controller
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_mock_db.py
python scripts/run_controller.py
pytest -q
```

## 当前实际数据源

当前模块 C 没有直接调用真实 HTTP API，而是使用 SQLite Mock 数据库作为本地数据源。

| 项目 | 当前值 |
| --- | --- |
| 数据库类型 | SQLite Mock |
| 数据库路径 | `data/mock_submissions.db` |
| 反馈输出目录 | `feedback_outbox/` |
| 后续替换点 | 可新增 `controller/api_client.py` 替换 SQLite Mock 数据访问层 |

## SQLite Mock 表字段

| 字段 | 说明 |
| --- | --- |
| `id` | 本地提交记录 ID |
| `student_id` | 学生 ID |
| `student_name` | 学生姓名 |
| `assignment_title` | 作业标题 |
| `content` | 作业内容 |
| `status` | 作业状态，当前主要为 `pending` 或 `approved` |
| `created_at` | 提交创建时间 |
| `score` | 批改分数 |
| `comment` | 批改评语 |
| `reviewed_at` | 批改完成时间 |
| `feedback_path` | Markdown 反馈文件路径 |

## TUI 快捷键

| 快捷键 | 说明 |
| --- | --- |
| `j` | 向下选择 |
| `k` | 向上选择 |
| `Enter` | 批改当前 `pending` 作业 |
| `Ctrl+s` | 在批改弹窗中提交 |
| `Esc` | 取消批改 |
| `p` | `pending` 视图 |
| `a` | `approved` 视图 |
| `l` | `all` 视图 |
| `r` | 刷新 |
| `q` | 退出 |

## 统一 JSON 数据交换规范

后续模块间数据交换统一使用 JSON 格式。

| 规范项 | 约定 |
| --- | --- |
| 数据格式 | JSON |
| 字段命名 | 统一使用 `snake_case`，例如 `student_id`；禁止 `studentID` 或 `StudentId` |
| 基础请求字段 | `action`、`timestamp`、`payload` |
| `action` | 操作类型，如 `SUBMIT`、`QUERY`、`APPROVE` |
| `timestamp` | Unix 时间戳 |
| `payload` | 具体业务数据 |

### 状态码约定

| 状态码 | 说明 |
| --- | --- |
| `200` | 操作成功 |
| `400` | 客户端数据格式错误或参数错误 |
| `403` | 权限不足 |
| `500` | 后端数据库或逻辑错误 |

## 模块 C 需要模块 B 提供的接口

| action | 说明 |
| --- | --- |
| `QUERY_PENDING` | 查询待批改作业 |
| `QUERY_APPROVED` | 查询已批改作业 |
| `QUERY_ALL` | 查询全部作业 |
| `APPROVE` | 提交批改结果 |

## 模块 C 的输出

模块 C 当前会产生以下输出：

- 数据库状态更新，将作业从 `pending` 更新为 `approved`。
- Markdown 反馈文件，输出到 `feedback_outbox/`。
- `feedback_markdown` 或 `feedback_path` 需要交给模块 B，后续由模块 A 获取反馈。
