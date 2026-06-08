# Haocean Mooc Teacher CLI

模块 C 是教师端终端工具。真实使用时教师不需要登录服务器；安装后在自己的 Linux 终端使用 `haocean-teacher`，配置和下载文件默认保存在 `~/.haocean-teacher/`。

## 安装

开发仓库内安装：

```bash
cd module_c_controller
python3 -m pip install -e .
```

安装后会得到命令：

```bash
haocean-teacher --help
```

## 首次配置

```bash
haocean-teacher setup
haocean-teacher login
```

`setup` 会按提示输入教师编号、Name 和邮箱。教师编号可以直接回车使用默认值 `T001`。`login` 会读取你选中的 profile；如果配置缺失，会提示补齐。

老师端支持多组本地配置。每次 `setup` 会创建或更新一组 profile；不传 `--profile` 时默认使用教师编号作为 profile 名。已有多组 profile 时，`login` 会先让你选择身份，然后再发送邮箱验证码：

```bash
haocean-teacher setup --profile t001
haocean-teacher setup --profile t002 --teacher-id T002 --name "Teacher Two" --email teacher2@example.com
haocean-teacher profiles
haocean-teacher login
```

默认服务地址是：

```text
https://teacher.haoceanlab.cn
```

配置文件与下载目录：

```text
~/.haocean-teacher/config.json
~/.haocean-teacher/auth_tokens/
~/.haocean-teacher/downloads/
```

## 班级和作业

创建班级并生成学生加入码：

```bash
haocean-teacher class
```

同一老师名下班级名不可重复。`class_id` 是唯一标识；不填写时服务端会自动生成。

查看班级和加入码：

```bash
haocean-teacher classes list
```

给班级发布作业：

```bash
haocean-teacher select
haocean-teacher publish
```

需要互评的作业应在发布时开启：

```bash
haocean-teacher publish home_001 "Homework 1" --peer-review --teacher-weight 0.7
```

学生互评权重默认自动等于 `1 - teacher_weight`。
学生提交完成后，在 `haocean-teacher grade home_001` 总览菜单输入 `pr`，即可切到互评阶段并自动分配任务。也可以直接运行：

```bash
haocean-teacher peer-review home_001
```

`Deadline` 按北京时间解析，`6.10` 会保存为当前北京时间年份的 `06-10 23:59:59`。

## 批改和高级功能

打开批改总览：

```bash
haocean-teacher grade home_001
```

总览菜单按当前作业统计；输入 `pr` 可打开互评阶段并分配任务；选择 `Enter TUI` 进入全屏批改界面。TUI 中按 `s` 查看当前学生成绩统计，按 `g` 查看当前提交的 AI 审阅报告，按 `c` 查看当前提交相关的 hybrid AI 查重结果，按 `d` 下载并解压提交包，按 `o` 优先预览解压目录中的 `.md` / `.txt` 文件，没有可读文档时打开本地内容目录。直接运行 `haocean-teacher grade` 时会提示输入作业编号。

查看查重报告：

```bash
haocean-teacher plagiarism home_001
```

触发混合 AI 查重并输出疑似重复对：

```bash
haocean-teacher plagiarism home_001 --check --method hybrid --threshold 0.75
```

查看作业成绩统计：

```bash
haocean-teacher stats home_001
```

查看学生历史成绩：

```bash
haocean-teacher history 2024001
```

重新计算互评后的最终成绩：

```bash
haocean-teacher final-scores home_final --calculate
```

下载某个提交包到本机：

```bash
haocean-teacher download 21 --extract
```

课程结束生成并下载归档：

```bash
haocean-teacher archive create --name 2026_spring.zip --note "2026 spring final archive"
haocean-teacher archive download 2026_spring.zip
```

## 本地 Mock 模式

如需继续使用旧的 SQLite mock 演示模式：

```bash
CONTROLLER_SOURCE=sqlite python3 scripts/run_controller.py
```

## 测试

```bash
python3 -m pytest -q
```
