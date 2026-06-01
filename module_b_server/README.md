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
| GET | `/v1/submissions/{submission_id}/download` | 教师下载提交包到本机 |

启用认证时，学生只会看到自己班级内的开放作业；如果作业绑定了班级，未加入该班级的学生不能提交。

---

## 4. 扩展功能：互评与最终成绩计算

模块 B 已支持期末大作业互评功能。

### 已实现接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/assignments/peer-review/config` | 配置某个作业是否开启互评 |
| POST | `/v1/peer-reviews` | 学生提交互评分 |
| POST | `/v1/assignments/{assignment_id}/calculate-final-scores` | 计算最终成绩 |
| GET | `/v1/assignments/{assignment_id}/final-scores` | 查看最终成绩 |

### 评分规则

```text
基础分 = 老师评分 × teacher_weight + 学生互评平均分 × peer_weight
最终分 = 基础分 + 互评准确奖励分
最终分最高不超过 100 分
```

互评奖励规则：

| 与老师评分差距 | 奖励 |
|---|---|
| ≤ 5 分 | +5 |
| ≤ 10 分 | +3 |
| ≤ 15 分 | +1 |
| > 15 分 | +0 |

### 功能验证结果

当前已完成测试：

1. 创建互评作业；
2. 开启互评；
3. 两名学生提交作业；
4. 老师分别评分；
5. 学生互评；
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

归档包中可以包含：

```text
database/engine.db        SQLite 数据库备份
submissions/              学生提交文件
feedback/                 教师反馈 Markdown
docs/                     项目文档
README.md                 模块 B 使用说明
```

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
      \"include_db\": true,
      \"include_submissions\": true,
      \"include_feedback\": true,
      \"include_docs\": true
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
