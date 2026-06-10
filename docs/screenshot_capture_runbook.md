# 真实环境模拟截图教程

本文档用于模拟一个“从 GitHub 拉代码、安装 CLI、连接线上服务、真实邮箱验证码登录”的演示环境。主流程只使用线上真实服务：

- 教师端服务：`https://teacher.haoceanlab.cn`
- 学生端服务：`https://student.haoceanlab.cn`
- 不启动本地 `uvicorn`
- 不使用开发验证码
- 不使用 `/Hao/gongchuang/module_*/.venv`
- 所有学生端、教师端配置都写入 `/tmp` 下的临时目录

目标截图：

1. 学生查看老师发布的作业、附件和要求。
2. 老师端 TUI 主界面。
3. 老师端 TUI 查看学生历史得分。
4. 老师端 TUI 查看 AI 查重报告。
5. 老师端 TUI 查看 AI 审阅报告。

## 0. 现场原则

- 不要把真实 DeepSeek key、邮箱验证码、token 截进图里。
- 每次演示都用新的 `DEMO_ROOT`，避免旧 token、旧班级、旧作业干扰。
- `class_id`、`join_code`、`assignment_id` 使用时间戳自动生成，避免撞到线上数据库里已经存在的记录。
- 多行命令一次只粘贴一份。如果出现 `1.0haocean-teacher` 或 `1.0hteacher`，说明两份命令粘到一起了。

## 1. 从 GitHub 拉代码并安装 CLI

开一个新终端，执行：

```bash
export DEMO_ROOT=/tmp/haocean-real-demo-$(date +%Y%m%d%H%M%S)
mkdir -p "$DEMO_ROOT"
cd "$DEMO_ROOT"

git clone https://github.com/Haohaha-11/Haocean_Mooc.git
cd Haocean_Mooc

export HAOCEAN_HOME="$DEMO_ROOT/student-home"
export HAOCEAN_TEACHER_HOME="$DEMO_ROOT/teacher-home"
export HAOCEAN_INSTALL_DIR="$DEMO_ROOT/student-cli"
export HAOCEAN_TEACHER_INSTALL_DIR="$DEMO_ROOT/teacher-cli"
export HAOCEAN_BIN_DIR="$DEMO_ROOT/bin"

bash install-all.sh
export PATH="$HAOCEAN_BIN_DIR:$PATH"
```

确认是 GitHub 最新代码，并且命令可用：

```bash
git log -1 --oneline
haocean-student --help
haocean-teacher --help
```

## 2. 写入演示环境变量

继续在同一个终端执行：

```bash
export REPO_ROOT="$DEMO_ROOT/Haocean_Mooc"
export DEMO_SUFFIX=$(date +%Y%m%d%H%M%S)

cat > "$DEMO_ROOT/env.sh" <<EOF
export DEMO_ROOT="$DEMO_ROOT"
export REPO_ROOT="$REPO_ROOT"
export PATH="$HAOCEAN_BIN_DIR:\$PATH"
export HAOCEAN_HOME="$HAOCEAN_HOME"
export HAOCEAN_TEACHER_HOME="$HAOCEAN_TEACHER_HOME"

export TEACHER_URL=https://teacher.haoceanlab.cn
export STUDENT_URL=https://student.haoceanlab.cn
export CONTROLLER_REQUEST_TIMEOUT_SECONDS=60
export MODULE_A_REQUEST_TIMEOUT_SECONDS=60

export DEMO_SUFFIX="$DEMO_SUFFIX"
export CLASS_ID="real_demo_class_$DEMO_SUFFIX"
export CLASS_NAME="Real Demo Class $DEMO_SUFFIX"
export COURSE_TITLE="Linux CLI Course"
export JOIN_CODE="RPT$DEMO_SUFFIX"

export ASSIGNMENT_ID="linux_cli_report_$DEMO_SUFFIX"
export ASSIGNMENT_TITLE="Linux 命令行作业流程报告"
export ASSIGNMENT_DESC="请提交一份 Markdown 文档，说明你如何在 Linux 终端中查看作业、下载附件、预览提交包并完成提交。"

export TEACHER_ID="T_REAL_$DEMO_SUFFIX"
export TEACHER_EMAIL="your-teacher-email@example.com"
export STUDENT1_ID="S1_$DEMO_SUFFIX"
export STUDENT1_EMAIL="your-student1-email@example.com"
export STUDENT2_ID="S2_$DEMO_SUFFIX"
export STUDENT2_EMAIL="your-student2-email@example.com"
EOF

source "$DEMO_ROOT/env.sh"
```

把三个邮箱改成你能收验证码的真实邮箱：

```bash
nano "$DEMO_ROOT/env.sh"
source "$DEMO_ROOT/env.sh"
```

可以临时用同一个邮箱接收三个身份的验证码，但每次登录都要使用最新邮件里的验证码。更稳妥的做法是至少让学生 2 使用另一个可收码邮箱。

后面每开一个新终端，都先执行：

```bash
source /tmp/haocean-real-demo-具体时间戳/env.sh
```

实际路径就是第 1 步生成的 `$DEMO_ROOT`。

## 3. 检查线上服务和 DNS

执行：

```bash
getent hosts teacher.haoceanlab.cn
getent hosts student.haoceanlab.cn
curl "$TEACHER_URL/health"
curl "$STUDENT_URL/health"
```

正常应看到：

- 域名能解析到服务器 IP。
- `/health` 返回 `code: 200`。
- `auth_required: true`。
- `smtp_configured: true`。
- 如果 `deepseek_configured: true`，AI 审阅和 hybrid 查重可直接使用服务端 key。

如果出现：

```text
Failed to resolve 'teacher.haoceanlab.cn'
```

这是当前机器 DNS 解析问题，不是业务失败。演示前固定 hosts：

```bash
echo '43.247.134.254 teacher.haoceanlab.cn student.haoceanlab.cn' >> /etc/hosts
getent hosts teacher.haoceanlab.cn
getent hosts student.haoceanlab.cn
```

如果不是 root 用户，用：

```bash
printf '%s\n' '43.247.134.254 teacher.haoceanlab.cn student.haoceanlab.cn' | sudo tee -a /etc/hosts
```

## 4. 如果需要配置 DeepSeek key

如果 `/health` 已经显示 `deepseek_configured: true`，跳过本节。

如果线上服务没有配置 DeepSeek，但你需要真实 AI 审阅和 AI 查重，在老师端临时 HOME 写入 key：

```bash
source "$DEMO_ROOT/env.sh"
mkdir -p "$HAOCEAN_TEACHER_HOME"
chmod 700 "$HAOCEAN_TEACHER_HOME"

read -s -p "Paste DeepSeek key: " DEEPSEEK_KEY
printf '\n'
printf 'MODULE_C_DEEPSEEK_API_KEY=%s\nDEEPSEEK_MODEL=deepseek-v4-flash\n' "$DEEPSEEK_KEY" > "$HAOCEAN_TEACHER_HOME/.env"
chmod 600 "$HAOCEAN_TEACHER_HOME/.env"
unset DEEPSEEK_KEY
```

不要把 `.env` 内容复制进报告、截图或聊天记录。

## 5. 老师登录、建班、发布作业

```bash
source "$DEMO_ROOT/env.sh"

haocean-teacher setup \
  --api-base-url "$TEACHER_URL" \
  --profile real-teacher \
  --teacher-id "$TEACHER_ID" \
  --name "Real Demo Teacher" \
  --email "$TEACHER_EMAIL"
```

登录：

```bash
haocean-teacher login
```

选择 `real-teacher`，从邮箱复制最新验证码。登录成功后创建班级：

```bash
haocean-teacher classes create "$CLASS_NAME" \
  --course-title "$COURSE_TITLE" \
  --class-id "$CLASS_ID" \
  --join-code "$JOIN_CODE"
```

确认班级：

```bash
haocean-teacher classes list
```

发布带附件的作业：

```bash
haocean-teacher assignment create "$ASSIGNMENT_ID" "$ASSIGNMENT_TITLE" \
  --class-id "$CLASS_ID" \
  --description "$ASSIGNMENT_DESC" \
  --deadline "2099-12-31 23:59:59" \
  --materials "$REPO_ROOT/docs/screenshot_demo_materials/linux_cli_submission_spec.md" \
  --weight 1.0
```

确认作业：

```bash
haocean-teacher assignment list
```

如果仍然遇到 `class_id or join_code already exists` 或 `assignment_id already exists`，说明你复用了旧的 `DEMO_ROOT/env.sh`。重新从第 1 步开始生成新的 `DEMO_ROOT`。

## 6. 学生 1 查看作业和附件

开学生终端，先 source 环境：

```bash
source /tmp/haocean-real-demo-具体时间戳/env.sh
```

配置学生 1：

```bash
haocean-student setup \
  --profile real-s1 \
  --server-url "$STUDENT_URL" \
  --student-id "$STUDENT1_ID" \
  --name "Real Demo Student 1" \
  --email "$STUDENT1_EMAIL" \
  --class-code "$JOIN_CODE"
```

登录：

```bash
haocean-student login
```

选择 `real-s1`，从邮箱复制最新验证码。登录成功后会自动加入班级。

执行下面命令并截图，用于展示“学生查看老师布置的作业、附件和要求”：

```bash
haocean-student classes
haocean-student list
haocean-student materials "$ASSIGNMENT_ID"
find "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/materials" -maxdepth 2 -type f -print
cat "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/materials/linux_cli_submission_spec.md"
```

截图建议包含：

- `haocean-student list` 里的作业编号、标题、班级、`materials=yes`。
- `haocean-student materials` 的保存路径。
- `cat` 输出的作业要求和评分标准。

## 7. 学生 1 提交作业

继续在学生终端执行：

```bash
mkdir -p "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID"
cp "$REPO_ROOT/docs/screenshot_demo_student_answer.md" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"
sed -i "s/linux_cli_report_20260610/$ASSIGNMENT_ID/g" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"

haocean-student preview "$ASSIGNMENT_ID"
haocean-student submit "$ASSIGNMENT_ID"
```

`preview` 应该能看到 `answer.md` 和 materials 文件。`submit` 成功后，老师端就能看到学生 1 的 pending submission。

## 8. 学生 2 提交相似作业

学生 2 用于让 AI 查重报告更有内容。仍在学生终端执行：

```bash
source "$DEMO_ROOT/env.sh"

haocean-student setup \
  --profile real-s2 \
  --server-url "$STUDENT_URL" \
  --student-id "$STUDENT2_ID" \
  --name "Real Demo Student 2" \
  --email "$STUDENT2_EMAIL" \
  --class-code "$JOIN_CODE"

haocean-student login
```

选择 `real-s2`，从邮箱复制最新验证码。然后提交一份相似答案：

```bash
mkdir -p "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID"
cp "$REPO_ROOT/docs/screenshot_demo_student_answer.md" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"
sed -i "s/linux_cli_report_20260610/$ASSIGNMENT_ID/g" "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"
printf '\n\n补充说明：这是第二名学生提交的相似版本，用于演示查重报告。\n' >> "$HAOCEAN_HOME/workspace/$ASSIGNMENT_ID/answer.md"

haocean-student preview "$ASSIGNMENT_ID"
haocean-student submit "$ASSIGNMENT_ID"
```

## 9. 老师端 TUI 截图

回到老师终端：

```bash
source "$DEMO_ROOT/env.sh"
haocean-teacher tui "$ASSIGNMENT_ID"
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

建议截图顺序：

1. TUI 主界面：进入后停在 pending 列表，截图左侧提交列表和右侧详情。
2. AI 审阅报告：按 `g`，等待弹窗出现，确认有 `Source: deepseek` 后截图。
3. AI 查重报告：按 `c`，等待 hybrid 查重弹窗出现，截图 `Method: hybrid`、`Submissions`、`AI reviewed` 和 suspected pairs。
4. 评分弹窗：按 `Enter`，`Score` 输入 `96`，`Comment` 输入：

```text
命令流程完整，能清楚说明 list、materials、preview 和 submit 的作用；文件组织清楚，提交前检查意识较好。
```

然后按 `Ctrl+s` 保存。

5. 学生历史得分：按 `a` 切到已批改列表，选中学生 1，按 `s`，截图 `Student Score Stats` 弹窗。

如果还需要给学生 2 打分，可以同样输入 93 分，这样统计更完整。

## 10. 可复制进报告的真实输出

这些命令适合直接复制到报告，不一定都要截图：

```bash
source "$DEMO_ROOT/env.sh"

haocean-teacher plagiarism "$ASSIGNMENT_ID" --check --method hybrid --threshold 0.75
haocean-teacher stats "$ASSIGNMENT_ID"
haocean-teacher history "$STUDENT1_ID"
```

学生 1 拉取反馈：

```bash
source "$DEMO_ROOT/env.sh"
haocean-student login
# 选择 real-s1
haocean-student feedback
find "$HAOCEAN_HOME/feedback_inbox" -type f -name '*feedback.md' -print
cat "$HAOCEAN_HOME/feedback_inbox/$ASSIGNMENT_ID"/submission_*_feedback.md
```

## 11. 常见问题

### DNS 失败

报错：

```text
Failed to resolve 'teacher.haoceanlab.cn'
```

处理：

```bash
echo '43.247.134.254 teacher.haoceanlab.cn student.haoceanlab.cn' >> /etc/hosts
getent hosts teacher.haoceanlab.cn
```

### 发验证码超时

如果看到 `Read timed out (read timeout=10.0)`，说明当前使用的 CLI 不是最新代码，或者没有 source 新的 `env.sh`。确认：

```bash
source "$DEMO_ROOT/env.sh"
echo "$CONTROLLER_REQUEST_TIMEOUT_SECONDS"
echo "$MODULE_A_REQUEST_TIMEOUT_SECONDS"
git -C "$REPO_ROOT" log -1 --oneline
```

最新代码默认已经是 60 秒超时。

### 班级或作业已存在

报错：

```text
class_id or join_code already exists
assignment_id already exists
```

处理：不要反复执行同一条创建命令。重新从第 1 步开始，用新的 `DEMO_ROOT` 生成新的时间戳。

### `--weight` 参数变成奇怪字符串

报错：

```text
argument --weight: invalid float value: '1.0haocean-teacher'
```

或：

```text
argument --weight: invalid float value: '1.0hteacher'
```

处理：你把两份多行命令粘贴到一起了。重新只粘贴一次 `assignment create` 命令。

## 12. 截图插入位置

- 学生查看作业和附件：放在“班级、作业材料和截止时间”附近。
- 教师 TUI 主界面和评分弹窗：放在“教师端批改和反馈”附近。
- AI 审阅报告：放在“AI 审阅”附近。
- AI 查重报告：放在“查重”附近。
- 学生历史得分或统计输出：放在“互评和最终成绩”或“测试与验证”附近。
