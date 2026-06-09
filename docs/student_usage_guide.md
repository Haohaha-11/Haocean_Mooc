# 学生使用指南

本文档面向在另一台 Linux 机器上使用 Haocean Mooc 学生端的学生。学生不需要登录服务器，也不需要服务器上的项目目录；安装后直接使用 `haocean-student` 命令。

## 1. 使用前提

你的 Linux 机器需要能访问：

- GitHub，用于安装客户端。
- Haocean 服务端，默认地址为 `https://student.haoceanlab.cn`。

如果学校还没有配置域名，也可以使用服务端 IP，例如：

```text
http://服务器IP:8000
```

安装基础依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

你还需要从老师那里拿到班级加入码，例如：

```text
JOIN101
```

## 2. 安装学生端

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-student.sh | bash
```

如果安装后提示找不到 `haocean-student`，执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

建议把这行加入 `~/.bashrc`：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

检查安装：

```bash
haocean-student --help
haocean ai-help --local "怎么提交作业？"
```

`haocean-student` 是学生端正式命令；`haocean ai-help` 只用于打开 DeepSeek 使用小助手。没有配置 `DEEPSEEK_API_KEY` 时，小助手会使用内置本地帮助。

如果学生希望 `haocean ai-help` 真正调用 DeepSeek，在学生自己的机器上配置环境变量即可：

```bash
echo 'export DEEPSEEK_API_KEY=your-deepseek-key' >> ~/.bashrc
source ~/.bashrc
haocean ai-help "怎么提交作业？"
```

也可以使用 `HAOCEAN_DEEPSEEK_API_KEY`。这只影响本机帮助命令，不影响提交作业；老师端 AI 查重和 AI 审阅报告使用老师端本机 key 或服务器 Module B key，不读取学生机器上的 key。

## 3. 首次配置和登录

使用默认学生端域名时，直接运行：

```bash
haocean-student setup
haocean-student login
```

`setup` 会按提示让你输入：

```text
Student ID
Name
Email
Class Code (optional)
```

`JOIN101` 是老师给你的班级加入码。建议在 `Class Code (optional)` 这里直接输入，`login` 成功后会自动加入班级。如果 setup 时先跳过，也可以登录后再执行 `haocean-student join JOIN101`。

如果使用自建服务器 IP，可以只指定服务端地址，其余信息仍然按提示输入：

```bash
haocean-student setup --server-url http://服务器IP:8000
haocean-student login
```

`login` 会读取 `setup` 保存的信息并发送邮箱验证码。输入验证码后，本地会保存登录 token。之后日常使用继续执行 `haocean-student login` 即可；如果配置缺失，`login` 会提示补齐。

学生端支持多组本地 profile。同一台机器需要保存多个学生身份时，可以这样创建并查看：

```bash
haocean-student setup --profile s001
haocean-student setup --profile s002 --student-id 2024002 --name "Student Two" --email student2@example.com
haocean-student profiles
```

执行 `haocean-student login` 时，如果本地有 profile，会先列出身份。输入序号、profile 名、学号或邮箱选择身份后，系统才会发送邮箱验证码。每个 profile 使用独立登录 token，互相不会覆盖。

学生端本地配置默认保存在：

```text
~/.haocean/config.json
~/.haocean/auth_tokens/
~/.haocean/workspace/
~/.haocean/cache/archives/
~/.haocean/feedback_inbox/
~/.haocean/logs/haocean.log
```

旧版单配置里的 `~/.haocean/auth_token` 仍然兼容；执行新的 `setup` 后会迁移到 profile 结构。

## 4. 加入班级

如果 setup 时已经填写了班级加入码，登录后会自动加入班级。如果当时跳过了，可以用老师给的加入码加入班级：

```bash
haocean-student join JOIN101
```

查看自己已经加入的班级：

```bash
haocean-student classes
```

## 5. 查看开放作业

```bash
haocean-student list
```

输出会包含：

- 作业编号，例如 `home_001`。
- 作业标题。
- 所属班级。
- 截止时间。

提交作业时需要使用作业编号。

## 6. 准备作业文件

学生端默认工作区是：

```text
~/.haocean/workspace/
```

每个作业一个目录，目录名必须等于作业编号。例如作业编号是 `home_001`：

```bash
mkdir -p ~/.haocean/workspace/home_001
```

把你的作业文件放进去：

```bash
nano ~/.haocean/workspace/home_001/answer.py
```

目录示例：

```text
~/.haocean/workspace/home_001/
├── answer.py
└── README.md
```

## 7. 预览提交内容

提交前建议先预览：

```bash
haocean-student preview home_001
```

或者：

```bash
haocean-student submit home_001 --dry-run
```

预览会显示：

- 会被打包的文件。
- 被排除的文件。
- 临时压缩包路径。
- 压缩包内部文件列表。

默认会排除：

```text
.git/
.venv/
venv/
__pycache__/
node_modules/
*.log
*.db
*.zip
*.tar
*.gz
```

如果老师明确要求提交压缩包，需要加：

```bash
haocean-student submit home_001 --allow-zip
```

## 8. 提交作业

```bash
haocean-student submit home_001
```

学生端会自动：

1. 读取 `~/.haocean/workspace/home_001/`。
2. 过滤不应提交的缓存和系统文件。
3. 打包为 `tar.gz`。
4. 计算 MD5。
5. 上传到服务端。
6. 等待服务端校验和入库。

提交成功后，服务端状态会变成 `pending`，等待老师批改。

## 9. 自动监控提交

如果希望学生端持续监控工作区：

```bash
haocean-student watch
```

它会不断扫描开放作业目录。检测到文件变化后，会等待文件稳定一段时间，再自动打包提交，避免保存文件时频繁上传。

如果想放到后台运行：

```bash
nohup haocean-student watch > ~/.haocean/watch.log 2>&1 &
```

## 10. 拉取老师反馈

```bash
haocean-student feedback
```

反馈默认保存到：

```text
~/.haocean/feedback_inbox/
```

反馈文件是 Markdown 格式，内容包括：

- 提交编号。
- 学号。
- 作业编号。
- 批改时间。
- 分数。
- 老师评语。

## 11. 互评

如果课程开启互评，老师进入互评阶段并分配任务后，先查看自己的互评任务：

```bash
haocean-student peer-review --assignment-id home_001
```

然后按任务中的提交编号提交互评分：

```bash
haocean-student peer-review 21 95 --comment "完成较好，结构清晰"
```

其中：

- `21` 是被互评的提交编号。
- `95` 是你的互评分数。

## 12. 常见问题

### 命令找不到

执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

然后重新运行：

```bash
haocean-student --help
```

### 登录收不到验证码

确认：

- 邮箱地址是否写错。
- 服务端是否已经配置 SMTP。
- 开发环境下验证码可能在服务端日志里。

### 登录时又提示配置信息

说明当前选中的 profile 里缺少学号、Name 或邮箱。按提示补齐即可，系统会写回 `~/.haocean/config.json`。

### 看不到作业

确认：

- 是否已经加入老师给的班级。
- 老师是否已经发布作业。
- 老师发布作业时是否绑定了正确班级。
- 当前配置的服务端地址是否正确。

### 提交失败

确认：

- 作业目录名是否和作业编号一致。
- 作业目录里是否真的有文件。
- 网络是否能访问服务端。
- 如果要提交压缩包，是否加了 `--allow-zip`。

### 反馈为空

可能原因：

- 老师还没有批改。
- 老师批改后你还没有重新执行 `haocean-student feedback`。
- 当前登录的学号和提交作业的学号不一致。
