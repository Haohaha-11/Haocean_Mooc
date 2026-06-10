# Haocean Mooc CLI 实验报告

## 摘要

Haocean Mooc CLI 是一个面向 Linux 课程场景的命令行课程作业管理系统。项目最初来自一个很直接的想法：既然课程本身强调 Linux 使用，那么作业提交、资料下载、反馈获取和教师批改这些真实课程流程，也可以放到 Linux 命令行中完成。围绕这一目标，项目逐步扩展为由学生端 CLI、教师端 CLI/TUI、FastAPI 服务端和自动化验证脚本组成的综合系统，覆盖班级管理、作业发布、材料下载、作业预览、作业提交、教师批改、反馈生成、AI 审阅、查重、互评、成绩统计、课程归档和服务端数据隔离等完整流程。

本项目强调“在真实任务中使用 Linux”。学生不是孤立练习几个命令，而是在完成作业的过程中持续接触路径管理、文件组织、压缩归档、命令行参数、网络请求、日志和反馈文件。教师也可以在 Linux 终端中完成课程管理操作。项目最终完成了本地测试、端到端验证、fresh GitHub clone 验证、真实环境流程测试和长期服务部署，具备真实运行和继续扩展的基础。

## 一、项目背景

Linux 课程的学习目标不应只停留在记忆命令或完成若干孤立实验。真正有价值的学习体验来自于把 Linux 放进实际工作流中使用。传统课程作业平台通常以网页为中心，学生提交作业时只需要点击按钮上传文件，Linux 只出现在课堂练习中，与真实课程流程之间存在割裂。

因此，我们提出了 Haocean Mooc CLI 的设计想法：让作业提交这个高频课程场景发生在 Linux 终端中。学生需要在本地 workspace 中整理作业，使用命令查看任务、下载资料、预览提交包、提交作业并拉取反馈。教师也在终端中完成建班、发布、批改、查重、统计和归档。这样，Linux 不再只是课程内容，而成为课程运行方式本身。

项目从“Linux 提交作业”这一最小想法出发，后续逐步补充了认证、班级、材料、AI 审阅、查重、互评、成绩统计、课程归档和教师数据隔离等能力，最终形成了一套较完整的命令行课程管理系统。

## 二、项目目标

本项目的核心目标包括：

1. 为学生提供一个 Linux 命令行作业客户端，支持配置、登录、加入班级、查看作业、下载材料、预览提交包、提交作业、查看反馈和参与互评。
2. 为教师提供一个 Linux 命令行管理客户端，支持建班、发布作业、查看提交、下载作业包、批改作业、查看查重结果、统计成绩、计算最终成绩和导出课程归档。
3. 提供一个稳定的服务端，统一处理认证、权限、班级、作业、材料、提交、反馈、AI 审阅、查重、互评和成绩计算。
4. 建立服务端强制的数据隔离机制，确保学生只能访问自己有权限的班级和作业，教师只能访问自己创建的作业或自己班级下的作业。
5. 提供自动化测试、端到端验证、安装脚本和部署方案，使项目可以真实运行，而不是只停留在演示代码或单机脚本阶段。
6. 通过 AI 审阅、查重和互评等功能，增强系统在课程管理中的辅助评价能力。

## 三、系统总体架构

项目采用模块化设计，主要分为四个模块：学生端 Module A、服务端 Module B、教师端 Module C 和运维验收 Module D。整体交互链路如下：

```text
学生端 CLI / 教师端 CLI
        ↓
     HTTP API
        ↓
 FastAPI 服务端
        ↓
SQLite 数据库 + 本地文件存储
```

其中，学生端和教师端负责命令行交互，服务端负责统一业务逻辑和权限控制，SQLite 保存结构化数据，本地文件系统保存作业材料、提交包、反馈文件和归档文件。Module D 则用于自动化验证，保证 CLI 到服务端的主链路可以稳定跑通。

### 1. Module A：学生端 CLI

Module A 提供 `haocean-student` 命令，是学生使用系统的入口。它负责读取本地配置、管理 profile、保存登录 token、调用服务端 API、组织本地 workspace、生成提交包、计算 MD5、上传作业和保存反馈。

学生端支持的主要命令包括：

```bash
haocean-student setup
haocean-student login
haocean-student join <class_code>
haocean-student classes
haocean-student list
haocean-student materials <assignment_id>
haocean-student preview <assignment_id>
haocean-student submit <assignment_id>
haocean-student feedback
haocean-student peer-review
haocean-student watch
haocean ai-help <question>
```

其中，`setup` 用于写入学生本地配置，`login` 用于邮箱验证码登录并保存 token，`join` 用于通过班级加入码加入课程班级，`list` 用于查看当前可见作业，`materials` 用于下载教师发布的材料，`preview` 用于提交前检查归档内容，`submit` 用于正式提交作业，`feedback` 用于拉取教师反馈，`peer-review` 用于查看或提交互评任务，`watch` 用于监听 workspace 并在文件稳定后自动提交。

### 2. Module B：FastAPI 服务端

Module B 是系统核心，基于 FastAPI 实现。服务端提供认证、班级、作业、材料、提交、批改、反馈、AI 审阅、查重、互评、成绩统计、最终成绩和课程归档相关 API。服务端使用 SQLite 保存结构化数据，使用本地文件系统保存材料、提交包、反馈和归档文件。

Module B 同时负责关键安全边界。认证开启后，学生和教师的访问权限由服务端统一检查，而不是依赖客户端隐藏菜单。例如，学生只能访问自己可见的作业，教师只能管理自己创建的作业或自己班级下的作业，查重历史候选和课程归档也必须按教师可访问范围过滤。

### 3. Module C：教师端 CLI/TUI

Module C 提供 `haocean-teacher` 命令，是教师使用系统的入口。它负责教师登录、班级管理、作业发布、提交查看、提交包下载、交互式批改、AI 报告查看、查重结果查看、成绩统计、最终成绩计算、互评阶段管理和课程归档。

教师端支持的主要命令包括：

```bash
haocean-teacher setup
haocean-teacher login
haocean-teacher class
haocean-teacher classes list
haocean-teacher classes create <class_name>
haocean-teacher select
haocean-teacher publish
haocean-teacher assignment list
haocean-teacher assignment create <assignment_id> <title>
haocean-teacher grade <assignment_id>
haocean-teacher tui <assignment_id>
haocean-teacher download <submission_id>
haocean-teacher plagiarism <assignment_id>
haocean-teacher stats <assignment_id>
haocean-teacher history <student_id>
haocean-teacher final-scores <assignment_id> --calculate
haocean-teacher peer-review <assignment_id>
haocean-teacher archive create
haocean-teacher archive list
haocean-teacher archive download
```

其中，`grade` 是教师端批改总览入口，`tui` 提供基于 Textual 的交互式批改界面，`plagiarism` 用于查看或触发查重，`stats` 和 `final-scores` 用于成绩统计和最终成绩计算，`archive` 用于课程归档的创建、查看和下载。

### 4. Module D：运维和验证

Module D 提供自动化验收脚本，主要入口是 `make verify`。该流程会依次运行各模块测试、启动临时 Module B 服务、执行服务端 smoke test、通过学生端 CLI 提交作业，并检查服务端 pending submission。

这一模块保证项目不是只在单个函数层面可用，而是能够完整验证从学生端命令行到服务端提交记录生成的主链路。

## 四、关键功能设计与实现

### 1. Linux 原生命令行作业流

学生端把作业流程放到 Linux 命令行中完成。学生在本地 workspace 中准备作业文件，通过 `preview` 预览将要提交的内容，再通过 `submit` 打包上传。这个过程让学生自然接触目录结构、文件路径、压缩归档、MD5 校验和命令行交互。

设计时重点考虑了真实使用习惯。学生不需要记忆复杂 API，只需要围绕作业流程使用几个清晰命令：`list` 查看任务，`materials` 下载资料，`preview` 检查本地目录，`submit` 提交当前作业，`feedback` 拉取教师反馈。这样既降低了使用门槛，也把 Linux 操作自然嵌入课程任务中。

### 2. 班级、作业材料和截止时间

教师可以创建班级并生成加入码，学生通过加入码加入班级。教师发布作业时可以绑定班级，也可以附带材料文件或材料目录。学生端看到作业包含 materials 后，可以通过命令下载到本地 workspace。

作业支持截止时间。服务端在接收提交时进行 deadline 校验，过期作业会拒绝提交。这保证规则由服务端执行，而不是依赖客户端自觉判断。该功能在测试中已覆盖过期作业提交失败等情况。

### 3. 提交包预览、过滤与 MD5 校验

学生端在正式提交前提供 `preview` 命令，用于展示提交包中包含的文件和被过滤的文件。默认过滤内容包括缓存目录、虚拟环境、日志、数据库、历史压缩包和版本控制目录等，避免学生把无关文件或临时文件提交到服务器。

正式提交时，学生端会生成提交包并计算 MD5。服务端接收文件后重新计算 MD5 并进行比对，从而确认上传文件完整性。这个设计可以减少因网络传输或文件错误导致的提交异常。

### 4. 重复提交覆盖

同一学生对同一作业重复提交时，系统采用覆盖旧提交的策略，并保留同一个 `submission_id`。覆盖时会清空旧分数、旧评语、旧反馈路径和旧 AI 报告缓存，将状态重新置为 pending。

这样做可以避免多次提交导致批改入口、反馈入口和成绩统计混乱。教师看到的是学生最新一次提交，学生也不会因为重复提交产生多个难以区分的记录。

### 5. 教师端批改和反馈

教师端可以查看待批改、已批改和全部提交。批改时，教师可以下载并解压学生提交包，预览其中的文本文件，填写分数和评语。项目还提供 Textual TUI，用于在终端中更方便地切换提交、查看内容和完成批改。

批改完成后，服务端会生成 Markdown 格式反馈，学生端可以通过 `feedback` 命令拉取。反馈文件包含提交编号、学生学号、作业编号、批改教师、批改时间、分数和评语，便于学生保存和复查。

### 6. AI 审阅

AI 审阅是项目的特色功能之一。系统不仅读取学生提交内容，还会读取教师发布的作业描述和 materials 文本，使 AI 报告更贴合作业要求。

AI 审阅报告采用结构化格式，包含：

* summary
* requirement checks
* strengths
* concerns
* suggestions
* score rationale
* requirements excerpt

如果服务端或教师端提供 DeepSeek key，系统会调用 DeepSeek API 生成审阅报告；如果没有 key，则返回本地结构化 fallback 报告，保证教师端功能不会完全不可用。报告带有 schema version，旧格式缓存会自动刷新，避免报告结构升级后出现兼容问题。

### 7. 查重

查重支持 token、AI 和 hybrid 三种模式。基础 token 查重会提取文本内容并计算相似度，AI 和 hybrid 模式用于进一步判断候选对。

查重范围包括当前作业和近三年历史提交。为了避免数据泄露，认证开启后，历史候选只来自当前教师可访问的作业，也就是教师自己的作业或自己班级下的作业。这样教师不能通过查重结果看到其他教师管理范围内的学生提交。

### 8. 互评和最终成绩

教师可以为作业开启互评，并设置教师评分权重、互评分权重和 peer bonus。系统可以自动分配互评任务，学生完成互评后，最终成绩可以结合教师分数、互评平均分和 peer bonus 计算。

最终成绩可以通过教师端命令计算和查看，也可以导出到课程归档中。这一设计使系统不只支持“提交—批改—反馈”的基本流程，也支持更接近课程真实评价的综合成绩管理。

### 9. 课程归档

教师可以生成课程归档 zip。归档中包含学生提交文件、作业成绩 CSV 和课程总成绩 CSV。归档文件名和归档内部路径经过安全处理，避免路径穿越和解压风险。

认证开启后，归档也按教师权限过滤。教师生成的归档只包含自己可访问作业的提交和成绩，教师之间互不可见。

### 10. 服务端长期运行

项目最终在服务器上将 Module B 配置为 systemd 服务 `haocean-module-b.service`。服务端监听本地 `127.0.0.1:8000`，再由 Caddy 将 HTTPS 域名反向代理到服务端。

这种部署方式保证：

* 当前终端关闭后服务不会停止。
* 机器重启后服务会自动启动。
* 服务崩溃后 systemd 会自动重启。
* 学生和教师可以通过固定 HTTPS 域名访问服务端。

通过 systemd 和 Caddy，项目从本地演示脚本进一步变成可以长期运行的课程服务。

## 五、数据隔离与安全设计

项目后期重点补强了教师数据隔离。最终隔离边界定义为：

> 教师只能访问自己的作业，或自己班级下的作业。

这一边界不是客户端隐藏菜单实现的，而是在服务端入口统一检查。涉及入口包括：

* 作业统计。
* 最终成绩计算和查看。
* 查重报告查看。
* 手动查重。
* AI 审阅报告。
* 互评配置和阶段切换。
* 自动互评任务分配。
* 课程归档创建、列表和下载。
* 单个提交下载和批改。

学生侧的边界包括：

* 学生只能看到公开作业，或自己加入班级下的作业。
* 学生只能下载自己有权限的作业材料。
* 学生只能提交自己加入班级下的班级作业。
* 学生只能查看自己的反馈和成绩历史。
* 学生只能查看和提交分配给自己的互评任务。

真实部署必须开启：

```bash
MODULE_B_AUTH_REQUIRED=true
```

如果不开启认证，服务端会保持本地联调兼容模式，不强制跨用户隔离。因此，正式运行时需要开启认证配置。

文件安全方面，系统也做了多层处理。学生端提交前会过滤缓存、虚拟环境、日志、数据库和历史压缩包；服务端会进行 MD5 校验；教师端解压提交包时会检查路径穿越；课程归档时会再次过滤和扁平化作业文件。这些设计共同降低了误提交、恶意路径和归档污染的风险。

## 六、测试与验证

### 1. 单元测试

项目三个核心模块均有自动化测试。本次最终测试结果如下：

```text
Module A: 36 passed
Module B: 25 tests OK
Module C: 44 passed
```

总计 105 个测试通过。

测试覆盖内容包括：

* 学生端配置、认证、API client、材料下载、归档过滤、提交预览、反馈保存、互评、watcher 防抖和 AI help。
* 服务端认证、班级、作业材料、下载权限、重复提交覆盖、截止时间校验、批改保护、查重、AI 审阅、互评、成绩统计、最终成绩和课程归档。
* 教师端配置、认证、API client、班级与作业接口、材料上传、查重、互评、成绩统计、TUI 安全解压和 review flow。

### 2. 端到端 verify

项目提供：

```bash
make verify
```

验证流程包括：

1. 运行三个模块的测试。
2. 启动临时 Module B 服务。
3. 执行 Module B smoke test。
4. 创建 Module A 集成测试作业。
5. 使用学生端 CLI 提交作业。
6. 检查服务端 pending submission。
7. 输出 Verification completed。

本地验证中使用避开端口占用的方式运行：

```bash
VERIFY_B_PORT=19080 make verify
```

验证结果通过，关键输出包括：

```text
[Module_D] [1/7] Running module tests
[Module_D] [2/7] Starting Module B server
[Module_D] [3/7] Running Module B smoke test
[Module_D] [4/7] Creating assignment for Module A integration
[Module_D] [5/7] Submitting with Module A
[Module_D] [6/7] Checking pending submission
[Module_D] [7/7] Verification completed
```

这说明项目主流程不仅在单元测试层面可用，也能完成从学生端 CLI 到服务端提交记录生成的端到端验证。

### 3. fresh GitHub clone 验证

项目推送 GitHub 后，又从 GitHub 最新 `main` 重新 clone，独立创建虚拟环境并安装依赖。fresh clone 验证确认：

* README 和 `docs/banner.svg` 已存在。
* 最新提交为 `6cc2b9d Tighten teacher data isolation and update README`。
* fresh clone 的 `make test` 通过。
* 双教师隔离专项测试通过。
* 使用可写 HOME 后，fresh clone 的完整 `make verify` 通过。

双教师隔离专项验证覆盖：

* 教师 A 可以访问自己的作业。
* 教师 A 可以访问自己班级下的作业。
* 教师 A 访问教师 B 的统计、查重、最终成绩、互评和归档被拒或不可见。
* 教师 A 导出的归档不包含教师 B 的提交和成绩。

fresh clone 验证说明项目不是依赖当前开发目录的临时状态，而是在重新拉取代码、重新安装依赖后仍能完成主要测试和验收流程。

### 4. 真实环境流程测试

真实环境测试覆盖了以下流程：

* 学生端和教师端通过 GitHub 安装脚本安装。
* 教师建班、发布带 materials 的作业。
* 学生执行 `list`、`materials`、`preview`、`submit`。
* 教师下载提交包、批改作业、查看统计、计算 final scores、创建和下载归档。
* 学生拉取反馈。
* AI 审阅和 hybrid AI 查重。

批量测试中，一次作业完成 15 个学生提交。指定学生二次提交覆盖成功，`submission_id` 保持不变，总提交数仍为 15。过期作业提交被拒绝。AI 审阅返回 DeepSeek 结果，查重输出 suspected pairs。

需要说明的是，批量 15 学生登录测试使用开发验证码覆盖认证、token、角色和 CLI 流程；由于没有 15 个真实可收码邮箱，未覆盖 15 个真实 SMTP 收件箱逐一收码。这不影响作业流、提交流、权限流和 CLI 流程的验证。

### 5. 真实命令输出摘录

以下摘录来自真实环境中的反馈演示作业 `feedback_demo_20260609_062310`，用于展示系统实际返回的数据形态。该作业的真实提交编号为 `59`，教师评分为 `96`。

教师端批改总览和成绩统计输出如下：

```text
Grade Overview: feedback_demo_20260609_062310
Course Weight : 1.0
Submissions   : total=1 pending=0 graded=1 rejected=0
Score Stats   : count=1 avg=96.0 min=96.0 max=96.0 median=96.0
Plagiarism    : top=0.0% submission=59
Final Scores  : calculated=0

Assignment : feedback_demo_20260609_062310
Count=1 Avg=96.0 Min=96.0 Max=96.0 Median=96.0
Student    Effective  Teacher  Peer Avg  Bonus  Final  Weight  Weighted
2026060901 96         96       None      0.0    None   1.0     96.0
```

AI 审阅报告返回了 DeepSeek 结果：

```text
Submission : 59
Assignment : feedback_demo_20260609_062310
Student    : 2026060901
Source     : deepseek
Model      : deepseek-v4-flash

学生清晰描述了 Linux 终端提交作业的流程，符合要求。

Requirement Checks:
- [met] 写出使用的核心命令
- [met] 说明提交前如何检查文件
- [met] 结尾写一句你对 Linux 命令行作业流的感受

Strengths:
- 命令列举完整，流程清晰
- 检查步骤明确
- 感受句具体且有深度

Score rationale: 完全满足所有要求，且表达清晰，因此得分 96。
```

hybrid AI 查重在单提交场景下返回完整检查摘要，并明确没有疑似对：

```text
Assignment : feedback_demo_20260609_062310
Method     : hybrid
Threshold  : 0.75
Submissions: 1
Pairs      : 0
AI Model   : deepseek-v4-flash
AI Reviewed: 0 / limit=12
Suspected  : none
```

学生端拉取到的教师反馈包含评分和评语：

```text
# 作业反馈

## 基本信息

- 提交编号：59
- 学生学号：2026060901
- 作业编号：feedback_demo_20260609_062310
- 当前状态：graded

## 批改结果

- 分数：96

## 教师评语

Excellent work: clear Linux CLI workflow with list, materials, preview, and submit.
```

## 七、部署与交付材料

项目最终整理了较完整的交付材料和安装方式，主要包括：

* `README.md`：项目总览、安装与使用入口。
* `install-student.sh`：学生端 GitHub 安装脚本。
* `install-teacher.sh`：教师端 GitHub 安装脚本。
* `install-all.sh`：学生端与教师端组合安装脚本。
* `uninstall.sh`：本地 CLI 卸载脚本。
* `docs/api_spec.md`：API 契约与接口说明。
* `docs/student_usage_guide.md`：学生端安装与使用指南。
* `docs/teacher_usage_guide.md`：教师端安装与使用指南。
* `docs/local_student_usage_guide.md`：本机学生端测试指南。
* `docs/local_teacher_usage_guide.md`：本机教师端测试指南。
* `docs/domain_auth_smoke.md`：DNS、Caddy/HTTPS、认证 smoke 说明。
* `docs/ppt_outline.md`：PPT 内容提纲。
* `docs/project_tree_for_report.txt`：报告用目录树。
* `docs/report_audit_material.md`：报告事实核查材料。

服务端部署方面，项目已经配置为 systemd 长期服务，并通过 Caddy 提供 HTTPS 域名访问。安装脚本、使用指南、API 文档和部署说明共同组成了项目的交付材料，使系统具备被他人复现、安装和演示的基础。

## 八、项目成果

项目最终完成了一个可以真实运行的 Linux 命令行课程管理系统。主要成果包括：

* 学生端 `haocean-student`。
* 教师端 `haocean-teacher`。
* 本机帮助命令 `haocean ai-help`。
* FastAPI 服务端 Module B。
* 自动化验证脚本 Module D。
* GitHub 安装脚本：`install-student.sh`、`install-teacher.sh`、`install-all.sh`。
* 卸载脚本：`uninstall.sh`。
* README、学生指南、教师指南、API 文档、部署说明、banner 和 PPT 提纲。
* systemd 长期服务部署。
* Caddy/HTTPS 域名访问。
* 105 个自动化测试通过。
* `VERIFY_B_PORT=19080 make verify` 端到端验证通过。
* fresh GitHub clone 验证通过。
* 双教师数据隔离专项验证通过。
* 真实环境流程测试和 15 学生批量提交流程测试完成。

从功能上看，系统已经覆盖课程作业管理的主要闭环：教师发布作业和材料，学生下载材料并提交作业，教师批改并生成反馈，学生拉取反馈，系统提供查重、AI 审阅、互评、成绩统计和课程归档等辅助能力。

从工程上看，项目体现了模块化设计、API 设计、权限控制、文件安全、自动化测试、集成验证和服务部署等软件工程实践。

## 九、遇到的问题与解决方案

### 1. 端口占用

验证过程中发现默认端口可能被旧进程占用。解决方案是支持通过环境变量指定 verify 端口，例如：

```bash
VERIFY_B_PORT=19080 make verify
```

这样可以避开已有服务占用，提高本地验收的稳定性。

### 2. 截止时间漂移

早期 smoke 测试中使用固定过去日期，随着真实日期变化会导致提交失败。解决方案是将测试作业 deadline 改为未来时间，避免时间漂移导致误失败。

### 3. AI 报告缓存升级

AI 报告结构升级后，旧缓存可能不包含新的 requirement checks。解决方案是在报告中加入 schema version，旧 schema 自动刷新，使教师端看到的报告结构保持一致。

### 4. 教师数据隔离补强

初期部分作业级入口只判断“是否是教师”，没有判断“是否有权访问该作业”。后续将统计、查重、最终成绩、互评、归档、下载和批改等入口统一接入权限检查，并增加双教师隔离测试，确保教师之间的数据互不可见。

### 5. fresh verify 的 HOME 写入问题

fresh clone verify 在沙箱环境中第一次失败，因为 Module A 默认写 `/root/.haocean/logs`，而该路径只读。解决方案是将 HOME 指向 `/tmp` 下可写目录后重跑，验证通过。

### 6. 历史运行数据混入 verify 输出

在部分验证过程中，临时服务可能使用当前项目目录下已有的 SQLite 数据库，导致 verify 输出中混入历史运行数据。虽然最终验证结果通过，但后续可以进一步改进为每次 verify 使用独立临时数据库和独立数据目录，使测试环境更加干净。

## 十、改进方向

后续可以从以下方向继续完善：

1. 将 SQLite 升级为 PostgreSQL，提高并发能力、事务管理能力和数据审计能力。
2. 将提交包、材料、反馈和归档迁移到对象存储，减少本地磁盘压力。
3. 将 AI 审阅和 AI 查重改为异步任务队列，避免大作业或外部模型调用阻塞请求。
4. 为 verify 流程增加独立临时数据库和临时文件目录，减少历史数据对测试输出的影响。
5. 增加 GitHub Actions，在每次提交后自动运行测试、构建安装包和发布版本。
6. 增加更细粒度 Rubric，让教师发布作业时定义评分项，AI 和人工批改都按评分项输出。
7. 增加 Web 只读看板，用于课程整体统计和展示，同时保留 Linux CLI 作为核心交互。
8. 增加 Docker Compose 部署方案，降低复用和迁移成本。
9. 准备测试邮件服务或更多真实邮箱，覆盖大规模真实 SMTP 验证码收码。
10. 增加更完善的管理员角色，用于跨课程管理、备份和审计。

## 十一、总结

Haocean Mooc CLI 的核心价值在于把 Linux 学习和课程管理流程结合起来。学生通过 Linux 命令行完成真实作业任务，教师通过 Linux 命令行完成课程管理，服务端负责认证、隔离、存储、AI 审阅、查重、互评、成绩计算和课程归档。

项目从一个“能不能用 Linux 交作业”的想法出发，最终形成了一个包含学生端、教师端、服务端、自动化验证、安装脚本、部署方案和真实运行测试的完整系统。它既体现了 Linux 课程的实践性，也体现了软件工程中的模块化设计、接口设计、权限控制、文件安全、自动化测试和部署运维能力。

最终，Haocean Mooc CLI 不只是一个课程作业提交工具，而是一套可以真实运行、可以继续扩展的 Linux 命令行课程管理平台。
