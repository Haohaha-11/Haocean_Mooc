# 老师使用指南

本文档面向在另一台 Linux 机器上使用 Haocean Mooc 教师端的老师或助教。老师不需要登录服务器，也不需要服务器上的项目目录；安装后直接使用 `haocean-teacher` 命令。

## 1. 使用前提

你的 Linux 机器需要能访问：

- GitHub，用于安装客户端。
- Haocean 服务端，默认地址为 `https://teacher.haoceanlab.cn`。

如果学校还没有配置域名，也可以使用服务端 IP，例如：

```text
http://服务器IP:8000
```

安装基础依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git curl
```

## 2. 安装教师端

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-teacher.sh | bash
```

如果安装后提示找不到 `haocean-teacher`，执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

建议把这行加入 `~/.bashrc`：

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

检查安装：

```bash
haocean-teacher --help
```

## 3. 首次配置和登录

使用默认教师端域名时，直接运行：

```bash
haocean-teacher setup
haocean-teacher login
```

`setup` 会按提示让你输入：

```text
Teacher ID [T001]
Name
Email
```

教师编号可以直接回车使用默认值 `T001`，也可以输入自己的编号，例如 `T002`。

教师端支持多组本地配置。每次 `setup` 会创建或更新一组 profile；不传 `--profile` 时默认使用 `Teacher ID` 作为 profile 名。例如：

```bash
haocean-teacher setup --profile t001
haocean-teacher setup --profile t002 --teacher-id T002 --name "Teacher Two" --email teacher2@example.com
haocean-teacher profiles
```

执行 `login` 时，如果本地有多组 profile，会先让你选择身份，然后再发送邮箱验证码。

如果使用自建服务器 IP，可以只指定服务端地址，其余信息仍然按提示输入：

```bash
haocean-teacher setup --api-base-url http://服务器IP:8000

haocean-teacher login
```

`login` 会读取你选中的 profile 并发送邮箱验证码。输入验证码后，本地会保存该 profile 的登录 token。之后日常使用继续执行 `haocean-teacher login` 即可；如果配置缺失，`login` 会提示补齐。

教师端本地配置默认保存在：

```text
~/.haocean-teacher/config.json
~/.haocean-teacher/auth_tokens/
~/.haocean-teacher/downloads/
```

## 4. 创建班级

老师日常只需要记住短命令：

```bash
haocean-teacher class
```

系统会交互式提示：

```text
Class Name
Course Title [默认同 Class Name]
Class ID
```

有默认值时，直接回车确认；如果想改默认值，输入 `q` 后重新填写。

创建成功后会打印班级 ID 和加入码，并把这个班级设为当前选中班级。

兼容旧命令：

```bash
haocean-teacher classes create "CS101 Spring" \
  --course-title "Computer Science" \
  --class-id cs101
```

查看班级和加入码：

```bash
haocean-teacher classes list
```

输出示例：

```text
cs101    Computer Science    CS101 Spring    code=JOIN101
```

把 `JOIN101` 这样的加入码发给学生。学生需要用它加入班级。

同一老师名下班级名不可重复。`class_id` 是唯一标识；不填写时服务端会自动生成。

## 5. 选择班级

如果已经有多个班级，可以选择当前班级：

```bash
haocean-teacher select
```

系统会列出班级，输入左侧编号即可。选中的班级会保存到本地配置并打印完整班级信息，后续发布作业会默认使用它。

## 6. 发布作业

推荐短命令：

```bash
haocean-teacher publish
```

系统会交互式提示：

```text
Assignment ID
Title
Class ID [当前选中班级]
Description
Deadline
Course Weight
Peer Review
```

有默认班级和默认权重时，直接回车确认；输入 `q` 可以重新选择或填写。`Course Weight` 是课程总评相对权重，默认 `1`。`Peer Review` 用于在发布阶段决定该作业是否开启互评。

`Deadline` 按北京时间解析。支持 `6.10`、`6.10 18:30`、`2026-06-10`、`2026-06-10 18:30`；只写日期时默认截止到当天 `23:59:59`。

也可以直接带部分参数：

```bash
haocean-teacher publish home_001 "Homework 1" --weight 2 --peer-review --teacher-weight 0.7
```

`peer_weight` 默认自动等于 `1 - teacher_weight`。例如 `--teacher-weight 0.6` 时，学生互评权重自动为 `0.4`。`--peer-weight` 只作为高级覆盖参数保留。

兼容旧命令：

给指定班级发布作业：

```bash
haocean-teacher assignment create home_001 "Homework 1" \
  --class-id cs101 \
  --description "完成第一次作业" \
  --deadline "2026-06-15 23:59:59" \
  --weight 2 \
  --peer-review
```

如果不传 `--class-id`，作业会作为全局开放作业发布。

查看某个作业的整体情况：

```bash
haocean-teacher assignment view home_001
```

## 7. 批改作业

推荐短命令：

```bash
haocean-teacher grade home_001
```

系统会展示当前作业的批改总览菜单：待批改、已批改、全部提交、查重详情、成绩统计、互评阶段入口、最终成绩详情和 `Enter TUI`。输入序号后按 Enter 查看详情；进入 TUI 是单独选项，不会自动打开。直接运行 `haocean-teacher grade` 时，系统会要求输入作业编号，不再默认进入全局历史概览。

也可以直接指定作业：

```bash
haocean-teacher grade home_001
```

批改 TUI 中会显示当前提交、AI 批改报告、查重报告、教师分、互评分、互评奖励和最终分。选中某条提交后可以下载、预览、查重、查看 AI 报告和历史成绩。

兼容旧命令：

```bash
haocean-teacher tui
```

常用快捷键：

```text
p        查看待批改提交
a        查看已批改提交
l        查看全部提交
j/k      上下移动
方向键    上下移动
Enter    批改当前提交
Ctrl+s   在批改弹窗中保存分数和评语
d        下载当前提交包
o        预览解压目录中的 .md / .txt；没有可读文档时打开本地目录
g        查看当前提交的 AI 自动审阅报告
c        查看当前提交相关的 hybrid AI 查重结果
s        查看当前学生成绩统计
r        刷新
q        退出
Esc      关闭弹窗
```

批改时填写：

- 分数：0 到 100。
- 评语：不能为空。

保存后，服务端会更新提交状态并生成 Markdown 反馈，学生可以通过学生端拉取。

## 8. 下载学生提交包

如果知道提交编号：

```bash
haocean-teacher download 21
```

下载并解压：

```bash
haocean-teacher download 21 --extract
```

文件默认保存到：

```text
~/.haocean-teacher/downloads/
```

## 9. 查看查重、统计和历史成绩

查看作业查重报告：

```bash
haocean-teacher plagiarism home_001
```

触发 hybrid AI 查重。范围包含当前作业内同期提交，以及当前作业提交与最近三年历史提交的交叉候选：

```bash
haocean-teacher plagiarism home_001 --check --method hybrid --threshold 0.75
```

查看作业成绩统计：

```bash
haocean-teacher stats home_001
```

查看某个学生的历史成绩：

```bash
haocean-teacher history 2024001
```

## 10. 互评和最终成绩

互评是否开启应在发布作业时决定：交互式 `publish` 会询问 `Peer Review`，非交互式可以使用 `--peer-review` 或 `--no-peer-review`。开启后作业仍先处于提交阶段；等学生提交完成后，在 `grade <assignment_id>` 总览菜单中输入 `pr`，即可切到互评阶段并自动分配任务。

也可以直接使用快捷命令：

```bash
haocean-teacher peer-review home_001
```

自动分配互评任务时，默认每个学生互评 2 份作业；如果只有 2 个学生，则相互评 1 份；只有 1 个学生无法分配互评任务。

如果某个作业启用了互评，互评结束后可以重新计算最终成绩：

```bash
haocean-teacher final-scores home_final --calculate
```

只查看当前成绩：

```bash
haocean-teacher final-scores home_final
```

互评奖励规则：学生互评分与教师分相差不超过 5 分时，该学生本作业最多获得 `+1` 互评奖励。成绩统计会显示教师分、互评平均分、互评奖励、最终分和作业权重。

## 11. 课程归档

课程结束后生成归档包：

```bash
haocean-teacher archive create \
  --name 2026_spring.zip \
  --note "2026 spring final archive"
```

查看归档列表：

```bash
haocean-teacher archive list
```

下载归档包：

```bash
haocean-teacher archive download 2026_spring.zip
```

## 12. 常见问题

### 命令找不到

执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

然后重新运行：

```bash
haocean-teacher --help
```

### 登录收不到验证码

确认：

- 邮箱地址是否写错。
- 服务端是否已经配置 SMTP。
- 开发环境下验证码可能在服务端日志里。

### 连接不上服务器

如果没有使用默认域名，重新配置服务端地址：

```bash
haocean-teacher setup --api-base-url http://服务器IP:8000
```

### 登录时又提示配置信息

说明 `~/.haocean-teacher/config.json` 里缺少教师编号、Name 或邮箱。按提示补齐即可，系统会写回配置文件。

### 看不到学生提交

确认：

- 学生是否已经加入你的班级。
- 作业是否绑定到了正确 `class_id`。
- 学生是否已经成功提交。
- TUI 中是否在 `pending`、`approved`、`all` 之间切换到了正确视图。
