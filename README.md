# Haocean MOOC CLI

Haocean MOOC CLI is a Linux-terminal coursework platform with separate student and teacher commands.

- Student command: `haocean`
- Teacher command: `haocean-teacher`
- Student HTTPS entry: `https://student.haoceanlab.cn`
- Teacher HTTPS entry: `https://teacher.haoceanlab.cn`

## Student Install

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-student.sh | bash
```

Then configure and log in:

```bash
haocean setup --student-id 2024001 --email student@example.com --class-code JOIN101
haocean login
```

Common commands:

```bash
haocean list
haocean submit home_001
haocean feedback
```

Student files are stored locally under:

```text
~/.haocean/
```

## Teacher Install

```bash
curl -fsSL https://raw.githubusercontent.com/Haohaha-11/Haocean_Mooc/main/install-teacher.sh | bash
```

Then configure and log in:

```bash
haocean-teacher setup --teacher-id T001 --email teacher@example.com
haocean-teacher login
```

Common commands:

```bash
haocean-teacher classes create "CS101 Spring" --class-id cs101
haocean-teacher assignment create home_001 "Homework 1" --class-id cs101
haocean-teacher tui
haocean-teacher plagiarism home_001
haocean-teacher stats home_001
haocean-teacher archive create --name course_archive.zip
```

Teacher files are stored locally under:

```text
~/.haocean-teacher/
```

## System Requirements

- Linux terminal
- Python 3.10+
- `python3-venv`
- Network access to GitHub and the Haocean HTTPS service

On Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## Repository Layout

```text
module_a_client/       Student CLI package
module_b_server/       FastAPI backend service
module_c_controller/   Teacher CLI package
docs/                  API and operation docs
install-student.sh     Student one-line installer
install-teacher.sh     Teacher one-line installer
```

## Security

Do not commit runtime data or secrets:

- `.env`
- SMTP credentials
- SQLite runtime databases
- student submissions
- feedback files
- logs
- virtual environments
