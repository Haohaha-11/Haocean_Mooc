# Haocean Mooc CLI

Haocean Mooc CLI 是一个面向 Linux 终端的课程作业平台，包含学生端、教师端和 FastAPI 服务端。真实使用时，学生和老师不需要登录服务器，只需要安装命令行客户端。

- 学生端命令：`haocean-student`
- 教师端命令：`haocean-teacher`
- AI 使用小助手：`haocean ai-help`
- 默认学生入口：`https://student.haoceanlab.cn`
- 默认教师入口：`https://teacher.haoceanlab.cn`

## 一分钟安装

同一个 Linux 用户如果需要同时使用学生端和教师端：

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-all.sh | bash
export PATH="$HOME/.local/bin:$PATH"
haocean-student --help
haocean-teacher --help
haocean ai-help --local "怎么提交作业？"
```

学生端：

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-student.sh | bash
haocean-student setup
haocean-student login
```

教师端：

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-teacher.sh | bash
haocean-teacher setup
haocean-teacher login
```

如果命令找不到，先执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

清理旧安装后重装：

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/uninstall.sh | bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-all.sh | bash
```

默认卸载会保留 `~/.haocean/` 和 `~/.haocean-teacher/` 中的配置、token、作业工作区和下载文件。如果需要连本地数据一起删除：

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/uninstall.sh | bash -s -- --with-data
```

详细使用文档：

- 学生：`docs/student_usage_guide.md`
- 老师：`docs/teacher_usage_guide.md`
- 本地联调学生：`docs/local_student_usage_guide.md`
- 本地联调老师：`docs/local_teacher_usage_guide.md`

## 学生常用流程

1. 配置身份并登录：

```bash
haocean-student setup
haocean-student login
```

2. 加入班级：

```bash
haocean-student join JOIN101
haocean-student classes
```

3. 查看作业：

```bash
haocean-student list
```

4. 准备作业目录。作业编号是 `home_001` 时：

```bash
mkdir -p ~/.haocean/workspace/home_001
nano ~/.haocean/workspace/home_001/README.md
```

5. 预览并提交：

```bash
haocean-student preview home_001
haocean-student submit home_001
```

6. 拉取老师反馈：

```bash
haocean-student feedback
```

7. 如果老师开启互评，查看并提交互评：

```bash
haocean-student peer-review --assignment-id home_001
haocean-student peer-review 21 95 --comment "完成较好，说明清晰"
```

学生端支持多 profile。同一台机器模拟多个学生时：

```bash
haocean-student setup --profile s001
haocean-student setup --profile s002 --student-id 2024002 --name "Student Two" --email student2@example.com
haocean-student profiles
haocean-student login
```

每个 profile 使用独立 token，默认保存在 `~/.haocean/auth_tokens/`。

## 老师常用流程

1. 配置身份并登录：

```bash
haocean-teacher setup
haocean-teacher login
```

2. 创建班级并获取加入码：

```bash
haocean-teacher class
haocean-teacher classes list
```

3. 选择当前班级：

```bash
haocean-teacher select
```

4. 发布作业：

```bash
haocean-teacher publish
```

也可以直接发布并开启互评：

```bash
haocean-teacher publish home_001 "Homework 1" --peer-review --teacher-weight 0.7
```

5. 打开当前作业批改总览：

```bash
haocean-teacher grade home_001
```

总览菜单中可以查看待批改、已批改、查重、统计、最终成绩，并进入 TUI。直接运行 `haocean-teacher grade` 会提示输入作业编号，避免误看全局历史数据。

教师端 TUI 常用键：

```text
p / a / l  切换待批改、已批改、全部提交
j / k      上下移动
Enter      批改或更新当前提交分数
d          下载并解压当前提交包
o          优先预览解压目录中的 .md / .txt，没有可读文档时打开本地目录
g          查看当前提交的 AI 自动审阅报告
c          查看当前提交相关的 hybrid AI 查重结果
s          查看当前学生历史成绩
r          刷新
q          退出
```

6. 学生都提交后，打开互评阶段并自动分配任务：

```bash
haocean-teacher peer-review home_001
```

也可以在 `haocean-teacher grade home_001` 总览菜单输入 `pr`。

7. 查看查重和成绩统计：

```bash
haocean-teacher plagiarism home_001
haocean-teacher plagiarism home_001 --check --method hybrid --threshold 0.75
haocean-teacher stats home_001
haocean-teacher history 2024001
```

`hybrid` 查重会比较当前作业内同期提交，以及当前作业提交与最近三年历史提交的交叉候选；先做本地 token 预筛，再交给 DeepSeek 复核。

8. 互评后计算最终成绩并归档课程：

```bash
haocean-teacher final-scores home_001 --calculate
haocean-teacher archive create --name 2026_spring.zip --note "2026 spring final archive"
haocean-teacher archive download 2026_spring.zip
```

教师端同样支持多 profile，token 默认保存在 `~/.haocean-teacher/auth_tokens/`。

## 明天真实环境演示清单

建议按下面顺序展示，能覆盖主要功能：

1. 老师安装、`setup`、`login`。
2. 老师 `class` 创建班级，复制加入码。
3. 两个学生分别用不同 profile 安装、`setup`、`login`、`join`。
4. 老师 `publish home_001 "Homework 1" --peer-review --teacher-weight 0.7`。
5. 两个学生 `list`，在 `~/.haocean/workspace/home_001/` 放入 `README.md` 或 `answer.txt`。
6. 学生 `preview home_001`，再 `submit home_001`。
7. 老师 `grade home_001`，进入 TUI：
   - `d` 下载并解压；
   - `o` 直接预览 `.md` / `.txt`；
   - `g` 看 AI 自动审阅报告；
   - `c` 看 AI 辅助查重；
   - `Enter` 批改；
   - `s` 看学生历史成绩。
8. 老师输入 `pr` 或执行 `peer-review home_001` 打开互评并自动分配。
9. 学生查看互评任务并提交互评分。
10. 老师 `final-scores home_001 --calculate` 查看最终成绩。
11. 学生 `feedback` 拉取 Markdown 反馈。
12. 老师 `archive create` 生成课程归档。

## AI Key 放在哪里

AI 分两类，key 的位置不同：

| 功能 | 谁调用 DeepSeek | key 放在哪里 |
| --- | --- | --- |
| 老师 TUI `g`：AI 自动审作业报告 | Module B 服务端 | 老师本机 `~/.haocean-teacher/.env`，或服务器统一配置 |
| 老师 TUI `c` / `plagiarism --check --method hybrid`：AI 查重复核 | Module B 服务端 | 老师本机 `~/.haocean-teacher/.env`，或服务器统一配置 |
| 学生/本机 `haocean ai-help` 使用小助手 | 当前学生或老师自己的终端 | 本机 shell 环境变量，例如 `~/.bashrc` |

### 老师端配置：查重和 AI 审阅报告

真实老师使用时，推荐每位老师在自己的机器上配置 key。教师端会读取本机 key，并通过 `X-DeepSeek-API-Key` 请求头发给 Module B；请优先使用 HTTPS 域名。

```bash
mkdir -p ~/.haocean-teacher
nano ~/.haocean-teacher/.env
```

示例：

```dotenv
MODULE_C_DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_MODEL=deepseek-v4-flash
```

也可以放在当前 shell：

```bash
export MODULE_C_DEEPSEEK_API_KEY=your-deepseek-key
```

老师端兼容这些变量名，优先级从高到低：

```text
MODULE_C_DEEPSEEK_API_KEY
DEEPSEEK_API_KEY
HAOCEAN_DEEPSEEK_API_KEY
```

配置后重新打开终端，或执行 `source ~/.bashrc`。然后在 TUI 里按 `g` 查看 AI 自动审作业报告，按 `c` 查看 AI 辅助查重。

### 服务器统一配置：查重和 AI 审阅报告

如果学校希望服务器统一承担 AI 调用，也可以在部署 Module B 的服务器上配置。仓库运行方式下推荐写入：

```bash
cd /Hao/gongchuang/module_b_server
nano .env
```

示例：

```dotenv
MODULE_B_DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_PREFILTER_SIMILARITY=0.45
DEEPSEEK_MAX_CANDIDATE_PAIRS=12
DEEPSEEK_MAX_CHARS_PER_SUBMISSION=8000
DEEPSEEK_TIMEOUT_SECONDS=30
```

`DEEPSEEK_API_KEY` 也可以；如果两个都设置，服务端优先读 `DEEPSEEK_API_KEY`。如果使用 systemd、Docker 或云平台部署，也可以把同样的变量写到服务进程环境里。

修改 key 后必须重启 Module B：

```bash
# 示例：手动 uvicorn 运行时，停止旧进程后重新启动
cd /Hao/gongchuang/module_b_server
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

验证服务端是否读到 key：

```bash
curl http://127.0.0.1:8000/v1/health
```

返回里的 `deepseek_configured` 应该是 `true`。如果是 `false`：

- 检查 `.env` 是否在 `module_b_server/.env`；
- 检查变量名是否是 `MODULE_B_DEEPSEEK_API_KEY` 或 `DEEPSEEK_API_KEY`；
- 检查是否已经重启 Module B。

### 本机配置：`haocean ai-help`

`haocean ai-help` 是本机使用小助手，和服务端查重/AI 审阅报告不是同一个 key 读取位置。学生如果想在自己的终端调用 DeepSeek，可以在本机配置：

```bash
echo 'export DEEPSEEK_API_KEY=your-deepseek-key' >> ~/.bashrc
source ~/.bashrc
haocean ai-help "怎么提交作业？"
```

也可以使用别名变量：

```bash
export HAOCEAN_DEEPSEEK_API_KEY=your-deepseek-key
```

没有配置本机 key 时，`haocean ai-help` 会输出内置帮助，不影响提交、批改、查重和反馈。

## 服务端配置

服务端需要 Python 3.10+。本地开发常用：

```bash
cd module_b_server
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

生产或真实演示需要确认：

- SMTP 已配置，否则邮箱验证码无法发送。
- 服务器上的 `DEEPSEEK_API_KEY` 或 `MODULE_B_DEEPSEEK_API_KEY` 已配置，否则 hybrid/AI 查重会提示缺少 key。
- 学生端和教师端默认域名能访问同一个 Module B 服务。

不要提交任何真实密钥、`.env`、运行时数据库、学生提交包或日志。

## 开发验证

```bash
make test
VERIFY_B_PORT=19080 make verify
```

当前验证覆盖：

- 学生端配置、登录、自动打包、提交、反馈、AI help。
- 服务端认证、班级、作业、提交、批改、查重、AI 报告、互评、归档。
- 教师端多 profile、发布、批改总览、TUI、查重、统计、最终成绩、归档。

## 项目结构

```text
module_a_client/       学生端 CLI
module_b_server/       FastAPI 服务端
module_c_controller/   教师端 CLI/TUI
module_d_ops/          集成验证脚本
docs/                  API、真实环境和本地联调文档
install-student.sh     学生一键安装脚本
install-teacher.sh     老师一键安装脚本
```

## 安全注意

不要提交或粘贴到公开渠道：

- `.env`
- GitHub token
- DeepSeek key
- SMTP 密码或授权码
- SQLite 运行时数据库
- 学生提交包、反馈文件、日志
- 虚拟环境目录
