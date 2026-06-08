from __future__ import annotations

import json

from module_a.ai_help import (
    AIHelpConfig,
    build_parser as build_ai_parser,
    call_deepseek,
    load_ai_help_config,
    run_ai_help,
)
from module_a.main import build_parser as build_student_parser


class FakeDeepSeekResponse:
    def __enter__(self) -> "FakeDeepSeekResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "运行 haocean-student list 查看开放作业。"
                        }
                    }
                ]
            },
            ensure_ascii=False,
        ).encode("utf-8")


def test_top_level_haocean_parser_accepts_ai_help_question() -> None:
    args = build_ai_parser().parse_args(["ai-help", "怎么提交作业"])

    assert args.command == "ai-help"
    assert args.question == ["怎么提交作业"]


def test_student_parser_accepts_ai_help_before_auth() -> None:
    args = build_student_parser().parse_args(["ai-help", "怎么登录"])

    assert args.command == "ai-help"
    assert args.question == ["怎么登录"]


def test_missing_deepseek_key_uses_local_help(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setenv("HAOCEAN_DEEPSEEK_API_KEY", "")

    run_ai_help(["怎么提交作业"])

    output = capsys.readouterr().out
    assert "DEEPSEEK_API_KEY is not set" in output
    assert "haocean-student submit" in output


def test_invalid_ai_help_numeric_env_values_fall_back_to_defaults() -> None:
    config = load_ai_help_config(
        {
            "HAOCEAN_DEEPSEEK_API_KEY": "alternate-key",
            "DEEPSEEK_TIMEOUT_SECONDS": "not-a-number",
            "DEEPSEEK_MAX_TOKENS": "also-invalid",
        }
    )

    assert config.api_key == "alternate-key"
    assert config.timeout_seconds == 30.0
    assert config.max_tokens == 900


def test_call_deepseek_uses_chat_completion_endpoint() -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request: object, timeout: float) -> FakeDeepSeekResponse:
        captured["url"] = request.full_url  # type: ignore[attr-defined]
        captured["authorization"] = request.get_header("Authorization")  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        return FakeDeepSeekResponse()

    answer = call_deepseek(
        "怎么查看作业？",
        AIHelpConfig(
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            timeout_seconds=5,
            max_tokens=300,
        ),
        opener=fake_urlopen,
    )

    assert answer == "运行 haocean-student list 查看开放作业。"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["timeout"] == 5
    body = captured["body"]
    assert body["model"] == "deepseek-v4-flash"  # type: ignore[index]
    assert body["messages"][0]["role"] == "system"  # type: ignore[index]
    assert body["messages"][-1]["content"] == "怎么查看作业？"  # type: ignore[index]
