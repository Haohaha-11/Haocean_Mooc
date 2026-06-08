# Domain, Login, and Smoke Test Guide

## DNS

Create these DNS records at the DNS provider for `haoceanlab.cn`:

```text
student.haoceanlab.cn  A  <server public IPv4>
teacher.haoceanlab.cn  A  <server public IPv4>
```

Both names can point to the same Module B service. The role separation is handled by
the client login role and token.

## Caddy Reverse Proxy

Add both hostnames to the server Caddyfile:

```caddyfile
student.haoceanlab.cn {
    reverse_proxy 127.0.0.1:8000
}

teacher.haoceanlab.cn {
    reverse_proxy 127.0.0.1:8000
}
```

Reload Caddy after editing:

```bash
sudo systemctl reload caddy
```

## Module B Server

Start Module B with auth enabled. Use the same SMTP environment variable names as
`/Hao/new-api`:

```bash
cd /Hao/gongchuang/module_b_server

MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=false \
MODULE_B_SYSTEM_NAME='Haocean Mooc' \
SMTPServer=smtp.example.com \
SMTPPort=587 \
SMTPAccount=no-reply@example.com \
SMTPFrom=no-reply@example.com \
SMTPToken='your-smtp-token' \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For local testing without SMTP, use:

```bash
MODULE_B_AUTH_REQUIRED=true \
MODULE_B_DEV_VERIFICATION_LOG=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In dev-log mode the verification code is printed in the Module B terminal and also
returned in the API payload.

## Student Client

```bash
cd /Hao/gongchuang/module_a_client

MODULE_A_SERVER_URL=https://student.haoceanlab.cn \
MODULE_A_EMAIL=student@example.com \
MODULE_A_STUDENT_ID=2024001 \
MODULE_A_ASSIGNMENT_ID=home_001 \
python3 scripts/run_client.py list
```

The first run asks for the email verification code and saves the token to
`data/auth_token`.

Submit only one assignment:

```bash
mkdir -p workspace/home_001
printf 'hello from student\n' > workspace/home_001/answer.txt

MODULE_A_SERVER_URL=https://student.haoceanlab.cn \
MODULE_A_EMAIL=student@example.com \
MODULE_A_STUDENT_ID=2024001 \
MODULE_A_ASSIGNMENT_ID=home_001 \
python3 scripts/run_client.py once
```

Fetch feedback:

```bash
MODULE_A_SERVER_URL=https://student.haoceanlab.cn \
MODULE_A_EMAIL=student@example.com \
MODULE_A_STUDENT_ID=2024001 \
MODULE_A_ASSIGNMENT_ID=home_001 \
python3 scripts/run_client.py feedback
```

## Teacher Client

```bash
cd /Hao/gongchuang/module_c_controller

CONTROLLER_SOURCE=http \
CONTROLLER_API_BASE_URL=https://teacher.haoceanlab.cn \
CONTROLLER_EMAIL=teacher@example.com \
CONTROLLER_TEACHER_ID=T001 \
.venv/bin/python scripts/run_controller.py
```

The first run asks for the email verification code and saves the token to
`data/auth_token`.

TUI keys:

```text
p        pending submissions
Enter    review selected submission
Ctrl+s   submit score and comment
a        approved view
q        quit
```

## Create an Assignment

For now, create the assignment through Module B with a teacher token, or use local
dev mode before enabling public testing:

```bash
curl -X POST https://teacher.haoceanlab.cn/v1/assignments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <teacher-token>" \
  -d '{"action":"CREATE_ASSIGNMENT","timestamp":1,"payload":{"teacher_id":"T001","assignment_id":"home_001","title":"本地测试作业","description":"提交任意文件","deadline":"2026-06-30 23:59:59"}}'
```

## Important

Use `MODULE_A_ASSIGNMENT_ID=home_001` during testing. Without it, the student client
scans every open assignment returned by Module B.
