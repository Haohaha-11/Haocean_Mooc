# Haocean MOOC Teacher CLI

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
haocean-teacher setup --teacher-id T001 --email teacher@example.com
haocean-teacher login
```

默认服务地址是：

```text
https://teacher.haoceanlab.cn
```

配置文件与下载目录：

```text
~/.haocean-teacher/config.json
~/.haocean-teacher/auth_token
~/.haocean-teacher/downloads/
```

## 班级和作业

创建班级并生成学生加入码：

```bash
haocean-teacher classes create "CS101 Spring" --course-title "Computer Science" --class-id cs101
```

查看班级和加入码：

```bash
haocean-teacher classes list
```

给班级发布作业：

```bash
haocean-teacher assignment create home_001 "Homework 1" --class-id cs101 --deadline "2026-06-15 23:59:59"
```

## 批改和高级功能

打开批改 TUI：

```bash
haocean-teacher tui
```

查看查重报告：

```bash
haocean-teacher plagiarism home_001
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
