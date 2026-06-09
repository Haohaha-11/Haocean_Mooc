# Haocean Mooc CLI 实验报告

## 摘要

Haocean Mooc CLI 是一个面向 Linux 课程场景的命令行课程作业管理系统。项目最初来自一个朴素想法：既然课程重点是 Linux，那么作业提交、资料下载、反馈获取和老师批改这些真实课程流程，也可以放到 Linux 命令行中完成。围绕这一目标，项目逐步扩展为由学生端 CLI、教师端 CLI/TUI、FastAPI 服务端和自动化验证脚本组成的综合系统，覆盖班级管理、作业发布、材料下载、作业提交、教师批改、反馈生成、AI 审阅、查重、互评、成绩统计、课程归档和服务端数据隔离。

本项目强调“在真实任务中使用 Linux”。学生不是单独练习几个命令，而是在完成作业的过程中持续接触路径管理、文件组织、压缩归档、命令行参数、网络请求、日志和反馈文件。老师也可以在 Linux 终端中完成课程管理操作。项目最终已部署为长期运行的服务，并通过本地测试、端到端 smoke、fresh GitHub clone 验证和真实环境流程测试。

## 一、项目背景

Linux 课程的学习目标不应只停留在记忆命令或完成孤立实验。真正有价值的学习体验来自于把 Linux 放进实际工作流中使用。传统课程作业平台通常以网页为中心，学生提交作业时只需要点击按钮上传文件，Linux 只出现在课堂练习中，与真实课程流程脱节。

因此，我们提出了 Haocean Mooc 的设计想法：让作业提交这个高频课程场景发生在 Linux 终端中。学生需要在本地 workspace 中整理作业，使用命令查看任务、下载资料、预览提交包、提交作业并拉取反馈。老师也在终端中完成建班、发布、批改、查重和归档。这样，Linux 不再只是课程内容，而成为课程运行方式本身。

项目从“Linux 提交作业”这一最小想法出发，进一步扩展为一个完整的课程管理软件，支持 AI 审阅、查重、互评和数据隔离等功能。

## 二、项目目标

本项目的核心目标包括：

- 为学生提供一个 Linux 命令行作业客户端，完成登录、加入班级、查看作业、下载资料、预览、提交和获取反馈。
- 为老师提供一个 Linux 命令行管理客户端，完成建班、发布作业、查看提交、批改、统计、查重、互评配置、最终成绩计算和归档导出。
- 提供一个稳定的服务端，统一处理认证、权限、作业、提交、文件、成绩、AI 审阅和查重。
- 建立服务端强制的数据隔离机制，确保老师只能访问自己的作业，或自己班级下的作业。
- 提供自动化测试、端到端验证和部署方案，使项目可以真实运行，而不是只停留在演示代码。

## 三、总体架构

项目采用模块化设计，主要分为四个模块。

### 1. Module A：学生端 CLI

Module A 提供 `haocean-student` 命令，是学生使用系统的入口。它负责读取本地配置、管理登录 token、调用服务端 API、组织本地 workspace、生成提交包、计算 MD5、提交作业和保存反馈。

典型命令包括：

```bash
haocean-student setup
haocean-student login
haocean-student join JOIN101
haocean-student list
haocean-student materials home_001
haocean-student preview home_001
haocean-student submit home_001
haocean-student feedback
```

### 2. Module B：服务端 API

Module B 是系统核心，基于 FastAPI 实现。它提供认证、班级、作业、材料、提交、批改、反馈、AI 审阅、查重、互评、成绩统计和归档相关 API。服务端使用 SQLite 保存结构化数据，使用本地文件系统保存提交包、材料、反馈和归档文件。

Module B 同时负责关键的安全边界，例如：

- 学生只能访问自己可见的作业。
- 学生只能提交自己已加入班级下的班级作业。
- 老师只能管理自己的班级。
- 老师只能访问自己的作业，或自己班级下的作业。
- 查重历史候选和课程归档也必须按老师可访问范围过滤。

### 3. Module C：教师端 CLI/TUI

Module C 提供 `haocean-teacher` 命令，是老师使用系统的入口。它负责老师登录、班级管理、作业发布、提交列表、交互式批改、AI 报告查看、查重结果查看、成绩统计和课程归档。

典型命令包括：

```bash
haocean-teacher setup
haocean-teacher login
haocean-teacher class
haocean-teacher publish
haocean-teacher grade home_001
haocean-teacher plagiarism home_001
haocean-teacher stats home_001
haocean-teacher final-scores home_001 --calculate
haocean-teacher archive create
```

### 4. Module D：运维和验证

Module D 提供自动化验证脚本，主要用于本地和集成测试。`make verify` 会依次执行模块测试、启动临时 Module B 服务、运行服务端 smoke test、通过学生端 CLI 提交作业，并检查服务端 pending submission。

这一模块保证项目不是只在单个函数层面可用，而是完整 CLI 到服务端链路可用。

## 四、关键功能设计与实现

### 1. Linux 原生命令行作业流

学生端把作业流程放到 Linux 命令行中完成。学生在本地 workspace 中准备作业文件，通过 `preview` 预览将要提交的内容，再通过 `submit` 打包上传。这个过程让学生自然接触目录结构、文件路径、归档、MD5 校验和命令行交互。

设计重点是让命令足够接近真实使用习惯：

- `list` 查看作业。
- `materials` 下载老师发布的资料。
- `preview` 检查本地目录。
- `submit` 提交当前作业。
- `feedback` 拉取老师反馈。

### 2. 班级、作业材料和截止时间

老师可以创建班级并生成加入码，学生通过加入码加入班级。老师发布作业时可以绑定班级，也可以附带材料文件或材料目录。学生端看到 `materials=yes` 后，可以下载材料到本地 workspace。

作业支持截止时间。服务端在接收提交时进行 deadline 校验，过期作业会拒绝提交。这保证规则由服务端执行，而不是依赖客户端自觉。

### 3. 重复提交覆盖

同一学生对同一作业重复提交时，系统采用覆盖旧提交的策略，并保留同一个 `submission_id`。这样可以避免多次提交导致批改入口、反馈入口和成绩统计混乱。覆盖时会清空旧分数、旧评语、旧反馈路径和旧 AI 报告缓存，使老师看到的是最新一次提交。

### 4. 教师端批改和反馈

老师端可以查看待批改、已批改和全部提交。批改时老师可以下载并解压提交包，预览其中的文本文件，填写分数和评语。服务端会生成 Markdown 格式反馈，学生端可以通过 `feedback` 拉取。

反馈文件包含提交编号、学生学号、作业编号、批改教师、批改时间、分数和评语，便于学生保存和复查。

### 5. AI 审阅

AI 审阅是项目的特色功能之一。系统不仅读取学生提交内容，还会读取老师发布的作业描述和 materials 文本，使 AI 报告更贴合作业要求。

AI 审阅报告采用结构化格式，包含：

- summary
- requirement checks
- strengths
- concerns
- suggestions
- score rationale
- requirements excerpt

如果服务端或老师端提供 DeepSeek key，系统会调用 DeepSeek API；如果没有 key，则返回本地结构化 fallback 报告，保证老师端功能不会完全不可用。报告带有 schema version，旧格式缓存会自动刷新。

### 6. 查重

查重支持 token、AI 和 hybrid 模式。基础 token 查重会提取文本内容并计算相似度，AI 和 hybrid 模式用于进一步判断候选对。

查重范围包括当前作业和近三年历史提交。为了避免数据泄露，认证开启后，历史候选只来自当前老师可访问的作业，也就是老师自己的作业或自己班级下的作业。这样老师不能通过查重结果看到其他老师的学生提交。

### 7. 互评和最终成绩

老师可以为作业开启互评，并设置老师评分权重和互评分权重。系统可以自动分配互评任务，学生完成互评后，最终成绩可以结合老师分数、互评平均分和 peer bonus 计算。

最终成绩可以通过教师端命令计算和查看，也可以导出到课程归档中。

### 8. 课程归档

老师可以生成课程归档 zip。归档中包含学生提交文件、作业成绩 CSV 和课程总成绩 CSV。归档文件名经过安全处理，避免路径穿越和解压风险。

认证开启后，归档也按老师权限过滤。老师生成的归档只包含自己可访问作业的提交和成绩，老师之间互不可见。

### 9. 服务端长期运行

项目最终在服务器上将 Module B 配置为 systemd 服务 `haocean-module-b.service`。服务端监听本地 `127.0.0.1:8000`，再由 Caddy 将 HTTPS 域名反向代理到服务端。

这种部署方式保证：

- 当前终端关闭后服务不会停止。
- 机器重启后服务会自动启动。
- 服务崩溃后 systemd 会自动重启。
- 学生和老师通过固定 HTTPS 域名访问。

## 五、数据隔离与安全设计

项目后期重点补强了教师数据隔离。最终隔离边界定义为：

> 老师只能访问自己的作业，或自己班级下的作业。

这一边界不是客户端隐藏菜单实现的，而是在服务端入口统一检查。涉及入口包括：

- 作业统计。
- 最终成绩计算和查看。
- 查重报告查看。
- 手动查重。
- AI 审阅报告。
- 互评配置和阶段切换。
- 自动互评任务分配。
- 课程归档创建、列表和下载。
- 单个提交下载和批改。

学生侧的边界包括：

- 学生只能看到公开作业，或自己加入班级的作业。
- 学生只能提交自己加入班级下的班级作业。
- 学生只能查看自己的反馈和成绩历史。

真实部署必须开启：

```bash
MODULE_B_AUTH_REQUIRED=true
```

如果不开启认证，服务端会保持本地联调兼容模式，不强制跨用户隔离。

## 六、测试与验证

### 1. 单元测试

项目三个核心模块均有自动化测试。

最终测试结果：

```text
Module A: 36 passed
Module B: 25 tests OK
Module C: 44 passed
```

测试覆盖内容包括：

- 学生端配置、认证、归档、反馈、AI help 和 API client。
- 服务端认证、班级、下载、批改保护、查重、统计、AI 审阅和课程归档。
- 教师端配置、认证、API client、数据库、反馈、TUI 和 review flow。

### 2. 端到端 verify

项目提供：

```bash
make verify
```

验证流程包括：

1. 跑三个模块的测试。
2. 启动临时 Module B 服务。
3. 执行 Module B smoke test。
4. 创建 Module A 集成测试作业。
5. 用学生端 CLI 提交作业。
6. 检查服务端 pending submission。
7. 输出 Verification completed。

本地验证使用避开占用端口的方式运行，例如：

```bash
VERIFY_B_PORT=19080 make verify
```

### 3. fresh GitHub 验证

项目推送 GitHub 后，又从 GitHub 最新 `main` 重新 clone，独立创建虚拟环境并安装依赖。fresh clone 验证确认：

- README 和 `docs/banner.svg` 已存在。
- 最新提交为 `6cc2b9d Tighten teacher data isolation and update README`。
- fresh clone 的 `make test` 通过。
- 双老师隔离专项测试通过。
- 使用可写 HOME 后，fresh clone 的完整 `make verify` 通过。

双老师隔离专项验证覆盖：

- 老师 A 可以访问自己的作业。
- 老师 A 可以访问自己班级下的作业。
- 老师 A 访问老师 B 的统计、查重、最终成绩、互评和归档被拒或不可见。
- 老师 A 导出的归档不包含老师 B 的提交和成绩。

### 4. 真实环境流程测试

真实环境测试覆盖了以下流程：

- 学生端和老师端通过 GitHub 安装脚本安装。
- 老师建班、发布带 materials 的作业。
- 学生 list、materials、preview、submit。
- 老师下载、批改、统计、final scores、归档创建和下载。
- 学生拉取反馈。
- AI 审阅和 hybrid AI 查重。

批量测试中，一次作业完成 15 个学生提交。指定学生二次提交覆盖成功，`submission_id` 保持不变，总提交数仍为 15。过期作业提交被拒绝。AI 审阅返回 DeepSeek 结果，查重输出 suspected pairs。

需要说明的是，批量 15 学生登录测试使用开发验证码覆盖认证、token、角色和 CLI 流程；由于没有 15 个真实可收码邮箱，未覆盖 15 个真实 SMTP 收件箱逐一收码。

## 七、项目成果

项目最终完成了一个可以真实运行的 Linux 命令行课程管理系统。

主要成果包括：

- 学生端 `haocean-student`。
- 教师端 `haocean-teacher`。
- 本机帮助命令 `haocean ai-help`。
- FastAPI 服务端 Module B。
- GitHub 安装脚本：`install-student.sh`、`install-teacher.sh`、`install-all.sh`。
- 卸载脚本：`uninstall.sh`。
- 自动化测试和 verify 脚本。
- README、使用指南、API 文档、banner 和部署说明。
- systemd 长期服务部署。
- HTTPS 域名访问。

项目不只是实现了功能，还完成了测试、部署和提交材料整理。

## 八、遇到的问题与解决方案

### 1. 端口占用

验证过程中发现默认端口可能被旧进程占用。解决方案是支持通过环境变量指定 verify 端口，例如：

```bash
VERIFY_B_PORT=19080 make verify
```

### 2. 截止时间漂移

早期 smoke 测试中使用固定过去日期，随着真实日期变化会导致提交失败。解决方案是将测试作业 deadline 改为未来时间，避免时间漂移导致误失败。

### 3. AI 报告缓存升级

AI 报告结构升级后，旧缓存可能不包含新的 requirement checks。解决方案是在报告中加入 schema version，旧 schema 自动刷新。

### 4. 老师数据隔离补强

初期部分作业级入口只判断“是否是老师”，没有判断“是否有权访问该作业”。后续将统计、查重、最终成绩、互评、归档等入口统一接入权限检查，并增加测试。

### 5. fresh verify 的 HOME 写入问题

fresh clone verify 在沙箱环境中第一次失败，因为 Module A 默认写 `/root/.haocean/logs`，而该路径只读。解决方案是将 HOME 指向 `/tmp` 下可写目录后重跑，验证通过。

## 九、改进方向

后续可以从以下方向继续完善：

- 将 SQLite 升级为 PostgreSQL，提高并发能力和数据审计能力。
- 将提交包、材料和归档迁移到对象存储，减少本地磁盘压力。
- 将 AI 审阅和 AI 查重改为异步任务队列，避免大作业阻塞请求。
- 增加 Web 只读看板，用于课程整体统计和展示，同时保留 Linux CLI 作为核心交互。
- 增加更细粒度 Rubric，让老师发布作业时定义评分项，AI 和人工批改都按评分项输出。
- 增加 Docker Compose 部署方案，降低复用和迁移成本。
- 增加 GitHub Actions，自动运行测试、构建安装包和发布版本。
- 准备测试邮件服务或更多真实邮箱，覆盖大规模真实 SMTP 验证码收码。
- 增加更完善的管理员角色，用于跨课程管理、备份和审计。

## 十、总结

Haocean Mooc CLI 的核心价值在于把 Linux 学习和课程管理流程结合起来。学生通过 Linux 命令行完成真实作业任务，老师通过 Linux 命令行完成课程管理，服务端负责认证、隔离、存储、AI 审阅和查重。

项目从一个“能不能用 Linux 交作业”的想法出发，最终形成了一个包含学生端、教师端、服务端、运维验证和真实部署的完整系统。它既体现了 Linux 课程的实践性，也体现了软件工程中的模块化设计、接口设计、权限控制、自动化测试和部署运维能力。

最终，Haocean Mooc 不只是一个课程作业提交工具，而是一套可以真实运行、可以继续扩展的 Linux 命令行课程管理平台。
