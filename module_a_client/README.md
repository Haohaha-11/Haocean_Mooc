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
```

## 首次配置

```bash
haocean-student setup --student-id 2024001 --email student@example.com --class-code JOIN101
haocean-student login
```

默认服务地址是：

```text
https://student.haoceanlab.cn
```

`setup` 会写入：

```text
~/.haocean/config.json
~/.haocean/workspace/
~/.haocean/feedback_inbox/
~/.haocean/auth_token
```

老师给学生的是班级加入码，例如 `JOIN101`。如果首次配置时没有填写，也可以之后执行：

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

## 配置

推荐使用 `~/.haocean/config.json`，也兼容环境变量：

```dotenv
MODULE_A_SERVER_URL=https://student.haoceanlab.cn
MODULE_A_STUDENT_ID=2024001
MODULE_A_EMAIL=student@example.com
MODULE_A_CLASS_CODE=JOIN101
MODULE_A_WORKSPACE_DIR=~/.haocean/workspace
MODULE_A_CACHE_DIR=~/.haocean/cache/archives
MODULE_A_FEEDBACK_DIR=~/.haocean/feedback_inbox
MODULE_A_LOG_FILE=~/.haocean/logs/haocean.log
```

## 测试

```bash
python3 -m unittest discover -s tests
```
