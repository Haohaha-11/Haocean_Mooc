# Haocean Mooc CLI 报告事实核查材料

核查时间：2026-06-09
核查范围：`README.md`、`Makefile`、`docs/`、`module_a_client/`、`module_b_server/`、`module_c_controller/`、`module_d_ops/`、各模块测试。
限制说明：本材料只做事实核查，不润色最终报告；本次未修改源码。
补充说明：本文记录的是 2026-06-09 的核查快照。2026-06-10 后续又补充了截图 runbook、报告摘录和线上请求默认超时调整，最终演示步骤以最新 `docs/screenshot_capture_runbook.md` 为准。

## 一、项目结构核查结论

项目结构与 `docs/project_tree_for_report.txt` 基本一致，可按四个模块加公共文档描述：

- `module_a_client/`：学生端 CLI。入口来自 `module_a_client/pyproject.toml`，包含 `haocean-student = module_a.main:main` 和 `haocean = module_a.ai_help:main`。
- `module_b_server/`：FastAPI 服务端。核心实现集中在 `module_b_server/app/main.py`，使用 SQLite 和本地文件目录保存运行数据。
- `module_c_controller/`：教师端 CLI/TUI。入口来自 `module_c_controller/pyproject.toml`，包含 `haocean-teacher = controller.main:main`。
- `module_d_ops/`：自动化验收脚本，`module_d_ops/scripts/verify_all.sh` 被 `make verify` 调用。
- `docs/`：API、部署、学生/教师指南、实验报告草稿、PPT 提纲、目录树和本核查材料。

运行时目录如 `module_b_server/data/`、`module_a_client/workspace/`、`module_a_client/feedback_inbox/` 不建议作为源码结构重点展示。`module_b_server/README.md` 的目录结构中提到旧备份文件，当前报告应以 `docs/project_tree_for_report.txt` 和真实文件树为准。

## 二、学生端功能核查

学生端真实命令来自 `module_a_client/module_a/main.py` 的 `build_parser()`。确认存在的命令和作用如下：

- `setup`：写入学生本地配置/profile，配置 server URL、学号、姓名、邮箱、班级码、workspace。
- `login`：选择本地 profile，邮箱验证码登录，保存 token；如果配置了班级码，登录后尝试自动加入班级。
- `profiles`：列出本机学生 profiles。
- `guide`：打印安装到本机的学生使用指南。
- `join <class_code>`：按教师提供的班级加入码加入班级。
- `classes`：列出当前学生已加入班级。
- `list`：读取服务端开放作业列表；会显示作业、班级和 materials 标记。
- `materials <assignment_id> [--no-extract]`：下载作业材料到 workspace 下的 materials 目录；zip 默认安全解压。
- `preview <assignment_id> [--allow-zip]`：只预览提交包，不上传；列出 included/excluded/archive_members。
- `submit <assignment_id> [--dry-run] [--allow-zip]`：从 workspace 打包作业并上传；`--dry-run` 等价预览。
- `once`：运行一次同步/提交流程，会要求 assignment id 或使用配置过滤。
- `feedback`：拉取当前学生反馈并保存为 Markdown。
- `peer-review [submission_id score] [--assignment-id ...] [--comment ...]`：无分数时列出互评任务；提供提交编号和分数时提交互评。
- `ai-help [--local] <question>`：本机使用帮助助手；未配置 key 时使用本地 fallback。
- `watch`：持续轮询 workspace，文件稳定后自动提交。

测试覆盖情况：

- 学生端测试共 36 个，通过 `test_archive.py`、`test_api_client.py`、`test_auth.py`、`test_config.py`、`test_feedback.py`、`test_watcher.py`、`test_ai_help.py` 覆盖打包过滤、预览、提交 API、材料下载、Bearer token、班级、互评、profile、登录、watcher 防抖、反馈保存、AI help fallback。
- `watch`、`once`、`submit` 的核心逻辑有 watcher/API/打包测试覆盖，但 CLI 交互本身不是逐命令端到端覆盖；实现存在，但部分交互测试覆盖有限。

## 三、教师端功能核查

教师端真实命令来自 `module_c_controller/controller/main.py` 的 `build_parser()`。确认存在的命令和作用如下：

- `setup`：写入教师本地配置/profile，配置 api base URL、教师编号、姓名、邮箱、下载目录。
- `login`：选择教师 profile，邮箱验证码登录并保存 token。
- `profiles`：列出本机教师 profiles。
- `guide`：打印安装到本机的教师使用指南。
- `class`：交互式创建班级并保存当前班级。
- `classes list`：列出教师可管理班级和加入码。
- `classes create <class_name>`：非交互创建班级，可指定 course/class/join code。
- `select`：从教师班级列表中选择当前班级。
- `publish [assignment_id title]`：交互或参数式发布作业，可绑定班级、说明、截止时间、materials、权重、互评开关。
- `assignment list`：列出已发布作业。
- `assignment create <assignment_id> <title>`：非交互创建作业，可上传 materials，可开启互评。
- `assignment view <assignment_id>`：查看作业 workspace/统计/查重等概览。
- `grade [assignment_id]`：批改总览入口，能查看 pending/graded/all、查重、成绩统计、最终成绩、互评阶段、进入 TUI。
- `tui [assignment_id]`：打开 Textual 批改 TUI。
- `download <submission_id> [--extract]`：下载单份提交包，可安全解压 tar 包。
- `plagiarism <assignment_id> [--check] [--method token|hybrid|ai]`：查看查重报告；加 `--check` 时触发查重。
- `stats <assignment_id>`：查看作业成绩统计。
- `history <student_id>`：查看某学生历史成绩。
- `final-scores <assignment_id> [--calculate]`：普通模式从成绩统计中展示最终成绩字段；`--calculate` 调用服务端重新计算最终成绩接口。
- `peer-review <assignment_id> [--stage ...] [--assign|--no-assign]`：切换互评阶段，默认进入 peer_review 阶段并自动分配任务。
- `archive create/list/download`：创建、列出、下载课程归档包。

TUI 批改功能确认存在。证据来自 `module_c_controller/controller/tui.py`、`module_c_controller/README.md` 和 `test_tui.py`。TUI 支持 pending/graded/all 视图、提交包下载与安全解压、优先打开 `.md`/`.txt`、评分、查看成绩统计、AI 审阅报告和查重结果。TUI 的完整人工交互体验需要截图或演示补充；实现存在，但自动测试覆盖有限。

测试覆盖情况：

- 教师端测试共 44 个，覆盖教师 API client、Bearer token、DeepSeek header、班级/作业/材料/查重/互评/统计接口、profile/login、deadline 解析、grade overview 互评入口、TUI 安全解压和可读文件选择。
- 本地 SQLite mock 相关文件和测试仍存在，当前真实 HTTP CLI 能力以 `controller/main.py` 和 `controller/api_client.py` 为准。

## 四、服务端功能核查

服务端真实能力来自 `module_b_server/app/main.py` 路由、README、API 文档和测试。逐项结论如下：

- 认证：已实现。`POST /v1/auth/request-code` 和 `POST /v1/auth/login` 支持邮箱验证码和 session token；测试覆盖有效/无效验证码。
- 班级管理：已实现。教师创建/列出班级，学生通过 join code 加入并查看自己的班级；测试覆盖班级作业可见性和同一教师重复班级名拒绝。
- 作业发布：已实现。`POST /v1/assignments` 创建作业，可绑定班级、权重、互评配置；教师端 publish/assignment create 调用该能力。
- materials 下载：已实现。教师上传/查询/下载作业材料，学生端下载 materials 并安全解压 zip；测试覆盖上传、metadata、班级成员下载权限。
- 作业提交：已实现。学生上传 multipart 表单，服务端校验 MD5、保存文件、写入 submissions。
- 重复提交覆盖：已实现。相同学生同一作业再次提交会复用原 submission row，重置为 pending 并清空旧分数/评语/反馈；测试覆盖。
- 截止时间校验：已实现。服务端解析 deadline，超过截止时间拒绝提交；测试覆盖。
- 教师批改：已实现。`POST /v1/submissions/grade` 写入分数、评语、状态和反馈文件；`test_grade_pending_guard.py` 覆盖已评分提交可更新策略。
- 反馈生成：已实现。批改后生成 Markdown 反馈，学生通过 `GET /v1/feedback/{student_id}` 拉取；smoke/verify 也覆盖提交、批改、反馈链路。
- AI 审阅：已实现。`GET /v1/submissions/{submission_id}/ai-grade-report` 无 key 时使用本地结构化 fallback，有 key 或教师端 header 时调用 DeepSeek；测试覆盖 fallback、schema 刷新、prompt 包含作业要求和 DeepSeek 请求构造。真实外部模型质量依赖可用 key 和网络。
- 查重：已实现。支持 token、hybrid、ai；包含同作业和近三年历史候选比较。测试覆盖 token 报告、缺 key 报错、hybrid 调用 DeepSeek、教师 header key、教师范围隔离。真实 hybrid/ai 外部效果依赖 key 和网络。
- 互评：已实现。支持配置、阶段切换、自动分配任务、学生提交互评；测试覆盖阶段门控、自动分配、非法互评拒绝。
- 成绩统计：已实现。`GET /v1/assignments/{assignment_id}/score-stats` 和 `GET /v1/students/{student_id}/score-history` 返回统计和历史成绩；测试覆盖。
- 最终成绩：已实现。`POST /v1/assignments/{assignment_id}/calculate-final-scores` 和 `GET /v1/assignments/{assignment_id}/final-scores` 存在；测试覆盖权重、peer_avg、peer_bonus、final_score。
- 课程归档：已实现。`POST /v1/archives/course`、`GET /v1/archives`、`GET /v1/archives/download/{archive_name}` 存在；归档写入过滤后的作业文件和 `scores/assignment_scores.csv`、`scores/course_final_scores.csv`。测试覆盖扁平化、过滤规则、zip 提交解包、防嵌套压缩包、成绩 CSV 和教师归档权限。
- 教师数据隔离：已实现。认证开启时教师只能管理/查看自己创建的作业或自己班级下作业；测试覆盖下载、成绩统计、历史成绩、最终成绩、查重、互评配置、归档等权限。
- 学生数据隔离：已实现。认证开启时学生只能看可见作业、下载自己班级材料、提交自己可提交作业、查自己的反馈/互评任务。测试覆盖班级可见性、materials 权限、提交权限和学生历史成绩自查限制。

## 五、安全与数据隔离核查

可写入报告的安全边界：

- 认证边界由服务端强制执行，不依赖客户端隐藏。`AUTH_REQUIRED` 开启后，`require_student` 和 `require_teacher` 约束主要路由。
- 学生隔离：班级作业仅对已加入该班级的学生可见；班级 materials 下载拒绝非班级学生；提交和反馈按学生身份收紧。
- 教师隔离：教师班级、作业、下载、批改、查重、统计、最终成绩、归档等操作按教师归属收紧。
- 文件安全：服务端使用安全文件名/存储组件，学生端 preview 默认排除缓存、虚拟环境、日志、数据库和历史压缩包；教师端/TUI 解压提交包检查路径穿越；课程归档二次过滤并扁平化导出作业文件。
- 完整性：学生提交包含 MD5，服务端重新计算并校验。

需要谨慎表述：

- `AUTH_REQUIRED=false` 时存在本地联调兼容模式，不应用完整跨用户隔离。真实部署必须说明开启认证。
- HTTPS、Caddy、systemd、SMTP 属于文档和环境配置能力；本次未执行公网或 systemd 状态核验，需人工确认。

## 六、测试与验证结果

### `git status --short`

当时执行结果：

```text
 M docs/ppt_outline.md
?? docs/project_tree_for_report.txt
?? docs/report_audit_material.md
?? "阅读/需求文档/拓展功能.md"
```

说明：本次任务只允许修改 `docs/report_audit_material.md`。上述其他改动/未跟踪文件为核查时工作区已有状态或先前生成文件，未修改源码。

### `make test`

结果：通过，退出码 0。

```text
module_a_client: 36 passed in 0.36s
module_b_server: Ran 25 tests in 9.527s, OK
module_c_controller: 44 passed in 0.94s
```

总计：105 个测试通过。

### `VERIFY_B_PORT=19080 make verify`

结果：通过，退出码 0。

关键摘要：

```text
[Module_D] [1/7] Running module tests
module_a_client: 36 passed
module_b_server: Ran 25 tests, OK
module_c_controller: 44 passed
[Module_D] [2/7] Starting Module B server
[Module_D] [3/7] Running Module B smoke test
[Module_D] [4/7] Creating assignment for Module A integration
[Module_D] [5/7] Submitting with Module A
[Module_D] [6/7] Checking pending submission
[Module_D] [7/7] Verification completed
```

观察：启动等待阶段出现一次 `curl: (7) Failed to connect to 127.0.0.1 port 19080`，脚本随后继续等待并成功完成。verify 输出混入历史运行库中的作业/反馈数据，因为临时服务使用当前 `module_b_server/data/db/engine.db`，最终结果仍为通过。

## 七、可写入最终报告的真实亮点

- 学生端和教师端均为真实 CLI 入口：`haocean-student`、`haocean-teacher`，并通过同一个 FastAPI 服务交互。
- 学生作业流完整：setup/login/join/list/materials/preview/submit/feedback/peer-review/watch。
- 教师管理流完整：class/select/publish/grade/TUI/download/plagiarism/stats/history/final-scores/archive。
- 服务端覆盖课程作业闭环：认证、班级、作业、材料、提交、批改、反馈、查重、AI 审阅、互评、成绩、归档。
- 服务端强制数据隔离：认证开启后，学生/教师权限按角色、班级、作业归属约束。
- 作业文件处理有多层防护：学生端提交包过滤、MD5 校验、教师端安全解压、课程归档过滤和扁平化。
- AI 能力可降级：无 DeepSeek key 时 AI 审阅有本地 fallback；查重可使用 token 模式。
- 自动化验收链路可复现：`make test` 和 `VERIFY_B_PORT=19080 make verify` 本次均通过。

## 八、需要谨慎表述的内容

- “已部署为 systemd 长期服务”：代码和文档提供长期运行建议，但本次未检查真实服务器 service 状态；需人工确认。
- “HTTPS 域名真实可用”：README 和 `docs/domain_auth_smoke.md` 提供域名/Caddy 说明，本次未从公网核验；需人工确认。
- “真实 DeepSeek 审阅/AI 查重效果”：代码和测试支持调用，自动测试主要验证 fallback、请求格式和 monkeypatch 响应；真实效果依赖 key、网络和模型返回。
- “TUI 交互体验”：TUI 实现存在，测试覆盖安全解压和可读文件选择等基础逻辑；完整体验建议用截图或录屏佐证。
- “大规模真实学生测试”：若最终报告写 15 人或更多真实环境验收，需要补充日志、截图或名单脱敏证据；本次只复跑自动化测试和 verify。
- `module_c_controller/docs/module_c_handoff.md` 含有历史 mock 模式描述，不宜作为当前教师端真实 HTTP 能力的依据。

## 九、建议删减或合并的报告内容

- 安装命令、默认域名、PATH 配置在 README、学生指南、教师指南中重复较多，最终报告保留一次即可。
- AI 审阅、查重、互评、最终成绩可合并为“智能辅助与评价体系”，避免分散重复。
- systemd、Caddy、HTTPS、SMTP 建议统一放在“部署与运维”一节，并标注已验证项和需人工确认项。
- 测试输出不要粘贴完整 verify stdout；保留 105 个测试通过和 `[7/7] Verification completed`。
- 不建议把 `module_b_server/data/`、临时数据库、历史 smoke 输出作为源码成果展示。

## 十、建议最终报告结构

1. 项目背景与目标：说明面向 Linux CLI 的课程作业提交、批改和归档场景。
2. 系统架构：Module A 学生端、Module B 服务端、Module C 教师端、Module D 验收脚本；说明 CLI -> FastAPI -> SQLite/文件存储链路。
3. 学生端功能：setup/login/join/list/materials/preview/submit/watch/feedback/peer-review/ai-help。
4. 教师端功能：class/select/publish/grade/TUI/download/plagiarism/stats/history/final-scores/archive。
5. 服务端核心实现：认证、班级、作业、材料、提交、批改、反馈、AI、查重、互评、成绩、归档。
6. 安全与数据隔离：学生隔离、教师隔离、MD5、安全解压、提交包过滤、归档过滤。
7. 测试与验证：写入本次 `make test` 105 个测试通过和 `VERIFY_B_PORT=19080 make verify` 通过。
8. 部署与运维：安装脚本、服务端长期运行、Caddy/HTTPS/SMTP；未核验项明确写需人工确认。
9. 问题与改进：真实 DeepSeek/HTTPS/systemd 依赖环境证据，verify 使用历史运行库会混入旧数据，后续可考虑独立测试库、CI、对象存储、Web 看板。
