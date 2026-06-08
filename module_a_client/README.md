# Haocean Mooc Student CLI

模块 A 是学生端命令行工具。学生不需要服务器上的 `/Hao/gongchuang/module_a_client` 目录；安装后直接在自己的 Linux 终端使用 `haocean-student`，配置、登录令牌、工作区和反馈默认保存在 `~/.haocean/`。

## 安装

开发仓库内安装：

```bash
cd module_a_client
python3 -m pip install -e .
```

安装后会得到命令：

```bash
haocean-student --help
haocean ai-help
```

## 首次配置

```bash
haocean-student setup
haocean-student login
```

`setup` 会按提示输入学号、Name、邮箱和可选班级加入码。`login` 会读取 setup 保存的信息；如果配置缺失，会提示补齐。

老师给学生的是班级加入码，例如 `JOIN101`。如果 setup 时已经填写，login 成功后会自动加入班级；如果当时跳过，可以之后执行 `join`。

学生端支持多组本地配置。每次 `setup` 会创建或更新一组 profile；不传 `--profile` 时默认使用学号作为 profile 名。已有多组 profile 时，`login` 会先让你选择身份，然后再发送邮箱验证码：

```bash
haocean-student setup --profile s001
haocean-student setup --profile s002 --student-id 2024002 --name "Student Two" --email student2@example.com
haocean-student profiles
haocean-student login
```

默认服务地址是：

```text
https://student.haoceanlab.cn
```

`setup` 和 `login` 会写入：

```text
~/.haocean/config.json
~/.haocean/workspace/
~/.haocean/feedback_inbox/
~/.haocean/auth_tokens/
```

旧版单配置里的 `~/.haocean/auth_token` 仍然兼容；迁移到 profile 后，新登录令牌默认按 profile 分别保存到 `~/.haocean/auth_tokens/`。

如果之后需要加入新的班级，也可以再次执行：

```bash
haocean-student join JOIN101
```

## 日常使用

查看自己班级内开放作业：

```bash
haocean-student list
```

查看已加入班级：

```bash
haocean-student classes
```

提交作业。学生把文件放入对应目录：

```text
~/.haocean/workspace/home_001/
```

然后运行：

```bash
haocean-student submit home_001
```

提交前可先预览本次打包内容：

```bash
haocean-student submit home_001 --dry-run
# 或
haocean-student preview home_001
```

默认只会打包常见作业文件（如 `.py/.md/.pdf/.ipynb/.jpg` 等），并自动排除
`.git/`、`.venv/`、`venv/`、`__pycache__/`、`node_modules/`、`*.log`、`*.db`、`*.zip` 等缓存/历史压缩包。
如果确实要提交压缩包，需显式加 `--allow-zip`。

持续监控并自动提交：

```bash
haocean-student watch
```

拉取教师反馈：

```bash
haocean-student feedback
```

## AI 使用小助手

`haocean` 只作为帮助入口，学生端日常命令仍然使用 `haocean-student`。

```bash
export DEEPSEEK_API_KEY=your-new-deepseek-key
haocean ai-help
haocean ai-help "怎么提交作业？"
haocean-student ai-help "怎么查看反馈？"
```

未配置 `DEEPSEEK_API_KEY` 时，小助手会输出内置本地帮助摘要。

## 配置

推荐使用 `~/.haocean/config.json`，也兼容环境变量：

```dotenv
MODULE_A_SERVER_URL=https://student.haoceanlab.cn
MODULE_A_STUDENT_ID=2024001
MODULE_A_NAME=Alice Student
MODULE_A_EMAIL=student@example.com
MODULE_A_CLASS_CODE=JOIN101
MODULE_A_WORKSPACE_DIR=~/.haocean/workspace
MODULE_A_CACHE_DIR=~/.haocean/cache/archives
MODULE_A_FEEDBACK_DIR=~/.haocean/feedback_inbox
MODULE_A_LOG_FILE=~/.haocean/logs/haocean.log
```

## 测试

```bash
python3 -m pytest -q
```
