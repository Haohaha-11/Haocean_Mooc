# Linux 命令行作业提交说明

## 1. 查看作业和附件

我先使用 `haocean-student classes` 查看自己已经加入的班级，再用 `haocean-student list` 查看当前开放作业。作业列表中可以看到作业编号、标题、所属班级、是否有 materials 以及截止时间。

确认本次作业编号后，我执行 `haocean-student materials linux_cli_report_20260610` 下载老师发布的作业要求。下载完成后，作业说明被保存到当前 workspace 的 `materials/` 目录中，我可以直接用 `cat` 在终端中阅读要求。

## 2. 准备本地文件

我把答案文件放在当前作业目录下，保持目录结构简单清楚：

```text
linux_cli_report_20260610/
├── answer.md
└── materials/
    └── linux_cli_submission_spec.md
```

这样老师下载我的提交包后，可以直接看到答案文件，也能看到我阅读过的作业说明材料。

## 3. 预览和提交

正式提交前，我使用 `haocean-student preview linux_cli_report_20260610` 检查即将打包上传的内容。预览结果会列出 included files、excluded files 和 archive members，我重点确认 `answer.md` 被包含在提交包中，同时没有把 `.git`、缓存目录、日志文件、数据库文件或旧压缩包误提交进去。

确认无误后，我执行 `haocean-student submit linux_cli_report_20260610` 完成提交。提交过程中客户端会生成压缩包并计算 MD5，服务端接收后保存提交记录，老师端就能在批改界面看到我的作业。

## 4. 学习体会

这种流程让我更直接地理解 Linux 路径、文件组织和命令行工具的作用。作业不是通过网页点击上传完成，而是需要自己明确当前目录、文件内容、提交包组成和命令参数，因此更接近真实 Linux 环境中的工作方式。
