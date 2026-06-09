![Haocean Mooc CLI](docs/banner.svg)

# 🌊 Haocean Mooc CLI

Haocean Mooc CLI 是给课程作业使用的 Linux 命令行工具。学生用它查看作业、下载资料、提交作业和获取反馈；老师用它创建班级、发布作业、批改、查重、统计成绩和导出归档。

真实使用时，学生和老师不需要登录服务器，只需要安装对应命令：

- 🎓 学生：`haocean-student`
- 🧑‍🏫 老师：`haocean-teacher`
- 💬 本机帮助：`haocean ai-help`

默认服务地址：

- 学生端：`https://student.haoceanlab.cn`
- 教师端：`https://teacher.haoceanlab.cn`

## ✨ 特色功能

- 学生和老师各自使用独立 CLI：学生端负责加入班级、下载资料、预览和提交作业；教师端负责建班、发布、批改、统计、查重和归档。
- 作业支持资料附件、截止时间、重复提交覆盖和反馈拉取，适合课程作业反复迭代。
- 服务端认证开启后强制数据隔离：老师只能访问自己的作业，或自己班级下的作业；学生只能访问自己可见和可提交的作业。
- AI 审阅会结合老师发布的作业说明和材料文本生成报告；没有 DeepSeek key 时也能返回本地结构化反馈。
- 查重支持 token、Jaccard、AI 和 hybrid 模式，历史候选会按老师可访问范围收紧。
- 支持互评、最终成绩计算、成绩统计、学生历史成绩和课程归档导出。
- Module B 可以作为长期服务运行，配合 Caddy/Nginx 对外提供 HTTPS 域名。

## 📖 使用教程

### 🚀 安装

同一台机器同时安装学生端和教师端：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-all.sh | bash
export PATH="$HOME/.local/bin:$PATH"
```

只安装学生端：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-student.sh | bash
export PATH="$HOME/.local/bin:$PATH"
```

只安装教师端：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-teacher.sh | bash
export PATH="$HOME/.local/bin:$PATH"
```

安装后会把使用指南保存到本机：

- 📘 学生指南：`~/.haocean/docs/student_usage_guide.md`
- 📗 教师指南：`~/.haocean-teacher/docs/teacher_usage_guide.md`

也可以直接在终端查看：

```bash
haocean-student guide
haocean-teacher guide
```

如果提示 `command not found`，执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

并建议把这行加入 `~/.bashrc`。

### 🎓 学生怎么用

首次配置并登录：

```bash
haocean-student setup
haocean-student login
```

加入老师给的班级：

```bash
haocean-student join JOIN101
haocean-student classes
```

查看开放作业：

```bash
haocean-student list
```

如果某个作业显示 `materials=yes`，先下载老师发布的说明文件和附件：

```bash
haocean-student materials home_001
```

资料会保存到：

```text
~/.haocean/workspace/home_001/materials/
```

准备并提交作业：

```bash
mkdir -p ~/.haocean/workspace/home_001
nano ~/.haocean/workspace/home_001/answer.md
haocean-student preview home_001
haocean-student submit home_001
```

获取老师反馈：

```bash
haocean-student feedback
```

如果老师开启互评：

```bash
haocean-student peer-review --assignment-id home_001
haocean-student peer-review 21 95 --comment "完成较好，说明清晰"
```

同一台电脑需要保存多个学生身份时：

```bash
haocean-student setup --profile s001
haocean-student setup --profile s002 --student-id 2024002 --name "Student Two" --email student2@example.com
haocean-student profiles
haocean-student login
```

每个身份的登录 token 会分别保存在 `~/.haocean/auth_tokens/`。

### 🧑‍🏫 老师怎么用

首次配置并登录：

```bash
haocean-teacher setup
haocean-teacher login
```

创建班级并获取加入码：

```bash
haocean-teacher class
haocean-teacher classes list
```

选择当前班级：

```bash
haocean-teacher select
```

发布作业：

```bash
haocean-teacher publish
```

直接发布作业并附带说明文件或附件目录：

```bash
haocean-teacher publish home_001 "Homework 1" --materials ./home_001_spec.pdf
haocean-teacher publish home_002 "Homework 2" --materials ./home_002_materials/
```

开启互评：

```bash
haocean-teacher publish home_001 "Homework 1" --peer-review --teacher-weight 0.7
```

查看和批改某个作业：

```bash
haocean-teacher grade home_001
```

批改总览里常用操作：

```text
p / a / l  切换待批改、已批改、全部提交
Enter      批改或更新当前提交分数
d          下载并解压当前提交包
o          预览解压目录中的 .md / .txt
g          查看当前提交的 AI 审阅报告
c          查看当前提交相关的查重结果
s          查看当前学生历史成绩
pr         打开互评阶段并自动分配任务
q          退出
```

查看查重、统计和历史成绩：

```bash
haocean-teacher plagiarism home_001
haocean-teacher plagiarism home_001 --check --method hybrid --threshold 0.75
haocean-teacher stats home_001
haocean-teacher history 2024001
```

互评结束后计算最终成绩并导出归档：

```bash
haocean-teacher final-scores home_001 --calculate
haocean-teacher archive create --name 2026_spring.zip --note "2026 spring final archive"
haocean-teacher archive download 2026_spring.zip
```

教师端也支持多身份，本地 token 默认保存在 `~/.haocean-teacher/auth_tokens/`。

### 💬 本机 AI 帮助

`haocean ai-help` 是用户本机的命令帮助助手。它不会调用 Haocean 服务端，也不会读取服务器上的测试 AI 配置。

没有配置本机 DeepSeek key 时，它会显示内置帮助：

```bash
haocean ai-help "怎么提交作业？"
```

如果你想让它调用你自己的 DeepSeek key，可以放到当前 shell：

```bash
export HAOCEAN_DEEPSEEK_API_KEY=your-deepseek-key
haocean ai-help "怎么提交作业？"
```

也可以写入本机文件：

```bash
mkdir -p ~/.haocean
nano ~/.haocean/ai.env
```

示例：

```dotenv
HAOCEAN_DEEPSEEK_API_KEY=your-deepseek-key
```

`ai-help` 只读取这些本机位置：

- 当前 shell 环境变量：`HAOCEAN_DEEPSEEK_API_KEY` 或 `DEEPSEEK_API_KEY`
- `~/.haocean/ai.env`
- `~/.haocean/.env`

### 🔍 老师的 AI 查重和 AI 审阅

老师端的 AI 查重和 AI 审阅由 `haocean-teacher` 发起。真实使用推荐老师在自己机器上配置 key，教师端会通过 HTTPS 请求头传给服务端本次调用使用。

```bash
mkdir -p ~/.haocean-teacher
nano ~/.haocean-teacher/.env
```

示例：

```dotenv
MODULE_C_DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_MODEL=deepseek-v4-flash
```

学校也可以选择在服务器上统一配置 AI key。无论哪种方式，都不要把真实 key 提交到 GitHub 或发到公开聊天里。

### 🧹 卸载

卸载命令会删除 CLI 程序和虚拟环境，但默认保留本地配置、token、作业工作区、下载文件和指南：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/uninstall.sh | bash
```

连本地数据一起删除：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/uninstall.sh | bash -s -- --with-data
```

### 🛟 常见问题

#### 🌐 安装时 raw.githubusercontent.com 断开

这是网络或代理问题，常见报错包括 `SSL_ERROR_SYSCALL`、`Failed to connect`。可以重试，或先下载脚本再执行：

```bash
curl --retry 5 --retry-delay 2 -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-teacher.sh -o /tmp/install-teacher.sh
bash /tmp/install-teacher.sh
```

#### 📭 看不到作业

先确认：

- 已执行 `haocean-student login`
- 已执行 `haocean-student join <班级加入码>`
- 老师已经发布作业
- 老师发布作业时绑定的是你加入的班级

#### 📦 提交失败

先运行：

```bash
haocean-student preview home_001
```

确认目录名和作业编号一致，且目录里确实有要提交的文件。

## 🖥️ 服务端长期运行

要让学生和老师持续使用，Module B 必须一直运行。学生端和老师端只是安装在各自电脑上的 CLI；真正接收登录、发布作业、提交、批改和下载的是服务器上的 Module B 服务。

如果你是在终端里直接运行：

```bash
cd module_b_server
MODULE_B_AUTH_REQUIRED=true .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

那么这个终端关闭后，`uvicorn` 进程通常也会停止，学生和老师就无法继续连接服务端。已经安装好的 `haocean-student` / `haocean-teacher` 命令还在，但会因为服务端不可用而无法登录、提交或批改。

正式使用建议把 Module B 作为长期服务运行，例如：

- 用 `systemd` 管理 `uvicorn` 进程，机器重启后自动拉起。
- 或者临时测试时用 `tmux` / `screen` / `nohup` 保持进程不随当前终端退出。
- 公网部署时用 Caddy/Nginx 把 HTTPS 域名反代到 Module B。

域名和认证 smoke 参考：[`docs/domain_auth_smoke.md`](docs/domain_auth_smoke.md)。

## 🔐 数据隔离边界

开启 `MODULE_B_AUTH_REQUIRED=true` 后，隔离由服务端强制执行，不依赖客户端界面隐藏。

- 学生只能看到全局开放作业，或自己已加入班级的作业。
- 学生只能提交自己已加入班级下的班级作业。
- 老师只能管理自己创建的班级。
- 老师只能发布到自己的班级。
- 老师只能查看、下载、批改、统计、查重、AI 审阅、计算最终成绩和归档自己创建的作业，或自己班级下的作业。
- 老师生成课程归档时，归档包只包含自己可访问作业的提交文件和成绩 CSV。

如果没有开启认证，服务端会保持本地联调兼容模式，不应用这些跨用户隔离规则。真实部署必须开启认证。
