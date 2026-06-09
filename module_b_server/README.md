# 模块 B：通信中枢与数据库

## 1. 模块定位

模块 B 是系统的服务端核心，负责：

1. 接收模块 C 发布的作业；
2. 向模块 A 返回开放作业列表；
3. 接收模块 A 上传的作业压缩包；
4. 重新计算 MD5，校验文件完整性；
5. 将提交记录写入 SQLite；
6. 向模块 C 提供待批改列表；
7. 接收模块 C 的批改结果；
8. 生成 Markdown 反馈文件；
9. 向模块 A 返回反馈内容；
10. 管理课程班级、学生加入码和班级范围内的开放作业；
11. 向教师端提供提交包下载、查重报告、成绩统计和课程归档。

---

## 2. 目录结构

```text
module_b_server/
├── app/
│   ├── main.py
│   ├── main_phase1_backup.py
│   └── main_phase2_backup.py
├── data/
│   ├── db/
│   │   └── engine.db
│   ├── tmp/
│   ├── submissions/
│   └── feedback/
├── scripts/
│   └── smoke_test.sh
├── requirements.txt
└── README.md
```

---

## 3. 扩展功能：班级、加入码与远程下载

模块 B 已支持教师创建班级、学生通过加入码入班、作业绑定班级。

### 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/classes` | 教师创建班级并生成加入码 |
| GET | `/v1/classes` | 教师查看自己创建的班级 |
| POST | `/v1/classes/join` | 学生通过加入码加入班级 |
| GET | `/v1/classes/my` | 学生查看自己已加入班级 |
| GET | `/v1/submissions?status=pending|graded|rejected|all` | 教师查看待批改、已批改或全部提交 |
| GET | `/v1/submissions/{submission_id}/download` | 教师下载提交包到本机 |

启用认证时，学生只会看到自己班级内的开放作业；如果作业绑定了班级，未加入该班级的学生不能提交。

同一老师名下 `class_name` 不可重复；`class_id` 和 `join_code` 仍是全局唯一。

### 登录邮箱验证码

模块 B 的登录验证码邮件兼容 new-api 的 SMTP 配置名：

```env
MODULE_B_SYSTEM_NAME=Haocean Mooc
SMTPServer=smtp.example.com
SMTPPort=587
SMTPSSLEnabled=false
SMTPForceAuthLogin=false
SMTPAccount=your-account@example.com
SMTPFrom=your-account@example.com
SMTPToken=your-smtp-token
```

如果 new-api 的 SMTP 配置放在环境文件里，可以让模块 B 启动前加载它：

```bash
MODULE_B_NEW_API_ENV_FILE=/Hao/new-api/.env \
MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=false \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

说明：

- 模块 B 优先使用自身环境变量；`MODULE_B_NEW_API_ENV_FILE` 只补充未设置的值。
- 已兼容 new-api 的 `SMTPForceAuthLogin`，以及 Outlook、SendCloud、Azure Communication 等需要 `AUTH LOGIN` 的服务。
- 本地联调若暂时不想发邮件，可保留 `MODULE_B_DEV_VERIFICATION_LOG=true`，验证码会打印到服务端日志。

---

## 4. 扩展功能：互评与最终成绩计算

模块 B 已支持期末大作业互评功能。互评开关建议在创建作业时决定：`POST /v1/assignments` 可同时传 `peer_review_enabled`、`teacher_weight` 和 `peer_weight`。开启后作业先处于提交阶段，提交结束后再切到互评阶段并分配任务。

### 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/assignments` | 创建作业，并可决定是否开启互评 |
| POST | `/v1/assignments/{assignment_id}/materials` | 上传或替换作业说明文件/附件包 |
| GET | `/v1/assignments/{assignment_id}/materials` | 查询作业资料包元数据 |
| GET | `/v1/assignments/{assignment_id}/materials/download` | 下载作业资料包 |
| POST | `/v1/assignments/peer-review/config` | 兼容入口；补配或调整已有作业互评权重 |
| POST | `/v1/assignments/{assignment_id}/peer-review/stage` | 切换提交、互评、最终计算等阶段 |
| POST | `/v1/assignments/{assignment_id}/peer-review/tasks/auto` | 自动分配互评任务 |
| GET | `/v1/peer-review/tasks/my` | 学生查看自己的互评任务 |
| POST | `/v1/peer-reviews` | 学生提交互评分 |
| POST | `/v1/assignments/{assignment_id}/calculate-final-scores` | 计算最终成绩 |
| GET | `/v1/assignments/{assignment_id}/final-scores` | 查看最终成绩 |

自动分配互评任务时，默认每个学生互评 2 份作业；如果只有 2 个学生，则相互评 1 份；只有 1 个学生无法分配互评任务。

### 评分规则

```text
基础分 = 老师评分 × teacher_weight + 学生互评平均分 × peer_weight
最终分 = 基础分 + 互评准确奖励分
最终分最高不超过 100 分
```

互评奖励规则：

| 与老师评分差距 | 奖励 |
|---|---|
| ≤ 5 分 | +1 |
| > 5 分 | +0 |

同一学生在同一作业内即使命中多个接近条件，互评准确奖励也最多为 `+1`。

### 功能验证结果

当前已完成测试：

1. 发布作业时开启互评；
2. 提交结束后切换到互评阶段；
3. 两名学生提交作业；
4. 老师分别评分；
5. 自动分配任务并由学生互评；
6. 系统计算 `peer_avg_score`、`peer_bonus`、`final_score`；
7. 最终成绩查询接口返回正常。

---

## 5. 扩展功能：课程归档与打包下载

模块 B 已支持课程结束后的归档打包下载功能。

### 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/archives/course` | 生成课程归档 zip 包 |
| GET | `/v1/archives` | 查看已生成的归档包 |
| GET | `/v1/archives/download/{archive_name}` | 下载指定归档包 |

### 归档内容

归档包面向教师下载，导出的是作业文件集合（而非服务器运行目录备份）：

```text
assignment_<assignment_id>_homework_files/   单作业导出目录（扁平）
assignment_all_homework_files/               多作业导出目录（扁平）
```

导出命名规则：

```text
{assignment_id}_{student_id}_{submission_id}_{original_filename}
```

过滤规则：

- 排除：`__pycache__/`、`.git/`、`.venv/`、`node_modules/`、`.DS_Store`、`Thumbs.db`、`*.pyc`、`*.log`、`*.tmp`、`*.db`、`*.sqlite`、`*.zip`、`*.tar`、`*.gz`
- 保留：`.py`、`.c`、`.cpp`、`.h`、`.java`、`.js`、`.html`、`.css`、`.md`、`.txt`、`.pdf`、`.docx`、`.xlsx`、`.ipynb`、`.png`、`.jpg`、`.jpeg`

### 生成归档包示例

```bash
ARCHIVE_NAME="course_archive_$(date +%s).zip"

curl -X POST http://127.0.0.1:8000/v1/archives/course \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"CREATE_COURSE_ARCHIVE\",
    \"timestamp\": $(date +%s),
    \"payload\": {
      \"archive_name\": \"${ARCHIVE_NAME}\",
      \"note\": \"课程结束归档\",
      \"include_db\": false,
      \"include_submissions\": true,
      \"include_feedback\": false,
      \"include_docs\": false
    }
  }"
```

### 下载归档包示例

```bash
curl -L -o /tmp/downloaded_course_archive.zip \
  http://127.0.0.1:8000/v1/archives/download/${ARCHIVE_NAME}
```

### 查看压缩包内容

```bash
unzip -l /tmp/downloaded_course_archive.zip | head -50
```

当前已验证：

1. 归档包可以成功生成；
2. `data/archives` 下可以看到 zip 文件；
3. 下载接口可以正常下载；
4. zip 包内容可以正常查看。

---

## 6. 模块 B 当前完成情况

模块 B 当前已完成：

1. 作业发布；
2. 开放作业查询；
3. 作业提交；
4. MD5 校验；
5. 文件归档；
6. SQLite 入库；
7. 待批改列表；
8. 教师批改；
9. 反馈 Markdown 生成；
10. 学生反馈查询；
11. 学生互评；
12. 最终成绩计算；
13. 课程归档；
14. 归档包下载；
15. 班级/加入码/学生选课；
16. 班级作业可见性控制；
17. 教师远程下载提交包；
18. 查重与成绩统计接口。

详细接口文档见：

```text
/Hao/gongchuang/docs/api_spec.md
```
---

## 6. 扩展功能：查重检测

模块 B 已支持作业查重功能。

### 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/plagiarism/check` | 对某个作业进行查重 |
| GET | `/v1/plagiarism/reports/{assignment_id}` | 查询某个作业的查重报告 |

### 当前查重方式

当前支持三种查重方式：

- `token`：只做本地 token 查重，不调用外部模型。
- `hybrid`：先做本地 token 预筛，再把高风险提交对交给 DeepSeek 复核，推荐日常使用。
- `ai`：同样先按本地分数排序和限流，再使用 DeepSeek 复核；如需全量两两 AI 复核，可把 `ai_prefilter` 设为 `0` 并调大 `ai_limit`。

处理流程：

1. 读取学生提交压缩包中的文本/代码文件；
2. 候选范围包含当前作业内同期提交，以及当前作业提交与最近三年历史提交的交叉比较；
3. 同一个学生自己的多次提交不互相判为疑似；
4. 转成小写；
5. 过滤数字、下划线、标点；
6. 只保留中文和英文 token；
7. 计算 token 集合相似度；
8. `token` 模式下，相似度超过阈值则记录为疑似重复；
9. `hybrid` / `ai` 模式下，只把本地预筛命中的候选对发给 DeepSeek，返回 AI 相似度、判断理由和证据点。

DeepSeek 可以由老师端随请求提供，也可以由运行 Module B 的服务器统一配置。老师端会通过 `X-DeepSeek-API-Key` 请求头传入自己的 key；如果请求头没有 key，Module B 会读取服务器环境变量。仓库运行方式下可以写入 `module_b_server/.env`，或者写入 systemd/Docker/云平台的服务进程环境变量：

```env
MODULE_B_DEEPSEEK_API_KEY=your-deepseek-key
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_PREFILTER_SIMILARITY=0.45
DEEPSEEK_MAX_CANDIDATE_PAIRS=12
DEEPSEEK_MAX_CHARS_PER_SUBMISSION=8000
DEEPSEEK_TIMEOUT_SECONDS=30
```

`DEEPSEEK_API_KEY` 也兼容；如果两个变量都设置，服务端优先读取 `DEEPSEEK_API_KEY`。修改后必须重启 Module B，可通过 `/v1/health` 的 `deepseek_configured` 字段确认是否生效。

默认使用 `deepseek-v4-flash` 并关闭 V4 thinking 模式，优先保证批量查重速度和成本可控。

### 查重命令示例

```bash
ASSIGNMENT_ID="home_1"

curl -X POST http://127.0.0.1:8000/v1/plagiarism/check \
  -H "Content-Type: application/json" \
  -d "{
    \"action\": \"CHECK_PLAGIARISM\",
    \"timestamp\": $(date +%s),
    \"payload\": {
      \"assignment_id\": \"${ASSIGNMENT_ID}\",
      \"threshold\": 0.75,
      \"method\": \"hybrid\",
      \"ai_prefilter\": 0.45,
      \"ai_limit\": 12
    }
  }"
```

### 查询报告示例

```bash
curl http://127.0.0.1:8000/v1/plagiarism/reports/${ASSIGNMENT_ID}
```

### 图形化界面对接

图形化界面不需要直接访问数据库，只需要调用模块 B 的 HTTP 接口：

```text
POST /v1/plagiarism/check
GET  /v1/plagiarism/reports/{assignment_id}
```

教师端可以增加“查重”按钮，点击后调用 `/v1/plagiarism/check`，并展示 `suspected_pairs`。
