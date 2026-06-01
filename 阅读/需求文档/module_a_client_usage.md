# 模块 A 客户端分发与使用说明

本文档面向模块 A 组员和学生端部署人员，说明需要接收哪些文件、如何配置、如何运行和如何验证。

## 1. 分发范围

建议直接分发整个目录：

```text
/Hao/gongchuang/module_a_client/
```

核心必需文件：

```text
module_a_client/
├── module_a/
│   ├── __init__.py
│   ├── api_client.py
│   ├── archive.py
│   ├── config.py
│   ├── feedback.py
│   ├── logger.py
│   ├── main.py
│   └── watcher.py
├── scripts/
│   └── run_client.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

不要分发运行产物：

```text
__pycache__/
*.pyc
.pytest_cache/
.venv/
workspace/
data/
feedback_inbox/
logs/
```

## 2. 环境准备

要求：

- Python 3.10+
- 能访问模块 B 服务，例如 `http://127.0.0.1:8000` 或服务器 IP

安装依赖：

```bash
cd module_a_client
pip install -r requirements.txt
```

复制配置文件：

```bash
cp .env.example .env
```

## 3. 配置说明

编辑 `.env`：

```dotenv
MODULE_A_SERVER_URL=http://模块B服务器IP:8000
MODULE_A_STUDENT_ID=学生学号
MODULE_A_WORKSPACE_DIR=workspace
MODULE_A_CACHE_DIR=data/archives
MODULE_A_FEEDBACK_DIR=feedback_inbox
MODULE_A_LOG_FILE=logs/module_a.log
MODULE_A_DEBOUNCE_SECONDS=3
MODULE_A_POLL_INTERVAL_SECONDS=1
MODULE_A_REQUEST_TIMEOUT_SECONDS=10
MODULE_A_RETRY_COUNT=3
MODULE_A_RETRY_BACKOFF_SECONDS=1
```

必须配置：

- `MODULE_A_SERVER_URL`：模块 B 服务地址。
- `MODULE_A_STUDENT_ID`：当前学生学号。

路径可以是相对路径，也可以是绝对路径。不要把个人路径写死在代码里。

## 4. 作业目录约定

模块 A 按模块 B 返回的 `assignment_id` 查找本地作业目录。

默认目录结构：

```text
workspace/{assignment_id}/
```

示例：

```text
workspace/home_001/main.py
workspace/home_001/report.md
```

如果作业 ID 是 `home_001`，学生需要创建：

```bash
mkdir -p workspace/home_001
```

然后把作业文件放入该目录。

## 5. 常用命令

查看开放作业：

```bash
python3 scripts/run_client.py list
```

执行一次同步：

```bash
python3 scripts/run_client.py once
```

后台持续监控：

```bash
python3 scripts/run_client.py watch
```

手动拉取反馈：

```bash
python3 scripts/run_client.py feedback
```

## 6. 工作流程

1. 模块 A 调用 `GET /v1/assignments/open` 获取开放作业。
2. 学生在 `workspace/{assignment_id}/` 中完成作业。
3. 模块 A 检测目录文件变化。
4. 文件停止变化后等待防抖时间，默认 3 秒。
5. 模块 A 将目录打包为 `tar.gz`。
6. 模块 A 计算压缩包 MD5。
7. 模块 A 调用 `POST /v1/submissions` 上传。
8. 模块 B 校验 MD5 并写入 pending。
9. 批改完成后，模块 A 调用 `GET /v1/feedback/{student_id}` 拉取反馈。
10. 反馈保存到 `feedback_inbox/{assignment_id}/submission_{submission_id}_feedback.md`。

## 7. 验证方式

运行模块 A 单元测试：

```bash
python3 -B -m unittest discover -s tests
```

联调验证前确认模块 B 已启动：

```bash
python3 scripts/run_client.py list
```

如果能列出开放作业，说明 A 到 B 的查询接口可用。

完成一次提交后，预期日志中出现：

```text
submission accepted: submission_id=... assignment_id=... status=pending
```

拉取反馈后，预期日志中出现：

```text
feedback saved: path=...
```

## 8. 常见问题

### 8.1 `MODULE_A_STUDENT_ID or STUDENT_ID is required`

原因：没有配置学生学号。

处理：在 `.env` 中设置：

```dotenv
MODULE_A_STUDENT_ID=2024001
```

### 8.2 看不到作业目录被提交

检查本地目录是否和模块 B 的 `assignment_id` 完全一致。

示例：

```text
assignment_id = home_001
目录必须是 workspace/home_001/
```

### 8.3 MD5 mismatch

原因：上传文件和 metadata 中的 MD5 不一致。模块 A 正常流程会自动计算 MD5，通常不会出现。若手动改包或网络中断，重新运行 `once` 或 `watch`。

### 8.4 模块 B 暂时不可用

模块 A 已设置超时和重试。后台模式会继续下一轮同步；手动模式可稍后重新执行：

```bash
python3 scripts/run_client.py once
```

## 9. 注意事项

- 模块 A 当前最近提交快照保存在内存中，客户端重启后可能重复提交同一份未变化作业。
- 模块 B 返回的 `archive_path` 和 `feedback_path` 是服务端路径，只用于展示，不要当成本地下载路径。
- 不要提交或分发 `workspace/`、`data/`、`feedback_inbox/`、`logs/` 等运行目录。
