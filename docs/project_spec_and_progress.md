# Haocean Mooc CLI 项目 Spec 与进度对齐

更新时间：2026-06-08

本文档用于统一项目目标、产品范围、模块职责、核心链路、验收标准和当前进度。接口字段级细节以 `docs/api_spec.md` 为准；本文档关注项目级规格和交付状态。

## 1. 项目定位

Haocean Mooc CLI 是一个面向课程作业管理的终端化教学工具链。系统不以 Web 页面为主要交互入口，而是提供学生端 CLI、教师端 CLI/TUI 和服务端 API，完成课程作业从发布、提交、校验、批改、反馈、查重、统计到归档的完整闭环。

最终交付形态：

- 学生在自己的 Linux 终端安装并使用 `haocean-student`。
- 教师或助教在自己的 Linux 终端安装并使用 `haocean-teacher`。
- 服务端部署 `module_b_server`，通过 HTTPS 域名提供统一 API。
- 运维验收通过 `make test`、`make verify` 和 smoke test 自动检查主链路。

## 2. 目标用户和核心场景

### 2.1 学生

学生需要完成以下动作：

- 首次配置学号、Name、邮箱、服务端地址和可选班级加入码。
- 通过邮箱验证码登录并缓存 token。
- 通过加入码加入课程班级。
- 查看自己可见的开放作业。
- 将作业文件放入本地工作区。
- 手动提交某个作业，或启动 watcher 自动提交稳定后的文件。
- 拉取教师 Markdown 反馈并保存到本地。
- 在互评阶段给其他同学提交互评分。

### 2.2 教师 / 助教

教师或助教需要完成以下动作：

- 首次配置教师编号、Name、邮箱、服务端地址和下载目录。
- 通过邮箱验证码登录并缓存 token。
- 创建课程班级并生成学生加入码。
- 发布全局作业或绑定到指定班级的作业。
- 打开终端 TUI 查看待批改作业，输入分数和评语。
- 下载学生提交包到本机。
- 查看查重报告、成绩统计和学生历史成绩。
- 在互评结束后计算最终成绩。
- 课程结束时生成并下载归档包。

### 2.3 部署 / 验收人员

部署或验收人员需要完成以下动作：

- 在干净 Linux 环境安装依赖。
- 启动模块 B 服务。
- 配置 `student.haoceanlab.cn` 和 `teacher.haoceanlab.cn` 到同一服务。
- 运行单模块测试、服务端 smoke test 和 A -> B 真实提交流程。
- 检查异常输入、MD5 错误、权限边界、重复操作等场景。

## 3. 非目标范围

当前项目不以以下内容为主要目标：

- 不做完整 Web LMS 前端。
- 不提供在线代码编辑器。
- 不替代 Git、OJ 或复杂考试监考系统。
- 查重支持本地 token 预筛、hybrid AI 复核和 AI 限流；候选范围包含当前作业内同期提交，以及当前作业提交与最近三年历史提交的交叉比较。
- 当前数据存储以 SQLite 和本地文件归档为主，不要求分布式数据库或对象存储。

## 4. 系统架构

### 4.1 模块结构

```text
module_a_client/       学生端 CLI：haocean-student
module_b_server/       FastAPI 服务端：认证、作业、提交、批改、反馈、统计
module_c_controller/   教师端 CLI/TUI：haocean-teacher
module_d_ops/          自动化验收、联调脚本
docs/                  API、部署、项目级文档
install-student.sh     学生端一键安装脚本
install-teacher.sh     教师端一键安装脚本
```

### 4.2 运行拓扑

```text
Student Linux terminal
  haocean-student
        |
        | HTTPS: student.haoceanlab.cn
        v
Module B FastAPI service
  SQLite + data/submissions + data/feedback + data/archives
        ^
        | HTTPS: teacher.haoceanlab.cn
        |
Teacher Linux terminal
  haocean-teacher + Textual TUI
```

`student.haoceanlab.cn` 和 `teacher.haoceanlab.cn` 可以指向同一个模块 B 服务。角色隔离由登录角色、token 和服务端权限判断完成。

## 5. 核心业务闭环

### 5.1 班级和作业发布

1. 教师登录 `haocean-teacher`。
2. 教师创建班级，系统生成或保存加入码。
3. 学生通过加入码加入班级。
4. 教师创建作业，可以绑定某个班级，也可以作为全局作业。
5. 学生端只展示自己有权限看到的开放作业。

### 5.2 学生提交

1. 学生在 `~/.haocean/workspace/{assignment_id}/` 下放置作业文件。
2. 学生执行 `haocean-student submit {assignment_id}`，或启动 `haocean-student watch`。
3. 学生端过滤缓存、虚拟环境、历史压缩包等非作业文件。
4. 学生端打包为 `tar.gz`，计算 MD5。
5. 学生端调用模块 B 的提交接口，上传 metadata 和文件。
6. 模块 B 重新计算 MD5，不一致则拒绝。
7. 模块 B 将合法提交归档到服务端文件目录，并写入 SQLite。
8. 提交进入 `pending` 状态。

### 5.3 教师批改和反馈

1. 教师打开 `haocean-teacher tui`。
2. 教师端从模块 B 拉取待批改、已批改或全部提交。
3. 教师查看提交信息，可以下载提交包。
4. 教师输入分数、评语和结果状态。
5. 模块 B 更新提交记录，并生成 Markdown 反馈文件。
6. 学生执行 `haocean-student feedback` 或 watcher 定期同步反馈。

### 5.4 查重、统计、互评和归档

1. 教师触发或查看作业查重结果。
2. 服务端读取提交包中的文本/代码内容，先做 token 预筛，再按 `token` / `hybrid` / `ai` 模式输出疑似对。
3. 教师查看成绩统计和学生历史成绩。
4. 对启用互评的作业，学生提交互评分。
5. 教师触发最终成绩计算。
6. 课程结束后生成归档 zip，教师下载作业文件集合。

## 6. 权限和认证规格

### 6.1 登录

- 学生和教师均使用邮箱验证码登录。
- 登录成功后客户端缓存 token。
- 客户端后续请求通过 `Authorization: Bearer <token>` 访问服务端。
- 本地开发可关闭认证，或启用开发验证码日志。

### 6.2 学生权限

- 学生只能加入有效加入码对应的班级。
- 学生只能查看全局开放作业和自己已加入班级下的开放作业。
- 学生只能提交自己可见且开放的作业。
- 学生只能查询自己的反馈和历史相关数据。
- 学生不能给自己的提交互评。

### 6.3 教师权限

- 教师可以创建自己的班级。
- 教师可以发布全局作业或自己班级下的作业。
- 教师只能查看、下载、批改自己创建作业或自己班级下的提交。
- 教师可以查看作业查重、统计、历史成绩和课程归档。

## 7. 数据和状态规格

### 7.1 主要实体

- `auth_codes`：邮箱验证码。
- `auth_tokens`：登录 token。
- `classes`：课程班级和加入码。
- `class_members`：学生入班记录。
- `assignments`：作业。
- `submissions`：学生提交记录。
- `peer_review_configs`：作业互评配置。
- `peer_review_tasks`：互评任务。
- `peer_reviews`：互评分。
- `final_scores`：最终成绩。
- `plagiarism_reports`：查重报告。
- `archives`：课程归档包。

### 7.2 状态

作业状态：

- `open`：开放提交。

提交状态：

- `pending`：已接收，等待批改。
- `graded`：已评分。
- `rejected`：被打回或拒绝。

教师端本地 UI 历史上使用过 `approved`，正式 HTTP 接口必须映射到服务端的 `graded`。

## 8. 客户端命令规格

### 8.1 学生端 `haocean-student`

核心命令：

```bash
haocean-student setup
haocean-student login
haocean-student profiles
haocean-student join JOIN101
haocean-student classes
haocean-student list
haocean-student preview home_001
haocean-student submit home_001
haocean-student watch
haocean-student feedback
haocean-student peer-review 21 95 --comment "完成较好"
haocean-student ai-help "怎么提交作业？"
haocean ai-help
```

默认本地目录：

```text
~/.haocean/config.json
~/.haocean/auth_tokens/
~/.haocean/workspace/
~/.haocean/cache/archives/
~/.haocean/feedback_inbox/
~/.haocean/logs/haocean.log
```

学生端支持多组本地 profile。`setup --profile <name>` 创建或更新一组身份；`login` 会先选择 profile，再发送邮箱验证码；每个 profile 使用独立 token 文件。旧版单配置和 `~/.haocean/auth_token` 仍然兼容，新的 profile 写入会自动迁移。

### 8.2 教师端 `haocean-teacher`

核心命令：

```bash
haocean-teacher setup
haocean-teacher login
haocean-teacher profiles
haocean-teacher class
haocean-teacher select
haocean-teacher publish
haocean-teacher publish home_001 "Homework 1" --peer-review --teacher-weight 0.7
haocean-teacher grade home_001
haocean-teacher peer-review home_001
haocean-teacher classes create "CS101 Spring" --class-id cs101
haocean-teacher classes list
haocean-teacher assignment create home_001 "Homework 1" --class-id cs101
haocean-teacher assignment view home_001
haocean-teacher tui
haocean-teacher download 21 --extract
haocean-teacher plagiarism home_001
haocean-teacher stats home_001
haocean-teacher history 2024001
haocean-teacher final-scores home_final --calculate
haocean-teacher archive create --name course_archive.zip
haocean-teacher archive list
haocean-teacher archive download course_archive.zip
```

默认本地目录：

```text
~/.haocean-teacher/config.json
~/.haocean-teacher/auth_tokens/
~/.haocean-teacher/downloads/
~/.haocean-teacher/logs/haocean-teacher.log
```

教师端支持多组本地 profile。`setup --profile <name>` 创建或更新一组身份；`login` 会先选择 profile，再发送邮箱验证码；每个 profile 使用独立 token 文件。`grade <assignment_id>` 总览中输入 `pr` 可将已开启互评的作业切到 `peer_review` 阶段并自动分配任务；`peer-review <assignment_id>` 是同一能力的快捷命令。

需要互评的作业应在发布阶段决定，交互式 `publish` 会询问 `Peer Review`，非交互式可使用 `--peer-review` / `--no-peer-review`。开启后作业仍先收集提交，之后再切到互评阶段并分配任务。

## 9. 服务端 API 范围

详细字段以 `docs/api_spec.md` 为准。项目级 API 范围包括：

- 健康检查：`GET /health`
- 认证：`POST /v1/auth/request-code`、`POST /v1/auth/login`
- 班级：`POST /v1/classes`、`GET /v1/classes`、`POST /v1/classes/join`、`GET /v1/classes/my`
- 作业：`POST /v1/assignments`、`GET /v1/assignments/open`
- 提交：`POST /v1/submissions`、`GET /v1/submissions`、`GET /v1/submissions/pending`
- 下载：`GET /v1/submissions/{submission_id}/download`
- 批改：`POST /v1/submissions/grade`
- 反馈：`GET /v1/feedback/{student_id}`
- 互评：`POST /v1/assignments/peer-review/config`、`POST /v1/assignments/{assignment_id}/peer-review/stage`、`POST /v1/assignments/{assignment_id}/peer-review/tasks/auto`、`GET /v1/peer-review/tasks/my`、`POST /v1/peer-reviews`
- 成绩：`POST /v1/assignments/{assignment_id}/calculate-final-scores`、`GET /v1/assignments/{assignment_id}/final-scores`、`GET /v1/assignments/{assignment_id}/score-stats`、`GET /v1/students/{student_id}/score-history`
- AI 报告：`GET /v1/submissions/{submission_id}/ai-grade-report`，读取 `DEEPSEEK_API_KEY` / `MODULE_B_DEEPSEEK_API_KEY`，未配置时返回本地结构化报告
- 查重：`GET /v1/assignments/{assignment_id}/plagiarism`、`GET /v1/submissions/{submission_id}/plagiarism`、`POST /v1/plagiarism/check`、`GET /v1/plagiarism/reports/{assignment_id}`
- 归档：`POST /v1/archives/course`、`GET /v1/archives`、`GET /v1/archives/download/{archive_name}`

## 10. 非功能规格

### 10.1 文件安全

- 上传文件必须重新计算 MD5。
- 上传文件名必须清理路径，防止路径穿越。
- 作业包默认排除缓存、虚拟环境、数据库、日志和历史压缩包。
- 教师端解压提交包时必须校验成员路径，禁止解压到目标目录外。

### 10.2 网络可靠性

- 学生端和教师端 HTTP 请求必须设置 timeout。
- 学生端上传遇到服务端错误时应重试。
- watcher 不应因单次同步失败退出。

### 10.3 可部署性

- Python 版本要求为 3.10+。
- 学生端和教师端应可通过安装脚本安装为 CLI 命令。
- 服务端应可部署在 `127.0.0.1:8000`，再由 Caddy 等反向代理暴露 HTTPS 域名。

### 10.4 可测试性

- A/B/C 模块应有独立测试入口。
- B 模块应有 smoke test 覆盖主接口。
- D 模块应有全链路验收脚本，至少覆盖 A -> B 作业提交。

## 11. 当前进度对齐

### 11.1 总体结论

当前项目已经从早期“模块拆分任务书”推进到可联调的 CLI + API 工程形态。主闭环中的学生端、服务端、教师端和验收脚本均已存在。

当前最接近完成的主线是：

```text
教师创建作业 -> 学生查看作业 -> 学生打包上传 -> 服务端校验归档 ->
教师查看待批改 -> 教师评分反馈 -> 学生拉取反馈
```

高级能力也已进入实现阶段，包括认证、班级加入码、下载、互评、查重、统计和归档。

### 11.2 进度表

| 模块/能力 | 当前状态 | 说明 |
| --- | --- | --- |
| 学生 CLI 安装入口 | 已实现 | `pyproject.toml` 暴露正式学生命令 `haocean-student`，`haocean` 仅作为 `ai-help` 帮助入口 |
| 学生配置和登录 | 已实现 | 支持多 profile，`setup --profile` 创建/更新身份，`login` 选择身份后邮箱验证码登录，每个 profile 独立缓存 token |
| 学生加入班级 | 已实现 | 支持 `join` 和配置中的 `class_code` 自动加入 |
| 学生查看作业 | 已实现 | `list` 调用开放作业接口 |
| 学生打包提交 | 已实现 | 过滤非作业文件、生成 tar.gz、计算 MD5、上传 |
| 学生 watcher | 已实现 | 当前基于轮询和防抖，不是 systemd/inotify 版本 |
| 学生反馈拉取 | 已实现 | 反馈 Markdown 保存到本地 inbox |
| 学生互评提交 | 已实现 | `peer-review` 命令调用互评接口；自动分配默认每人 2 份，2 人时相互评 1 份 |
| AI 使用小助手 | 已实现 | `haocean ai-help` / `haocean-student ai-help` 读取 `DEEPSEEK_API_KEY` 调用 DeepSeek，未配置时输出本地帮助 |
| 服务端认证 | 已实现 | 支持验证码、token、角色上下文、开发日志验证码 |
| 服务端班级/加入码 | 已实现 | 支持创建班级、加入班级、班级作业可见性 |
| 服务端作业发布 | 已实现 | 支持创建作业和查询开放作业 |
| 服务端提交接收 | 已实现 | 支持 multipart 上传、MD5 校验、归档、入库 |
| 服务端批改反馈 | 已实现 | 支持评分、状态更新、Markdown 反馈 |
| 服务端提交下载 | 已实现 | 支持教师下载提交包，带权限检查 |
| 服务端查重 | 已实现 | 支持当前作业 + 近三年历史候选、本地 token 预筛、hybrid/AI DeepSeek 复核 |
| 服务端成绩统计 | 已实现 | 支持作业统计和学生历史成绩 |
| 服务端互评和最终成绩 | 已实现 | 支持互评配置、阶段、任务、评分、最终成绩计算 |
| 服务端课程归档 | 已实现 | 支持生成、列表、下载课程归档 zip |
| 教师 CLI 安装入口 | 已实现 | `pyproject.toml` 暴露 `haocean-teacher` |
| 教师配置和登录 | 已实现 | 支持多 profile，`setup --profile` 创建/更新身份，`login` 选择身份后邮箱验证码登录，每个 profile 独立缓存 token |
| 教师班级和作业命令 | 已实现 | 支持创建/查看班级、创建/查看作业工作台 |
| 教师 TUI 批改 | 已实现 | Textual TUI 支持列表、详情、评分、下载解压、.md/.txt 预览、AI 报告、查重和历史成绩弹窗 |
| 教师高级命令 | 已实现 | 支持查重、统计、历史、互评阶段、最终成绩、归档、下载 |
| C 本地 Mock 模式 | 保留 | `CONTROLLER_SOURCE=sqlite` 可用于演示和离线测试 |
| D 单元测试入口 | 已实现 | `make test` 调用 A/B/C 测试 |
| D 全链路验收 | 部分实现 | `make verify` 覆盖 B smoke 和 A -> B 真实提交 |
| 公网域名部署说明 | 已编写 | `domain_auth_smoke.md` 描述 DNS、Caddy 和认证 smoke |
| 统一日志规范 | 部分实现 | A/C 有本地日志配置，B 仍需进一步统一格式和落盘策略 |
| 一键安装全验收 | 部分实现 | 已有安装脚本和 Makefile，但干净机器一条命令完整部署仍需实测 |

### 11.3 按里程碑估算

| 里程碑 | 完成度 | 判断 |
| --- | --- | --- |
| M1：基础 A/B/C 作业闭环 | 约 85% | 代码已具备，仍需更多端到端验收和演示脚本 |
| M2：认证、班级和权限 | 约 80% | 主能力已实现，仍需公网真实 SMTP/DNS 场景验证 |
| M3：教师高级能力 | 已实现 | 下载、查重、统计、互评、归档和 TUI 快捷查看均已实现 |
| M4：自动化验收和交付 | 约 60% | `make test`、`make verify` 存在，干净环境部署还需压实 |
| M5：生产化稳定性 | 约 45% | 日志、异常恢复、数据迁移、服务管理、备份策略仍需补齐 |

### 11.4 本次验证结果

2026-06-08 在当前工作区执行：

```bash
make test
make verify
```

结果：

- `make test` 通过。
- 模块 A：19 个 unittest 通过。
- 模块 B：9 个 unittest 通过。
- 模块 C：23 个 pytest 测试通过。
- `make verify` 通过。
- `make verify` 已完成模块测试、启动模块 B 临时服务、执行模块 B smoke test，并通过模块 A 完成一次真实 A -> B 提交。

验证中观察到的问题：

- smoke/verify 当前使用 `module_b_server/data/db/engine.db` 运行库，输出里会混入历史 smoke 数据。
- 这不影响本次通过结论，但交付前应让 smoke/verify 使用隔离临时数据库，保证结果干净、可重复。

## 12. 主要风险和待办

### 12.1 P0：必须优先确认

- 后续每次合并前保持 `make test` 和 `make verify` 通过。
- 确认模块 B 的真实数据库初始化和历史迁移在空库、旧库两种情况下都可用。
- 确认认证开启后 A/C 的所有主命令都带上 token 且权限边界正确。
- 确认公网域名、Caddy、SMTP 验证码在真实服务器上可用。
- 确认教师端 TUI 在真实 HTTP 模式下批改、下载、刷新体验稳定。

### 12.2 P1：交付前需要补齐

- 将模块 B 日志统一为可定位问题的格式和落盘策略。
- 整理安装脚本，在干净 Ubuntu 上验证学生端和教师端安装。
- 给 `make verify` 增加 C -> B 批改、A 拉取反馈、MD5 错误拒绝等全链路断言。
- 明确重复批改策略：当前接口允许重新评分，应在验收文档中写清楚。
- 清理历史 backup 文件或标记其用途，避免评审时误读。

### 12.3 P2：可选增强

- watcher 可从轮询升级为 systemd/inotify 方案。
- 查重可继续增加更强的代码结构相似度特征和模板代码剔除能力。
- 归档可增加按班级、按作业、按学生的筛选导出。
- 教师 TUI 可继续增加文件树选择器；当前已支持 `.md` / `.txt` 优先预览。

## 13. 验收标准

最小可交付验收必须证明：

1. 教师可以创建班级并获得加入码。
2. 学生可以加入班级。
3. 教师可以发布班级作业。
4. 学生可以看到该作业。
5. 学生可以提交本地作业文件。
6. 服务端会校验 MD5 并保存提交。
7. 教师可以看到 pending 提交。
8. 教师可以下载提交包。
9. 教师可以评分并生成反馈。
10. 学生可以拉取反馈 Markdown。
11. 错误 MD5 会被拒绝。
12. 未授权学生不能提交非本班作业。
13. 教师不能下载或批改非自己权限范围内的提交。
14. `make test` 可通过。
15. `make verify` 可通过。

## 14. 当前工作结论

这个项目现在不是从零开始的需求草稿，而是一个已经具备主体功能的终端课程作业平台。后续工作重点不应再放在“要不要做这些模块”，而应放在以下三件事：

1. 用自动化和真实环境把主链路跑通。
2. 统一文档、接口、状态和验收口径。
3. 补齐部署、日志、异常和权限边界，保证最终演示和交付不翻车。
