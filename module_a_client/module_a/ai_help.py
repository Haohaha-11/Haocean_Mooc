from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
import urllib.error
import urllib.request

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(path: object, *_args: object, **_kwargs: object) -> bool:
        env_path = Path(path)
        if not env_path.exists():
            return False
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return True


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"


SYSTEM_PROMPT = """\
你是 Haocean Mooc CLI 的使用小助手，只回答这个 Linux 命令行应用的使用问题。

产品和命令：
- 学生端正式命令是 haocean-student，配置目录是 ~/.haocean/。
- 学生端支持本地多 profile：setup --profile <name>、profiles、login 选择身份。
- 教师端正式命令是 haocean-teacher，配置目录是 ~/.haocean-teacher/。
- haocean ai-help 是本机帮助入口，只使用用户本机配置的 DeepSeek key，不调用 Haocean 服务端。
- 学生 HTTPS 服务入口是 https://student.haoceanlab.cn。
- 教师 HTTPS 服务入口是 https://teacher.haoceanlab.cn。

学生常用流程：
1. haocean-student setup
2. haocean-student login
3. haocean-student profiles
4. haocean-student join JOIN101
5. haocean-student classes
6. haocean-student list
7. 如果有资料包，haocean-student materials <assignment_id>
8. 把作业放进 ~/.haocean/workspace/<assignment_id>/
9. haocean-student preview <assignment_id>
10. haocean-student submit <assignment_id>
11. haocean-student feedback
12. haocean-student guide 查看本机学生指南

教师常用流程：
1. haocean-teacher setup
2. haocean-teacher login
3. haocean-teacher class
4. haocean-teacher select
5. haocean-teacher publish，可以用 --materials 上传作业说明文件或附件目录
6. haocean-teacher grade 或 haocean-teacher tui
7. haocean-teacher download <submission_id> --extract
8. haocean-teacher plagiarism <assignment_id> --check --method hybrid
9. haocean-teacher stats <assignment_id>
10. haocean-teacher archive create --name course_archive.zip
11. haocean-teacher guide 查看本机教师指南

规则：
- 优先给出可直接复制执行的命令。
- 不要要求用户登录服务器。
- 不要编造不存在的子命令。
- 不要建议 module_a_client/.venv 或 module_c_controller/.venv 这种开发环境命令。
- 如果问题不属于 Haocean Mooc CLI 使用范围，简短说明你只能回答本应用使用问题。
"""


LOCAL_HELP = """\
Haocean Mooc CLI 本地帮助

学生端：
  haocean-student setup
  haocean-student login
  haocean-student profiles
  haocean-student join JOIN101
  haocean-student classes
  haocean-student list
  haocean-student materials home_001
  haocean-student submit home_001
  haocean-student feedback
  haocean-student guide

学生提交作业：
  1. 查看作业：haocean-student list
  2. 有资料包时先下载：haocean-student materials <assignment_id>
  3. 把文件放到 ~/.haocean/workspace/<assignment_id>/
  4. 先预览：haocean-student preview <assignment_id>
  5. 提交：haocean-student submit <assignment_id>
  6. 查看反馈：haocean-student feedback

教师端：
  haocean-teacher setup
  haocean-teacher login
  haocean-teacher class
  haocean-teacher select
  haocean-teacher publish
  haocean-teacher publish home_001 "Homework 1" --materials ./home_001_spec.pdf
  haocean-teacher grade
  haocean-teacher download <submission_id> --extract
  haocean-teacher plagiarism <assignment_id> --check --method hybrid
  haocean-teacher stats <assignment_id>
  haocean-teacher guide

AI 帮助：
  # 只读取你本机的环境变量或 ~/.haocean/ai.env，不调用 Haocean 服务端测试 AI
  export HAOCEAN_DEEPSEEK_API_KEY=你的新 DeepSeek key
  haocean ai-help
  haocean ai-help "怎么提交作业？"
"""


class AIHelpError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIHelpConfig:
    api_key: str
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    model: str = DEFAULT_DEEPSEEK_MODEL
    timeout_seconds: float = 30.0
    max_tokens: int = 900


UrlOpen = Callable[..., Any]


def _env_value(env: Mapping[str, str], *names: str) -> str:
    for name in names:
        value = env.get(name)
        if value:
            return value.strip()
    return ""


def _float_env(env: Mapping[str, str], name: str, default: float) -> float:
    value = env.get(name, "").strip()
    try:
        return float(value) if value else default
    except ValueError:
        return default


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    value = env.get(name, "").strip()
    try:
        return int(value) if value else default
    except ValueError:
        return default


def load_user_ai_help_env() -> None:
    custom_env_file = os.getenv("HAOCEAN_AI_ENV_FILE", "").strip()
    candidates = []
    if custom_env_file:
        candidates.append(Path(custom_env_file).expanduser())
    candidates.extend(
        [
            Path("~/.haocean/ai.env").expanduser(),
            Path("~/.haocean/.env").expanduser(),
        ]
    )
    for env_file in candidates:
        load_dotenv(env_file, override=False)


def load_ai_help_config(env: Mapping[str, str] | None = None) -> AIHelpConfig:
    if env is None:
        load_user_ai_help_env()
    source = os.environ if env is None else env
    return AIHelpConfig(
        api_key=_env_value(source, "DEEPSEEK_API_KEY", "HAOCEAN_DEEPSEEK_API_KEY"),
        base_url=(
            _env_value(source, "DEEPSEEK_BASE_URL", "HAOCEAN_DEEPSEEK_BASE_URL")
            or DEFAULT_DEEPSEEK_BASE_URL
        ).rstrip("/"),
        model=(
            _env_value(source, "DEEPSEEK_MODEL", "HAOCEAN_DEEPSEEK_MODEL")
            or DEFAULT_DEEPSEEK_MODEL
        ),
        timeout_seconds=_float_env(source, "DEEPSEEK_TIMEOUT_SECONDS", 30.0),
        max_tokens=_int_env(source, "DEEPSEEK_MAX_TOKENS", 900),
    )


def add_ai_help_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("question", nargs="*", help="Question for the Haocean usage assistant")
    parser.add_argument("--local", action="store_true", help="Use built-in help without DeepSeek")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haocean Mooc AI usage assistant")
    subparsers = parser.add_subparsers(dest="command")
    ai_help = subparsers.add_parser("ai-help", help="Ask the Haocean usage assistant")
    add_ai_help_arguments(ai_help)
    return parser


def _local_help_for(question: str = "") -> str:
    question = question.strip()
    if not question:
        return LOCAL_HELP
    return f"{LOCAL_HELP}\n针对你的问题：{question}\n优先从上面的学生端或教师端命令开始。"


def call_deepseek(
    question: str,
    config: AIHelpConfig,
    *,
    history: Sequence[dict[str, str]] = (),
    opener: UrlOpen = urllib.request.urlopen,
) -> str:
    if not config.api_key:
        raise AIHelpError("DEEPSEEK_API_KEY is not configured")

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": question})
    body = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": config.max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with opener(request, timeout=config.timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        raise AIHelpError(f"DeepSeek API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AIHelpError(f"DeepSeek API request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw)
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise AIHelpError("DeepSeek API returned an unexpected response") from exc

    answer = str(content).strip()
    if not answer:
        raise AIHelpError("DeepSeek API returned an empty answer")
    return answer


def run_ai_help(
    question_words: Sequence[str] | None = None,
    *,
    force_local: bool = False,
    config: AIHelpConfig | None = None,
    opener: UrlOpen = urllib.request.urlopen,
) -> None:
    config = config or load_ai_help_config()
    question = " ".join(question_words or ()).strip()

    if question:
        if force_local or not config.api_key:
            if not config.api_key and not force_local:
                print("DEEPSEEK_API_KEY is not set; showing built-in help.")
            print(_local_help_for(question))
            return
        try:
            print(call_deepseek(question, config, opener=opener))
        except AIHelpError as exc:
            print(f"DeepSeek unavailable: {exc}")
            print(_local_help_for(question))
        return

    _run_repl(config=config, force_local=force_local, opener=opener)


def _run_repl(
    *,
    config: AIHelpConfig,
    force_local: bool,
    opener: UrlOpen,
) -> None:
    print("Haocean AI Help. Type q, quit, or exit to leave.")
    if force_local or not config.api_key:
        print("DEEPSEEK_API_KEY is not set; using built-in help.")

    history: list[dict[str, str]] = []
    while True:
        try:
            question = input("haocean-ai> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question.lower() in {"q", "quit", "exit"}:
            return
        if not question:
            continue

        if force_local or not config.api_key:
            print(_local_help_for(question))
            continue

        try:
            answer = call_deepseek(question, config, history=history[-8:], opener=opener)
        except AIHelpError as exc:
            print(f"DeepSeek unavailable: {exc}")
            print(_local_help_for(question))
            continue

        print(answer)
        history.extend(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer},
            ]
        )


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "ai-help":
        run_ai_help(args.question, force_local=args.local)
        return

    print("Use `haocean ai-help` for the Haocean Mooc assistant.")
    print("Student commands use `haocean-student`; teacher commands use `haocean-teacher`.")
