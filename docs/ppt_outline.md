# Haocean Mooc CLI PPT 内容大纲

## Page 1. 封面

标题：Haocean Mooc CLI：面向 Linux 课程的命令行作业管理系统

内容要点：

- 项目定位：用 Linux 命令行完成作业查看、资料下载、提交、批改、查重、AI 审阅和成绩归档。
- 小组/成员/课程信息。
- 可以放 README 中的 `docs/banner.svg` 作为视觉主图。

视觉建议：

- 使用项目 banner。
- 下面放三个关键词：Linux Practice / Course Workflow / AI Review。

## Page 2. Background：为什么做这个项目

内容要点：

- 这门课主要聚焦 Linux，希望同学们不只是“学命令”，而是在真实任务中使用 Linux。
- 我们最初的问题是：既然在学习 Linux，能不能连“提交作业”这个过程也在 Linux 里完成？
- 传统网页式提交作业容易让 Linux 操作变成孤立练习，而命令行提交流程可以把课程实践、文件组织、压缩归档、网络请求和日志反馈串起来。
- 因此我们设计了 Haocean Mooc：从 Linux 命令行提交作业出发，扩展为学生提交、老师管理、AI 审阅、查重、互评、成绩统计和课程归档的一体化课程管理软件。

可用表达：

> 不感受 Linux，就拿不到作业分。我们希望把 Linux 从课堂内容变成课程工作流本身。

## Page 3. 项目目标

内容要点：

- 学生侧：在 Linux 终端中完成登录、加入班级、查看作业、下载资料、预览、提交和拉取反馈。
- 教师侧：在 Linux 终端中完成建班、发布作业、批改、查重、统计、互评、最终成绩计算和归档导出。
- 服务端：提供认证、权限隔离、提交存储、成绩管理、AI 审阅和查重 API。
- 工程侧：支持 GitHub 安装脚本、自动化测试、端到端 smoke 验证和长期服务部署。

视觉建议：

- 用“学生 / 老师 / 服务端 / 运维验证”四象限展示目标。

## Page 4. 整体架构

内容要点：

- Module A：学生端 CLI，命令为 `haocean-student`，负责学生工作流。
- Module B：FastAPI 服务端，负责核心业务、数据库、认证、文件存储、AI 审阅和查重。
- Module C：教师端 CLI/TUI，命令为 `haocean-teacher`，负责老师工作流。
- Module D：运维和验证脚本，负责自动化 verify、smoke test 和集成检查。
- Caddy/Nginx：将 HTTPS 域名反向代理到 Module B。
- systemd：让 Module B 作为长期服务运行，终端关闭后服务不停止。

架构图建议：

```text
Student Linux CLI           Teacher Linux CLI
haocean-student             haocean-teacher
       |                         |
       | HTTPS                   | HTTPS
       v                         v
 student.haoceanlab.cn     teacher.haoceanlab.cn
              \             /
               \           /
             Caddy / Nginx
                   |
                   v
        Module B FastAPI Service
     Auth / Assignment / Submit / Grade
     AI Review / Plagiarism / Archive
                   |
                   v
        SQLite + file storage
```

## Page 5. 技术选型

内容要点：

- Python：快速实现 CLI、服务端和测试脚本。
- FastAPI：构建 Module B REST API。
- SQLite：轻量级数据存储，便于课程项目部署和验收。
- requests / argparse / rich / textual：实现学生端、教师端命令行和交互式界面。
- tar/zip + MD5：完成作业打包、完整性校验和归档。
- DeepSeek API：实现 AI 审阅和 AI 辅助查重；没有 key 时提供本地结构化 fallback。
- systemd + Caddy：实现服务常驻和 HTTPS 访问。

## Page 6. 特色功能总览

内容要点：

- Linux 原生命令行作业流。
- 学生端和教师端双 CLI。
- 邮箱验证码登录与多身份 profile。
- 班级加入码、作业材料、截止时间、重复提交覆盖。
- 老师端批改、反馈、统计和历史成绩。
- AI 审阅：结合老师发布的作业说明和材料文本。
- 查重：token / hybrid / AI 多模式。
- 互评和最终成绩计算。
- 课程归档导出。
- 服务端强制数据隔离。
- 自动化测试与 fresh GitHub 验证。

视觉建议：

- 用 2 行 5 列功能卡片展示。

## Page 7. 特色功能 1：Linux 原生命令行作业流

内容要点：

- 学生不用打开网页，在 Linux 终端中完成作业全过程。
- 典型命令：
  - `haocean-student setup`
  - `haocean-student login`
  - `haocean-student list`
  - `haocean-student materials home_001`
  - `haocean-student preview home_001`
  - `haocean-student submit home_001`
  - `haocean-student feedback`
- 设计想法：让文件组织、路径、压缩包、日志、HTTP 请求这些 Linux 实践自然融入课程作业。

成果展示建议：

- 放学生端 `list / preview / submit / feedback` 的终端截图。

## Page 8. 特色功能 2：教师端批改和课程管理

内容要点：

- 老师端支持建班、选择班级、发布作业、附带材料、查看提交和批改。
- 典型命令：
  - `haocean-teacher class`
  - `haocean-teacher publish`
  - `haocean-teacher grade home_001`
  - `haocean-teacher stats home_001`
  - `haocean-teacher archive create`
- 批改界面支持下载提交包、预览文本、写分数和评语、查看 AI 审阅和查重结果。

成果展示建议：

- 放老师端批改总览截图。
- 放一份生成的 Markdown 反馈截图。

## Page 9. 特色功能 3：认证、班级和数据隔离

内容要点：

- 学生和老师通过邮箱验证码登录。
- 支持本机多身份 profile，适合同一电脑测试多个学生或多个老师账号。
- 学生只能看到公开作业或自己加入班级的作业。
- 老师只能访问自己的作业，或自己班级下的作业。
- 隔离由服务端强制执行，不依赖客户端隐藏按钮。
- 涉及隔离的入口包括：提交下载、批改、统计、查重、AI 报告、最终成绩、互评配置和课程归档。

成果展示建议：

- 放“双老师隔离专项测试通过”的终端截图。
- 可画一个边界图：Teacher A 与 Teacher B 的作业空间相互隔离。

## Page 10. 特色功能 4：作业材料、截止时间和重复提交覆盖

内容要点：

- 老师发布作业时可以附带 PDF、说明文件或材料目录。
- 学生端可以下载材料到本地 workspace。
- 提交时会进行截止时间检查，过期作业拒绝提交。
- 同一学生同一作业重复提交时覆盖旧提交，并保留同一个 `submission_id`，避免成绩和反馈关系混乱。
- 提交包通过 MD5 校验，减少文件传输错误。

成果展示建议：

- 放材料下载目录截图。
- 放“重复提交后 submission_id 不变”的验证截图。
- 放“deadline has passed”的错误截图。

## Page 11. 特色功能 5：AI 审阅

内容要点：

- AI 审阅读取学生提交内容，也读取老师发布的作业说明和 materials 文本。
- 生成结构化报告：summary、requirement checks、strengths、concerns、suggestions、score rationale。
- 支持 DeepSeek API；没有 key 时使用本地 fallback，保证功能可用。
- 报告带 schema version，旧缓存 schema 过期会自动刷新。
- 老师可以用自己的 key 通过 HTTPS 请求头临时传给服务端，不需要把 key 写进 GitHub。

成果展示建议：

- 放 AI 审阅报告截图。
- 高亮 requirement checks，体现“结合题目要求审阅”。

## Page 12. 特色功能 6：查重与历史候选收紧

内容要点：

- 支持 token 相似度、AI 查重和 hybrid 模式。
- 查重范围包括当前作业和近三年历史提交。
- 在认证开启后，历史候选只来自当前老师可访问的作业，避免老师通过查重看到其他老师的数据。
- 结果可以在老师端查看，也会在提交时自动生成基础查重报告。

成果展示建议：

- 放查重报告输出。
- 展示 suspected pairs、similarity、scope 等字段。

## Page 13. 特色功能 7：互评、最终成绩和归档

内容要点：

- 老师可以开启互评，并设置老师评分和互评分权重。
- 系统自动分配互评任务，学生提交互评分和评语。
- 最终成绩结合老师评分、互评平均分和 peer bonus。
- 老师可以导出课程归档 zip，包含提交文件、作业成绩 CSV 和课程总成绩 CSV。
- 归档也按老师权限过滤，老师只能导出自己可访问的数据。

成果展示建议：

- 放 final scores 输出。
- 放 archive zip 内部目录结构截图。

## Page 14. 真实环境测试 1：一老师两学生

内容要点：

- 测试目标：验证真实登录、建班、加入班级、发布作业、提交、批改、反馈闭环。
- 流程：
  1. 老师登录并创建班级。
  2. 两名学生登录并加入班级。
  3. 老师发布作业和材料。
  4. 两名学生分别下载资料、预览并提交。
  5. 老师批改并生成反馈。
  6. 学生拉取反馈。
- 展示内容：
  - 老师端建班/发布/批改输出。
  - 学生端提交/反馈输出。

## Page 15. 真实环境测试 2：一次作业 15 学生

内容要点：

- 测试目标：验证批量学生提交、重复提交覆盖、过期作业拒绝、老师下载和统计。
- 测试结果：
  - 15 个学生提交成功。
  - 指定学生二次提交覆盖成功，`submission_id` 保持不变，总提交数仍为 15。
  - 过期作业提交被拒绝。
  - 老师端下载、批改、统计、最终成绩和归档流程通过。
  - AI 审阅和 hybrid AI 查重通过。
- 说明：批量学生登录使用开发验证码覆盖认证/token/角色/CLI 流程；真实 SMTP 收码受可用邮箱数量限制，未覆盖 15 个真实邮箱逐一收码。

成果展示建议：

- 放 15 条提交记录或统计截图。
- 放 archive 下载成功截图。
- 放 AI 查重 suspected pairs 截图。

## Page 16. 自动化验证与工程质量

内容要点：

- 单元测试：
  - Module A：36 个测试。
  - Module B：25 个测试。
  - Module C：44 个测试。
- `make verify` 覆盖：
  - 模块测试。
  - Module B smoke。
  - Module A 到 Module B 的提交集成。
  - pending submission 检查。
- fresh GitHub 验证：
  - 从 GitHub 最新 main 重新 clone。
  - 独立安装依赖。
  - 运行测试和双老师隔离专项验证。
  - 完整 verify 通过。

成果展示建议：

- 放 `make test` 和 `make verify` 的通过截图。

## Page 17. 部署成果

内容要点：

- Module B 已配置为 systemd 长期服务。
- 终端关闭后服务仍继续运行，机器重启后自动启动。
- Caddy 将 HTTPS 域名代理到本地 Module B。
- 健康检查返回：
  - `auth_required=true`
  - `smtp_configured=true`
  - `deepseek_configured=true`
- 学生端域名：`https://student.haoceanlab.cn`
- 教师端域名：`https://teacher.haoceanlab.cn`

成果展示建议：

- 放 `systemctl status haocean-module-b.service` 截图。
- 放 `/health` 返回截图。

## Page 18. 改进想法

内容要点：

- 数据库升级：从 SQLite 切换到 PostgreSQL，支持更高并发和更完整的权限审计。
- 文件存储升级：将提交包和材料迁移到对象存储，减少服务器磁盘压力。
- AI 任务异步化：AI 审阅和查重放入后台队列，避免大作业阻塞请求。
- Web 管理后台：保留 Linux CLI 核心特色，同时提供只读看板用于课程整体观察。
- 更细粒度评分 Rubric：老师发布作业时定义评分项，AI 审阅和人工批改都按 rubric 输出。
- 更完整的邮件验证测试：准备更多真实邮箱或测试邮件服务，覆盖大规模真实 SMTP 收码。
- Docker/Compose 部署：降低部署门槛，便于其他课程复用。
- CI/CD：GitHub Actions 自动跑测试、构建安装包并发布版本。

## Page 19. 总结

内容要点：

- Haocean Mooc 把 Linux 学习从“课堂练习”延伸到“课程作业工作流”。
- 项目覆盖学生、老师和服务端完整闭环。
- 功能上实现了提交、批改、AI 审阅、查重、互评、统计、归档和服务端隔离。
- 工程上实现了安装脚本、自动化测试、fresh clone 验证和长期服务部署。
- 最终成果不仅是一个课程项目，也是一套可以真实运行的 Linux 命令行课程管理系统。

## Page 20. End

内容要点：

- Thank you.
- 可以放 GitHub 地址、项目二维码或安装命令。
