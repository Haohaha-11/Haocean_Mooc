# 本机测试指南：学生端

本文档用于在当前机器 `/Hao/gongchuang` 工作区直接测试学生端最新本地代码。不要使用 `~/.local/bin/haocean-student`，那个可能是从 GitHub 安装的旧版本。

## 1. 确认本地服务端已启动

先按老师端本机指南启动模块 B：

```bash
cd /Hao/gongchuang/module_b_server
MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证：

```bash
curl http://127.0.0.1:8000/health
```

## 2. 准备学生端测试环境

另开一个终端作为学生端终端：

```bash
cd /Hao/gongchuang
export HAOCEAN_HOME=/tmp/haocean-local-student
```

后续这个终端里的配置、token、作业工作区和反馈会写到：

```text
/tmp/haocean-local-student/
```

## 3. 使用本地学生端脚本

本机测试统一使用：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py
```

可以先看 help：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py --help
```

本地 AI 使用小助手也走同一个入口，先用内置帮助验证，不依赖 DeepSeek：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py ai-help --local "怎么提交作业？"
```

如果你已经重新安装过本地包，也可以测试 `haocean ai-help`；但排查本地代码时优先用上面的 `run_client.py`。

## 4. 首次 setup

从老师端创建班级后拿到 `Join Code`，例如：

```text
JOIN101
```

然后运行：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py setup \
  --server-url http://127.0.0.1:8000
```

按提示输入：

```text
Student ID
Name
Email
Class Code (optional)
```

建议在 `Class Code (optional)` 直接输入老师端打印的加入码。

如果要在同一台机器模拟多个学生（例如互评测试），用不同 profile 保存身份和 token：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py setup \
  --profile local-s001 \
  --server-url http://127.0.0.1:8000 \
  --student-id S001 \
  --name "Student One" \
  --email student1@example.com \
  --class-code JOIN101

module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py setup \
  --profile local-s002 \
  --server-url http://127.0.0.1:8000 \
  --student-id S002 \
  --name "Student Two" \
  --email student2@example.com \
  --class-code JOIN101

module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py profiles
```

不传 `--profile` 时，profile 名默认使用学号。旧版单配置会在新的 `setup` 写入时自动迁移到 `profiles` 结构。

## 5. 登录

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py login
```

如果本地已经有 profile，登录会先列出身份；输入序号、profile 名、学号或邮箱选择当前学生。之后会显示入场图案。由于服务端使用 `MODULE_B_DEV_VERIFICATION_LOG=true`，验证码会显示在学生端终端或服务端终端。输入验证码完成登录。

如果 setup 时填写了班级码，登录成功后会自动加入班级。

## 6. 查看班级和作业

查看已加入班级：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py classes
```

查看开放作业：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py list
```

## 7. 准备作业文件

假设老师发布的作业编号是：

```text
home_local_001
```

创建本地作业目录：

```bash
mkdir -p /tmp/haocean-local-student/workspace/home_local_001
```

写一个测试文件：

```bash
printf 'hello from local student\n' > /tmp/haocean-local-student/workspace/home_local_001/answer.txt
```

## 8. 预览提交

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py preview home_local_001
```

确认 included files 里有你的作业文件。

## 9. 提交作业

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py submit home_local_001
```

成功后，服务端会出现一条 `pending` 提交，老师端 `grade home_local_001` 可以看到。

## 10. 拉取反馈

老师端批改后，学生端运行：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py feedback
```

反馈会保存到：

```text
/tmp/haocean-local-student/feedback_inbox/
```

## 11. 互评测试

互评需要老师端先启用互评、至少有两个不同学生提交，并生成互评任务。默认每个学生互评 2 份；如果只有 2 个学生，则相互评 1 份。老师端准备好后，学生端可以查看自己的互评任务：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py peer-review
```

按作业筛选：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py peer-review --assignment-id home_local_001
```

提交互评分：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py peer-review 21 95 --comment "完成较好，结构清晰"
```

这里的 `21` 是任务列表里显示的 `submission=<id>`。服务端会校验该提交是否分配给当前学生，不能随便评别人或评自己的提交。

## 12. 本地验收脚本

如果要跑完整本地验收，建议先避开可能被旧服务占用的 `18080`：

```bash
cd /Hao/gongchuang
VERIFY_B_PORT=19080 make verify
```

如果 `19080` 也被占用，换一个空闲端口即可。

## 13. 常见问题

### 仍然跑到旧版本

确认你运行的是：

```bash
module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py
```

不要运行：

```bash
haocean-student
```

除非你已经把本地工作区重新安装进当前环境。

### 看不到作业

确认：

- 老师端已经发布作业。
- 学生端已经加入老师创建的班级。
- 学生端 `setup` 使用的是 `http://127.0.0.1:8000`。
- 如果服务端换了端口，学生端也要重新 `setup --server-url http://127.0.0.1:<端口>`。

### 提交后老师端看不到

确认：

- 作业编号和目录名完全一致。
- 学生提交命令成功结束。
- 老师端使用的是同一个本地模块 B 服务。

### 想重新来一遍干净测试

可以换一个新的测试目录：

```bash
export HAOCEAN_HOME=/tmp/haocean-local-student-2
```

模块 B 的数据库仍然是 `module_b_server/data/db/engine.db`，历史提交数据不会因为换学生端目录而清空。

### AI 帮助没有调用 DeepSeek

本地测试建议先用 `--local`。如果要真实调用 DeepSeek，确认当前终端或 `module_a_client/.env` 里有 `DEEPSEEK_API_KEY`，并且不要把 key 写进文档或提交。
