# 本机测试指南：老师端

本文档用于在当前机器 `/Hao/gongchuang` 工作区直接测试老师端最新本地代码。不要使用 `~/.local/bin/haocean-teacher`，那个可能是从 GitHub 安装的旧版本。

## 1. 启动本地服务端

开一个终端作为服务端终端：

```bash
cd /Hao/gongchuang/module_b_server
MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证服务端：

```bash
curl http://127.0.0.1:8000/health
```

正常应返回 JSON，并且包含：

```json
{
  "code": 200,
  "auth_required": true
}
```

注意：模块 B 当前使用 `module_b_server/data/db/engine.db`，里面可能已有历史 smoke 数据。

如果 `8000` 已被占用，可以换端口，例如：

```bash
MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

后续老师端 `setup --api-base-url` 和学生端 `setup --server-url` 都要同步改成这个端口。

## 2. 准备老师端测试环境

另开一个终端作为老师端终端：

```bash
cd /Hao/gongchuang
export HAOCEAN_TEACHER_HOME=/tmp/haocean-local-teacher
```

后续这个终端里的配置、token、下载文件会写到：

```text
/tmp/haocean-local-teacher/
```

## 3. 使用本地老师端脚本

本机测试统一使用：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py
```

可以先看 help：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py --help
```

你应该能看到短命令：

```text
class
select
publish
grade
```

## 4. 首次 setup

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py setup \
  --api-base-url http://127.0.0.1:8000 \
  --profile local-t001
```

按提示输入：

```text
Teacher ID [T001]
Name
Email
```

`Teacher ID` 有默认值时，直接回车确认；需要改就输入新值。

老师端现在支持多组本地配置。每次 `setup` 会创建或更新一组 profile；不传 `--profile` 时默认使用 `Teacher ID` 作为 profile 名。你可以为另一个老师再跑一次：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py setup \
  --api-base-url http://127.0.0.1:8000 \
  --profile local-t002 \
  --teacher-id T002 \
  --name "Teacher Two" \
  --email teacher2@example.com
```

查看当前已有 profile：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py profiles
```

## 5. 登录

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py login
```

如果本地有多组 profile，`login` 会先列出身份，让你输入序号、profile 名、Teacher ID 或邮箱。确认身份后才会发送邮箱验证码并登录。

登录会显示入场图案。右侧会显示老师快捷命令：

```text
class    create class
select   choose active class
publish  publish assignment
grade    review, download, plagiarism
```

由于服务端使用 `MODULE_B_DEV_VERIFICATION_LOG=true`，验证码会显示在老师端终端或服务端终端。输入验证码完成登录。

## 6. 创建班级

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py class
```

按提示输入：

```text
Class Name
Course Title [默认同 Class Name]
Class ID
```

同一老师名下 `Class Name` 不可重复。`Class ID` 是唯一标识；不填时服务端会自动生成。

有默认值时：

- 回车：确认默认值。
- 输入 `q`：重新填写。

创建成功后会输出 `Join Code`，这个码等会给学生端使用。

## 7. 选择班级

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py select
```

系统会列出班级。输入左侧序号，选中的班级会保存为当前班级，并打印完整班级信息。

## 8. 发布作业

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py publish
```

按提示输入：

```text
Assignment ID
Title
Class ID [当前选中班级]
Description
Deadline
Course Weight
Peer Review
```

`Deadline` 按北京时间解析。支持 `6.10`、`6.10 18:30`、`2026-06-10`、`2026-06-10 18:30`；只写日期时默认截止到当天 `23:59:59`。

也可以直接给部分参数：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py publish home_local_001 "Local Homework 1" --weight 2
```

如果这次作业需要互评，应在发布时就开启：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py publish home_local_001 "Local Homework 1" \
  --weight 2 \
  --peer-review \
  --teacher-weight 0.7
```

`peer_weight` 默认自动等于 `1 - teacher_weight`。例如 `--teacher-weight 0.6` 时，学生互评权重自动为 `0.4`。

开启后作业仍先处于提交阶段；等学生提交完成后，再由老师切到互评阶段并分配任务。

## 9. 批改作业

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py grade home_local_001
```

该命令会先显示批改总览菜单：

- 提交数量。
- pending / graded / rejected 统计。
- 成绩统计。
- 查重概览。
- 最终成绩概览。
- 单独的 `Enter TUI` 入口。

输入序号后按 Enter 查看详情；只有选择 `Enter TUI` 时才进入批改 TUI。

TUI 常用键：

```text
p        待批改
a        已批改
l        全部
j/k      上下移动
Enter    批改选中提交
Ctrl+s   保存分数和评语
d        下载选中提交包
s        查看当前学生成绩统计
r        刷新
q        退出
```

## 10. 查重测试

只查看自动查重报告：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py plagiarism home_local_001
```

手动触发本地 token 查重，不依赖 DeepSeek：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py plagiarism home_local_001 --check --method token --threshold 0.75
```

手动触发 DeepSeek 混合查重：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py plagiarism home_local_001 --check --method hybrid --threshold 0.75
```

`hybrid` / `ai` 需要模块 B 启动时能读到 `DEEPSEEK_API_KEY` 或 `MODULE_B_DEEPSEEK_API_KEY`。如果刚更新了 `module_b_server/.env`，必须重启模块 B 服务。

如果作业提交数少于 2 个，现在也会返回完整检查摘要，`Pairs` 和 `Suspected` 应显示为 0 / none，而不是 `None`。

## 11. 给学生端准备互评任务

互评是否开启应在第 8 步发布作业时决定，例如 `publish ... --peer-review`。本步骤只负责在提交结束后切换阶段并自动分配互评任务。

至少两个不同学生提交后，老师可以在作业批改总览中打开互评阶段：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py grade home_local_001
```

在总览菜单输入 `pr`，系统会把作业阶段切到 `peer_review` 并自动分配互评任务。

也可以直接执行快捷命令：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py peer-review home_local_001
```

默认每个学生互评 2 份作业；如果只有 2 个学生，则相互评 1 份；只有 1 个学生无法分配互评任务。

然后让学生端执行：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py peer-review --assignment-id home_local_001
```

如果模块 B 不是 `8000` 端口，老师端先重新 `setup --api-base-url http://127.0.0.1:<端口>`，确保老师端和学生端指向同一个模块 B。

## 12. 本地验收脚本

完整跑一遍测试和端到端验收：

```bash
cd /Hao/gongchuang
make test
VERIFY_B_PORT=19080 make verify
```

`make verify` 默认用 `18080`。如果该端口已有旧服务，可能会看到 `address already in use` 或 HTTP 501，这时换成 `VERIFY_B_PORT=19080` 这类空闲端口重跑。

## 13. 常见问题

### 仍然跑到旧版本

确认你运行的是：

```bash
module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py
```

不要运行：

```bash
haocean-teacher
```

除非你已经把本地工作区重新安装进当前环境。

### health 返回空或不是 JSON

先测：

```bash
curl -i http://127.0.0.1:8000/health
```

如果失败，说明模块 B 没启动，或端口不是 `8000`。

### 登录时没看到验证码

检查服务端启动命令是否包含：

```bash
MODULE_B_DEV_VERIFICATION_LOG=true
```

验证码可能显示在服务端终端。

### DeepSeek key 更新后仍然不可用

模块 B 只在启动时读取 `.env` 和环境变量。更新 `module_b_server/.env` 后，停止并重启模块 B 服务，再重新跑查重或 AI 批改报告。
