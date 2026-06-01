# 模块联调变更记录

记录日期：2026-05-28

本文档记录本轮围绕模块 A/B/C/D 全链路联调做出的变更，方便各组成员同步接口、状态和验收方式。

## 1. 模块 C：新增 HTTP 数据访问层

变更原因：

- 模块 C 原先只读取本地 SQLite Mock，无法看到模块 A 上传到模块 B 的真实 pending 提交。
- 权威工作文档要求模块 C 正式集成时调用模块 B 的 `GET /v1/submissions/pending` 和 `POST /v1/submissions/grade`。

变更内容：

- 新增 `controller/api_client.py`：实现模块 B HTTP 数据访问层。
- 新增 `controller/repository.py`：定义 TUI 使用的数据访问接口。
- 新增 `controller/sqlite_repo.py`：保留原 SQLite Mock 实现。
- 修改 `controller/tui.py`：TUI 不再直接调用 `db.py`，改为依赖 repository。
- 修改 `controller/config.py` 和 `.env.example`：新增 `CONTROLLER_SOURCE`、`CONTROLLER_API_BASE_URL`、`CONTROLLER_TEACHER_ID`、`CONTROLLER_REQUEST_TIMEOUT_SECONDS`。

使用方式：

```bash
CONTROLLER_SOURCE=http python scripts/run_controller.py
```

## 2. 模块 C：统一状态映射

变更原因：

- 模块 C 本地 Mock 使用 `approved`，模块 B 正式接口使用 `graded`。
- 如果不做映射，C 的 UI 状态和 B 的服务端状态无法互通。

变更内容：

- 新增 `controller/status.py`。
- 模块 C UI 可继续显示 `approved`。
- 模块 C HTTP 模式提交给模块 B 时使用 `graded`。
- 模块 C 从模块 B 读取到 `graded` 时映射为 UI 中的 `approved`。
- `rejected` 保持同名透传。

## 3. 模块 B：批改接口限制只能处理 pending

变更原因：

- 原模块 B 允许重复批改同一个 submission，第二次批改会覆盖第一次评分和评语。
- 权威工作文档要求“重复批改被拒绝”。

变更内容：

- 修改 `module_b_server/app/main.py` 中的 `POST /v1/submissions/grade`。
- 查询到提交后检查 `row["status"] == "pending"`。
- 非 `pending` 提交返回 400：`submission is not pending`。
- 新增 `module_b_server/tests/test_grade_pending_guard.py` 覆盖重复批改拒绝。

## 4. API 文档重写

变更原因：

- `/docs/api_spec.md` 内容不完整。
- 模块 C 旧文档仍包含 `APPROVE`、`approved`、`QUERY_PENDING` 等旧契约，和模块 B 真实接口冲突。

变更内容：

- 重写 `/docs/api_spec.md`。
- 重写 `/module_c_controller/docs/module_b_api_contract.md`。
- 文档统一为：
  - 作业 ID：`assignment_id`
  - 文件校验：`md5`
  - 待批改接口：`GET /v1/submissions/pending`
  - 批改接口：`POST /v1/submissions/grade`
  - 批改 action：`GRADE`
  - 服务端状态：`pending`、`graded`、`rejected`

## 5. 模块 D：一键验收入口

变更原因：

- 项目缺少统一验收入口，不能一条命令检查 A/B/C 基础测试和关键联调链路。

变更内容：

- 新增根目录 `Makefile`。
- 新增 `module_d_ops/`。
- 新增 `module_d_ops/scripts/verify_all.sh`。

当前命令：

```bash
make test
make verify
```

覆盖范围：

- 模块 A 单元测试。
- 模块 B 单元测试。
- 模块 C 单元测试。
- 模块 B smoke test。
- 启动模块 B 临时服务。
- 创建作业。
- 使用模块 A 自动打包、计算 MD5 并上传。
- 检查模块 B pending 列表中出现 A 的提交。
- 模块 D 验证脚本使用临时 workspace、cache 和 feedback 目录，避免误提交模块 A 旧工作区中的历史作业。

## 6. 测试隔离调整

变更原因：

- 模块 B 的重复批改测试如果直接写真实 `data/db/engine.db`，会污染联调数据库。
- 模块 D 调用模块 A 时如果使用默认 `workspace/`，可能把已有作业目录也提交一次。

变更内容：

- 模块 B 的 `test_grade_pending_guard.py` 改为使用临时 SQLite 数据库和临时 feedback 目录。
- 模块 D 的 `verify_all.sh` 改为给模块 A 注入临时 `MODULE_A_WORKSPACE_DIR`、`MODULE_A_CACHE_DIR`、`MODULE_A_FEEDBACK_DIR`。

## 7. 仍需注意

- 模块 C HTTP TUI 需要真实终端交互，当前自动脚本只覆盖其 HTTP 数据访问层单元测试。
- 模块 B 仍返回服务端本地绝对文件路径，客户端只能展示，不能当作下载协议。
- 模块 A 的最近提交快照目前保存在内存中，客户端重启后可能重复提交同一份未变化作业；后续建议增加本地状态文件。
