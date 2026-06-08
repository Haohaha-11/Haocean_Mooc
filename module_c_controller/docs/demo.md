# 验收演示流程

## 1. 准备环境

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_mock_db.py
python scripts/run_controller.py
```

## 2. pending 视图浏览

启动后默认进入 pending 视图。使用 `j` / `k` 在待批改提交之间移动，确认右侧详情会随选中记录变化。

## 3. Enter 批改或重新评分

在 pending 视图选中一条提交后按 `Enter`，打开批改窗口。输入分数和评语。

HTTP 模式下，在 approved 或 all 视图中选中已批改提交后也可以按 `Enter` 重新评分。

## 4. Ctrl+s 提交

在批改窗口按 `Ctrl+s` 提交。提交成功后窗口关闭，当前记录会被标记为 approved，并生成反馈 Markdown 文件。

如需取消批改，按 `Esc` 返回列表。

## 5. approved 视图查看批改结果

按 `a` 切换到 approved 视图。选中刚刚批改的记录，确认右侧展示分数、评语、批改时间和反馈文件路径。

HTTP 模式下，按 `d` 可下载当前选中的提交包到 `~/.haocean-teacher/downloads/`。

## 6. all 视图查看全部记录

按 `l` 切换到 all 视图。确认列表中同时展示 pending 和 approved 记录，并能看到每条记录的状态。

## 7. 查看 feedback_outbox 反馈文件

退出 TUI 后查看生成的 Markdown 文件：

```bash
ls feedback_outbox
sed -n '1,160p' feedback_outbox/<feedback-file>.md
```

文件内容应包含提交信息、分数、评语和原始提交内容。
