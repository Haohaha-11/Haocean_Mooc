# 模块 C 控制端分发与使用说明

本文档面向模块 C 组员和教师端部署人员，说明需要接收哪些文件、如何配置 HTTP 正式模式、如何运行 TUI 和如何验证。

## 1. 分发范围

建议直接分发整个目录：

```text
/Hao/gongchuang/module_c_controller/
```

如果只同步本轮改动，至少需要以下文件：

```text
module_c_controller/
├── controller/
│   ├── api_client.py
│   ├── config.py
│   ├── db.py
│   ├── repository.py
│   ├── sqlite_repo.py
│   ├── status.py
│   └── tui.py
├── docs/
│   └── module_b_api_contract.md
├── tests/
│   ├── test_api_client.py
│   └── test_config.py
├── requirements.txt
├── .env.example
└── README.md
```

不要分发运行产物：

```text
.venv/
__pycache__/
*.pyc
.pytest_cache/
data/*.db
feedback_outbox/
logs/
```

## 2. 环境准备

要求：

- Python 3.10+
- 可用终端环境
- 能访问模块 B 服务，例如 `http://127.0.0.1:8000` 或服务器 IP

安装依赖：

```bash
cd module_c_controller
pip install -r requirements.txt
```

复制配置文件：

```bash
cp .env.example .env
```

## 3. 运行模式

模块 C 现在支持两种数据源：

| 模式 | 配置 | 用途 |
| --- | --- | --- |
| SQLite Mock | `CONTROLLER_SOURCE=sqlite` | 本地演示和单元测试 |
| HTTP 正式模式 | `CONTROLLER_SOURCE=http` | 连接模块 B 真实服务 |

正式联调必须使用 HTTP 模式。

## 4. HTTP 正式模式配置

编辑 `.env`：

```dotenv
CONTROLLER_SOURCE=http
CONTROLLER_API_BASE_URL=http://模块B服务器IP:8000
CONTROLLER_TEACHER_ID=T001
CONTROLLER_REQUEST_TIMEOUT_SECONDS=10
```

说明：

- `CONTROLLER_SOURCE=http`：启用模块 B HTTP 数据访问层。
- `CONTROLLER_API_BASE_URL`：模块 B 服务地址。
- `CONTROLLER_TEACHER_ID`：批改教师 ID，会提交给模块 B。
- `CONTROLLER_REQUEST_TIMEOUT_SECONDS`：HTTP 请求超时秒数。

## 5. 启动 TUI

```bash
python3 scripts/run_controller.py
```

也可以使用：

```bash
python3 -m controller.main
```

## 6. TUI 操作

| 按键 | 功能 |
| --- | --- |
| `p` | 查看 pending 待批改提交 |
| `a` | 查看 approved 视图 |
| `l` | 查看 all 视图 |
| `j` / `Down` | 向下选择 |
| `k` / `Up` | 向上选择 |
| `Enter` | 批改当前 pending 提交 |
| `Ctrl+s` | 在批改弹窗中提交分数和评语 |
| `Esc` | 关闭批改弹窗 |
| `r` | 刷新当前视图 |
| `q` | 退出 |

## 7. 状态映射

模块 B 的正式状态：

```text
pending
graded
rejected
```

模块 C UI 为了兼容原演示，可以继续显示：

```text
pending
approved
rejected
```

映射规则：

| 模块 B 状态 | 模块 C UI 显示 |
| --- | --- |
| `pending` | `pending` |
| `graded` | `approved` |
| `rejected` | `rejected` |

提交批改时，模块 C 会向模块 B 发送：

```json
{
  "action": "GRADE",
  "payload": {
    "status": "graded"
  }
}
```

教师不需要手动处理 `approved` 到 `graded` 的转换。

## 8. 正式工作流程

1. 模块 A 上传作业到模块 B。
2. 模块 B 将提交状态写为 `pending`。
3. 模块 C HTTP 模式调用 `GET /v1/submissions/pending`。
4. TUI 显示待批改列表。
5. 教师选择提交并录入分数、评语。
6. 模块 C 调用 `POST /v1/submissions/grade`。
7. 模块 B 校验 submission 必须是 `pending`。
8. 模块 B 更新为 `graded` 或 `rejected`，并生成 Markdown 反馈。
9. 模块 A 后续拉取反馈。

## 9. 验证方式

运行模块 C 单元测试：

```bash
pytest -q
```

如果使用项目自带虚拟环境：

```bash
.venv/bin/python -m pytest -q
```

预期结果：

```text
15 passed
```

验证 HTTP 配置是否生效：

```bash
CONTROLLER_SOURCE=http python3 scripts/run_controller.py
```

启动后按 `p` 刷新 pending 视图。如果模块 A 已经提交作业，列表中应出现模块 B 的真实 pending 提交。

## 10. 常见问题

### 10.1 pending 列表为空

可能原因：

- 模块 B 没启动。
- `.env` 中 `CONTROLLER_SOURCE` 仍是 `sqlite`。
- `CONTROLLER_API_BASE_URL` 写错。
- 模块 A 还没有成功提交作业。
- 提交已经被批改，不再处于 `pending`。

### 10.2 批改时报 `submission is not pending`

原因：该提交已经被批改过或状态不是 `pending`。

处理：按 `r` 刷新列表，重新选择 pending 提交。

### 10.3 分数带小数无法提交

模块 B 当前要求 `score` 是 0 到 100 的整数。HTTP 正式模式不要输入小数。

### 10.4 approved 和 graded 看起来不一致

这是设计上的兼容映射：

- 模块 B 正式状态是 `graded`。
- 模块 C UI 为兼容原本演示，显示为 `approved`。

接口层已经自动转换，不影响联调。

## 11. 注意事项

- HTTP 正式模式下，模块 C 不再本地生成正式反馈文件，反馈由模块 B 生成。
- 模块 B 当前 pending 接口不返回学生姓名和作业正文，C 端会展示 `student_id`、`assignment_id`、文件名、服务端归档路径和 MD5。
- 模块 B 返回的 `file_path`、`feedback_path` 是服务端本地路径，只用于展示，不要当作客户端可直接打开的本地路径。
