# 报告截图自测流程

本文档用于准备 `/Hao/gongchuang/docs/report_new.md` 的最终截图材料。默认流程使用线上真实 Module B 服务、真实学生端 CLI、真实教师端 CLI/TUI，不需要使用昨天生成的截图。

目标截图：

1. 学生端查看老师布置的作业、作业附件和要求。
2. 老师端 TUI 主界面。
3. 老师端 TUI 查看学生历史得分。
4. 老师端 TUI 查看 AI 查重报告。
5. 老师端 TUI 查看 AI 审阅报告。

## 0. 注意事项

- 不要把真实 DeepSeek key 写进 `docs/`、报告正文、截图或聊天记录。
- 本流程使用 `/tmp/haocean-report-demo` 作为临时 HOME，避免污染你平时的 `~/.haocean` 和 `~/.haocean-teacher`。
- 线上真实环境会走真实邮箱验证码；本地备用模式才通过 `MODULE_B_DEV_VERIFICATION_LOG=true` 在服务端终端打印验证码。
- 如果某个固定 `class_id`、`join_code` 或 `assignment_id` 已存在，先用 `classes list` / `assignment list` 确认；已经存在就继续下一步，不要重复创建。只有确认不是本次演示对象时，才把下面环境变量中的后缀改成新的，例如把 `20260610` 改成 `20260610b`。
- 多行命令一次只粘贴一份。尤其是 `assignment create`，如果把两份命令粘到一起，最后一行会变成类似 `--weight 1.0hteacher`，这不是服务端问题，而是 shell 收到的参数被拼接错了。

## 0.5 fresh GitHub clone 验证模式

如果明天要演示“从 GitHub 拉下来再测试”，先用一个全新的临时目录，避免混到当前开发目录：

```bash
export FRESH_ROOT=/tmp/haocean-fresh-$(date +%Y%m%d%H%M%S)
mkdir -p "$FRESH_ROOT"
cd "$FRESH_ROOT"
git clone https://github.com/Haohaha-11/Haocean_Mooc.git
cd Haocean_Mooc

python3 -m venv module_a_client/.venv
module_a_client/.venv/bin/python -m pip install --upgrade pip
module_a_client/.venv/bin/python -m pip install -e module_a_client

python3 -m venv module_c_controller/.venv
module_c_controller/.venv/bin/python -m pip install --upgrade pip
module_c_controller/.venv/bin/python -m pip install -e module_c_controller

export REPO_ROOT="$(pwd)"
echo "REPO_ROOT=$REPO_ROOT"
```

记下终端打印的 `REPO_ROOT=...`。后面每个新终端 `source /tmp/haocean-report-demo/env.sh` 后，如果使用 fresh clone，再补一句，路径换成刚才打印出来的实际路径：

```bash
export REPO_ROOT=/tmp/haocean-fresh-具体时间戳/Haocean_Mooc
```

如果不做 fresh clone，默认继续使用当前目录：

```bash
export REPO_ROOT=/Hao/gongchuang
```

## 1. 公共环境变量

先开一个普通终端，写入本次截图的公共变量：

```bash
mkdir -p /tmp/haocean-report-demo

cat > /tmp/haocean-report-demo/env.sh <<'EOF'
export DEMO_ROOT=/tmp/haocean-report-demo
export REPO_ROOT=${REPO_ROOT:-/Hao/gongchuang}
export TEACHER_URL=https://teacher.haoceanlab.cn
export STUDENT_URL=https://student.haoceanlab.cn
export SERVER_URL="$TEACHER_URL"
export CONTROLLER_REQUEST_TIMEOUT_SECONDS=60
export MODULE_A_REQUEST_TIMEOUT_SECONDS=60
export HAOCEAN_TEACHER_HOME=/tmp/haocean-report-demo/teacher
export HAOCEAN_HOME=/tmp/haocean-report-demo/student

export CLASS_ID=linux_cli_report_class_20260610
export CLASS_NAME="Report Demo Class"
export COURSE_TITLE="Linux CLI Course"
export JOIN_CODE=RPT610

export ASSIGNMENT_ID=linux_cli_report_20260610
export ASSIGNMENT_TITLE="Linux 命令行作业流程报告"
export ASSIGNMENT_DESC="请提交一份 Markdown 文档，说明你如何在 Linux 终端中查看作业、下载附件、预览提交包并完成提交。"

export TEACHER_ID=T_REPORT_SCREENSHOT
export TEACHER_EMAIL=your-teacher-email@example.com
export STUDENT1_ID=2026061001
export STUDENT1_EMAIL=your-student1-email@example.com
export STUDENT2_ID=2026061002
export STUDENT2_EMAIL=your-student2-email@example.com

hteacher() {
  cd "$REPO_ROOT" && module_c_controller/.venv/bin/python -B module_c_controller/scripts/run_controller.py "$@"
}

hstudent() {
  cd "$REPO_ROOT" && module_a_client/.venv/bin/python -B module_a_client/scripts/run_client.py "$@"
}
EOF

source /tmp/haocean-report-demo/env.sh
```

后面每开一个新终端，都先执行：

```bash
source /tmp/haocean-report-demo/env.sh
```

默认就是线上真实环境。老师端 `setup` 使用 `$TEACHER_URL`，学生端 `setup` 使用 `$STUDENT_URL`。

演示前把 `TEACHER_EMAIL`、`STUDENT1_EMAIL`、`STUDENT2_EMAIL` 换成你能收验证码的邮箱。可以临时用同一个邮箱收多个身份的验证码，但要注意每次登录使用最新邮件中的验证码；更推荐学生 2 使用另一个可收码邮箱。

线上发验证码有时会等待 SMTP 返回，10 秒默认超时可能不够，因此这里默认把老师端和学生端请求超时都设为 60 秒：

```bash
export CONTROLLER_REQUEST_TIMEOUT_SECONDS=60
export MODULE_A_REQUEST_TIMEOUT_SECONDS=60
```

如果遇到 `Failed to resolve 'teacher.haoceanlab.cn'`，这是当前机器 DNS 解析问题，不是作业发布失败；先执行：

```bash
getent hosts teacher.haoceanlab.cn
curl https://teacher.haoceanlab.cn/health
```

正常情况下应解析到服务器 IP，并返回 `code: 200`。

这台演示 VM 如果反复出现 `Failed to resolve 'teacher.haoceanlab.cn'`，线上演示前先固定 hosts，避免截图过程中 DNS 抖动：

```bash
echo '43.247.134.254 teacher.haoceanlab.cn student.haoceanlab.cn' >> /etc/hosts
```

执行后确认：

```bash
getent hosts teacher.haoceanlab.cn
getent hosts student.haoceanlab.cn
tail -n 5 /etc/hosts
```

注意：这行命令只粘贴一次。如果终端里出现 `/etc/hostsecho` 或同一行里出现两段 `echo ... >> /etc/hosts`，说明粘贴时两条命令连在了一起；此时以 `getent hosts teacher.haoceanlab.cn` 是否能解析为准。

如果你想改成本地备用模式，在每个终端 `source` 后追加执行：

```bash
source /tmp/haocean-report-demo/env.sh
export TEACHER_URL=http://127.0.0.1:8000
export STUDENT_URL=http://127.0.0.1:8000
export SERVER_URL="$TEACHER_URL"
```

## 2. 配置 DeepSeek key

线上服务当前健康检查如果显示 `deepseek_configured=true`，说明服务端已经配置了 DeepSeek，可以跳过本节。若你想使用自己的 key，推荐使用老师端本地 key。这样不会把 key 写进报告目录。

在老师端终端执行：

```bash
source /tmp/haocean-report-demo/env.sh
mkdir -p "$HAOCEAN_TEACHER_HOME"
chmod 700 "$HAOCEAN_TEACHER_HOME"

read -s -p "Paste DeepSeek key: " DEEPSEEK_KEY
printf '\n'
printf 'MODULE_C_DEEPSEEK_API_KEY=%s\nDEEPSEEK_MODEL=deepseek-v4-flash\n' "$DEEPSEEK_KEY" > "$HAOCEAN_TEACHER_HOME/.env"
chmod 600 "$HAOCEAN_TEACHER_HOME/.env"
unset DEEPSEEK_KEY
```

说明：

- 教师端会读取 `$HAOCEAN_TEACHER_HOME/.env`。
- 教师端请求 AI 审阅和 hybrid 查重时，会把 key 通过 `X-DeepSeek-API-Key` 请求头传给 Module B。
- 如果你改用服务端统一 key，则写入 `$REPO_ROOT/module_b_server/.env` 的变量名是 `MODULE_B_DEEPSEEK_API_KEY` 或 `DEEPSEEK_API_KEY`，然后必须重启 Module B。

## 3. 验证线上服务

线上真实环境不需要你启动 `uvicorn`。先确认两个域名都可用：

```bash
source /tmp/haocean-report-demo/env.sh
curl "$TEACHER_URL/health"
curl "$STUDENT_URL/health"
```

正常情况下应看到 `code: 200`、`auth_required: true`。如果 `deepseek_configured: true`，AI 审阅和 hybrid 查重可直接使用服务端 key。

如果你临时改成本地备用模式，才需要开一个服务端终端：

```bash
source /tmp/haocean-report-demo/env.sh
export TEACHER_URL=http://127.0.0.1:8000
export STUDENT_URL=http://127.0.0.1:8000
export SERVER_URL="$TEACHER_URL"
cd "$REPO_ROOT/module_b_server"

MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 4. 老师登录、建班、发布作业

开老师端终端：

```bash
source /tmp/haocean-report-demo/env.sh

hteacher setup \
  --api-base-url "$TEACHER_URL" \
  --profile report-teacher \
  --teacher-id "$TEACHER_ID" \
  --name "Report Demo Teacher" \
  --email "$TEACHER_EMAIL"
```

登录：

```bash
hteacher login
```

如果提示选择 profile，输入 `report-teacher` 或对应序号。线上模式从邮箱收验证码；本地备用模式从服务端终端复制验证码。

创建班级：

```bash
hteacher classes create "$CLASS_NAME" \
  --course-title "$COURSE_TITLE" \
  --class-id "$CLASS_ID" \
  --join-code "$JOIN_CODE"
```

确认班级和加入码：

```bash
hteacher classes list
```

如果创建班级时报：

```text
class_id or join_code already exists
```

说明真实服务端里已经有这个班级或加入码。不要继续重复创建，先执行：

```bash
hteacher classes list
```

如果列表里能看到 `$CLASS_ID` 或 `$JOIN_CODE`，直接继续发布作业。如果列表里不是你要的演示班级，再换一组新的变量后重新建班，例如：

```bash
export CLASS_ID=linux_cli_report_class_20260610b
export JOIN_CODE=RPT610B
export ASSIGNMENT_ID=linux_cli_report_20260610b
```

发布带附件的作业：

```bash
hteacher assignment create "$ASSIGNMENT_ID" "$ASSIGNMENT_TITLE" \
  --class-id "$CLASS_ID" \
  --description "$ASSIGNMENT_DESC" \
  --deadline "2099-12-31 23:59:59" \
  --materials "$REPO_ROOT/docs/screenshot_demo_materials/linux_cli_submission_spec.md" \
  --weight 1.0
```

确认作业：

```bash
hteacher assignment list
```

如果创建作业时报 `assignment_id already exists`，先执行 `hteacher assignment list`。已经存在就继续学生端截图和提交；只有不是本次演示作业时才换新的 `ASSIGNMENT_ID`。

如果看到：

```text
argument --weight: invalid float value: '1.0hteacher'
```

这是命令被粘贴了两遍，`1.0` 和下一条 `hteacher` 粘在一起了。重新只粘贴一次上面的 `assignment create` 命令即可。

## 5. 学生 1 查看作业、下载附件并截图

开学生端终端：

```bash
source /tmp/haocean-report-demo/env.sh

hstudent setup \
  --profile report-s1 \
  --server-url "$STUDENT_URL" \
  --student-id "$STUDENT1_ID" \
  --name "Report Demo Student 1" \
  --email "$STUDENT1_EMAIL" \
  --class-code "$JOIN_CODE"
```

登录：

```bash
hstudent login
```

如果提示选择 profile，输入 `report-s1` 或对应序号。线上模式从邮箱收验证码；本地备用模式从服务端终端复制验证码。登录成功后会自动加入班级。

执行下面几条命令，然后截图。这张图用于展示“学生查看老师布置的作业及作业附件和要求”：

```bash
hstudent classes
hstudent list
hstudent materials "$ASSIGNMENT_ID"
find "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/materials" -maxdepth 2 -type f -print
cat "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/materials/linux_cli_submission_spec.md"
```

截图建议包含：

- `hstudent list` 中的作业编号、标题、班级、`materials=yes`。
- `hstudent materials` 的保存路径。
- `cat` 输出的作业要求和评分标准。

## 6. 学生 1 提交作业

继续在学生端终端执行：

```bash
mkdir -p "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID"
cp "$REPO_ROOT/docs/screenshot_demo_student_answer.md" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"

hstudent preview "$ASSIGNMENT_ID"
hstudent submit "$ASSIGNMENT_ID"
```

`preview` 应该能看到 `answer.md` 和 materials 文件。`submit` 成功后老师端就能看到一条 pending submission。

如果你在第 1 步修改过 `ASSIGNMENT_ID`，提交前也把 `answer.md` 里出现的默认作业编号 `linux_cli_report_20260610` 改成你的新作业编号。

## 7. 学生 2 提交相似作业，方便 AI 查重截图

这一步不是为了学生截图，而是为了让老师端 AI 查重报告更有内容。仍然使用学生端终端：

```bash
hstudent setup \
  --profile report-s2 \
  --server-url "$STUDENT_URL" \
  --student-id "$STUDENT2_ID" \
  --name "Report Demo Student 2" \
  --email "$STUDENT2_EMAIL" \
  --class-code "$JOIN_CODE"

hstudent login
```

如果提示选择 profile，输入 `report-s2` 或对应序号。

提交一份相似答案：

```bash
mkdir -p "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID"
cp "$REPO_ROOT/docs/screenshot_demo_student_answer.md" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"
printf '\n\n补充说明：这是第二名学生提交的相似版本，用于演示查重报告。\n' >> "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"

hstudent preview "$ASSIGNMENT_ID"
hstudent submit "$ASSIGNMENT_ID"
```

同样，如果你改过 `ASSIGNMENT_ID`，提交前先同步更新 `answer.md` 中的作业编号。

## 8. 老师端 TUI 截图

回到老师端终端：

```bash
source /tmp/haocean-report-demo/env.sh
hteacher tui "$ASSIGNMENT_ID"
```

TUI 常用按键：

```text
j / k     上下移动
p         待批改
a         已批改
l         全部提交
Enter     给当前提交评分
g         AI 审阅报告
c         AI 查重报告
s         当前学生历史得分
d         下载当前提交包
q         退出
```

建议按这个顺序截图：

1. TUI 主界面：进入后停留在 pending 列表，截图左侧提交列表和右侧详情。
2. AI 审阅报告：按 `g`，等待报告弹窗出现，确认有 `Source: deepseek deepseek-v4-flash` 后截图。按 `q` 或 `Enter` 关闭弹窗。
3. AI 查重报告：按 `c`，等待 hybrid 查重弹窗出现，截图 `Method: hybrid`、`Submissions`、`AI reviewed` 和 suspected pairs 或无疑似对说明。按 `q` 或 `Enter` 关闭弹窗。
4. 评分弹窗：按 `Enter`，在 `Score` 输入 `96`，按 `Tab` 到 `Comment`，输入：

```text
命令流程完整，能清楚说明 list、materials、preview 和 submit 的作用；文件组织清楚，提交前检查意识较好。
```

然后按 `Ctrl+s` 保存。

5. 学生历史得分：保存后按 `a` 切到已批改列表，选中学生 1 的提交，按 `s`，截图 `Student Score Stats` 弹窗。按 `q` 或 `Enter` 关闭。

如果你还想让统计结果更完整，可以用同样方式给学生 2 打分，例如 93 分。

## 9. 可直接复制进报告的输出

这些命令的输出适合直接作为报告文字材料，不一定需要截图：

```bash
hteacher plagiarism "$ASSIGNMENT_ID" --check --method hybrid --threshold 0.75
hteacher stats "$ASSIGNMENT_ID"
hteacher history "$STUDENT1_ID"
```

如果你要展示学生收到反馈，再切回学生 1：

```bash
hstudent login
# 选择 report-s1
hstudent feedback
find "$HAOCEAN_HOME/feedback_inbox" -type f -name '*feedback.md' -print
cat "$HAOCEAN_HOME/feedback_inbox/$ASSIGNMENT_ID"/submission_*_feedback.md
```

## 10. 截图插入建议

建议插入到 `report_new.md` 的位置：

- 学生查看作业和附件：放在“四、关键功能设计与实现 / 班级、作业材料和截止时间”附近。
- 教师 TUI 主界面和评分弹窗：放在“四、关键功能设计与实现 / 教师端批改和反馈”附近。
- AI 审阅报告：放在“四、关键功能设计与实现 / AI 审阅”附近。
- AI 查重报告：放在“四、关键功能设计与实现 / 查重”附近。
- 学生历史得分或统计输出：放在“互评和最终成绩”或“测试与验证”附近。
