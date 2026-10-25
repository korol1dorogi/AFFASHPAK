"""«Вставил ключ — полетело» (AI19): is the model provider of .env ready for the assistant?

Standard library only, no Django — runs anywhere:

    docker compose exec backend python -m apps.assistant.llm.smoke     # the stand's .env
    python scripts/llm_smoke.py                                         # the .env of the repo

Checks LLM_BASE_URL, LLM_API_KEY and every model of LLM_MODEL (comma separated): the list of
models answers, the model calls a tool with JSON arguments, the answer time. Prints «готово» or
what is wrong in plain words. Exit code: 0 — every model works, 1 — some do, 2 — none.
The key is never printed.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

TOOL = {
    "type": "function",
    "function": {
        "name": "calc_payment",
        "description": "Ежемесячный аннуитетный платёж.",
        "parameters": {
            "type": "object",
            "properties": {
                "principal": {"type": "string", "description": "Сумма, рубли"},
                "annual_rate": {"type": "string", "description": "Годовая ставка, доля"},
                "term_months": {"type": "integer"},
            },
            "required": ["principal", "annual_rate", "term_months"],
        },
    },
}
QUESTION = "Посчитай ежемесячный платёж: 1 000 000 рублей под 24% годовых на 12 месяцев."
SLOW_SECONDS = 15.0

HINTS = {
    401: "ключ не подходит — проверьте LLM_API_KEY",
    402: "на счёте провайдера нет денег — пополните баланс или выберите бесплатную модель",
    403: "доступ запрещён — ключ без прав на эту модель или регион",
    404: "нет такого адреса или модели — проверьте LLM_BASE_URL (обычно оканчивается на /v1) "
    "и имя модели в LLM_MODEL",
    429: "лимит запросов провайдера — подождите минуту; в LLM_MODEL можно перечислить "
    "запасные модели через запятую",
}


class Failure(Exception):
    pass


def _request(base_url: str, key: str, path: str, body: dict | None, timeout: float) -> dict:
    data = None if body is None else json.dumps(body).encode()
    # run() lets only http(s) addresses through
    request = urllib.request.Request(  # noqa: S310
        base_url + path, data=data, method="POST" if data else "GET"
    )
    request.add_header("Content-Type", "application/json")
    # Providers behind Cloudflare refuse the default «Python-urllib» agent with 403.
    request.add_header("User-Agent", "alfa-cabinet-llm-smoke/1.0")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        hint = HINTS.get(error.code) or f"провайдер ответил ошибкой {error.code}"
        raise Failure(f"{hint} (HTTP {error.code})") from error
    except urllib.error.URLError as error:
        raise Failure(
            f"не удалось подключиться к {base_url}: {error.reason} — проверьте LLM_BASE_URL "
            "и что сервис модели запущен"
        ) from error
    except TimeoutError as error:
        raise Failure(f"нет ответа за {timeout:.0f} с — увеличьте LLM_TIMEOUT_SECONDS") from error
    except json.JSONDecodeError as error:
        raise Failure("ответ не JSON — это точно OpenAI-совместимый адрес?") from error


def check_model(base_url: str, key: str, model: str, timeout: float) -> tuple[float, str]:
    """One tool call of the model → (seconds, the arguments it sent). Failure — what is wrong."""
    started = time.monotonic()
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Для расчётов всегда вызывай инструмент."},
            {"role": "user", "content": QUESTION},
        ],
        "tools": [TOOL],
        "tool_choice": "auto",
        "temperature": 0,
        # Reasoning models (Qwen3.6, gpt-oss) think a few hundred tokens before the call.
        "max_tokens": 2000,
    }
    completion = _request(base_url, key, "/chat/completions", body, timeout)
    seconds = time.monotonic() - started
    try:
        message = completion["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as error:
        raise Failure("в ответе нет choices[0].message — формат не OpenAI") from error
    calls = message.get("tool_calls") or []
    if not calls:
        raise Failure(
            "модель ответила текстом и не вызвала инструмент — она не поддерживает вызов "
            "инструментов (tools); выберите другую модель"
        )
    function = calls[0].get("function") or {}
    raw = function.get("arguments") or "{}"
    try:
        arguments = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as error:
        raise Failure(f"аргументы инструмента не JSON: {str(raw)[:80]}") from error
    if function.get("name") != "calc_payment" or not isinstance(arguments, dict):
        raise Failure(f"модель вызвала не тот инструмент: {function.get('name')!r}")
    return seconds, json.dumps(arguments, ensure_ascii=False)


def run(env: Mapping[str, str], out: Callable[[str], None] = print) -> int:
    base_url = (env.get("LLM_BASE_URL") or "").strip().rstrip("/")
    key = (env.get("LLM_API_KEY") or "").strip()
    models = [m.strip() for m in (env.get("LLM_MODEL") or "").split(",") if m.strip()]
    timeout = float(env.get("LLM_TIMEOUT_SECONDS") or 30)
    provider = (env.get("LLM_PROVIDER") or "mock").strip()

    if not base_url or not models:
        out("Не настроено: нужны LLM_BASE_URL и LLM_MODEL в .env (README, «Подключить модель»).")
        return 2
    if not base_url.startswith(("http://", "https://")):
        out("Не настроено: LLM_BASE_URL должен начинаться с http:// или https://")
        return 2
    has_key = "задан" if key else "не задан"
    out(f"Провайдер: {base_url}; ключ: {has_key}; моделей: {len(models)}")
    if provider != "openai":
        out("Внимание: LLM_PROVIDER не openai — ассистент сейчас отвечает заглушкой (mock).")
    try:
        listed = _request(base_url, key, "/models", None, timeout)
        names = {item.get("id") for item in listed.get("data", []) if isinstance(item, dict)}
        missing = [m for m in models if names and m not in names]
        if missing:
            out(f"Внимание: провайдер не перечисляет {', '.join(missing)} — проверьте имя модели")
    except Failure as error:
        if "HTTP 401" in str(error) or "подключиться" in str(error):
            out(f"Не готово: {error}")
            return 2
        out(f"Список моделей недоступен ({error}) — проверяю сами модели")

    working = 0
    for model in models:
        try:
            seconds, arguments = check_model(base_url, key, model, timeout)
        except Failure as error:
            out(f"✗ {model}: {error}")
            continue
        working += 1
        slow = " — медленно, ответы ассистента займут время" if seconds > SLOW_SECONDS else ""
        out(f"✓ {model}: вызвала инструмент за {seconds:.1f} с, аргументы {arguments}{slow}")
    if working == len(models):
        where = "на этих моделях" if working > 1 else "на этой модели"
        out(f"готово: ассистент может работать {where}")
        return 0
    if working:
        out(f"частично: работают {working} из {len(models)} — нерабочие уберите из LLM_MODEL")
        return 1
    out("не готово: ни одна модель не прошла проверку")
    return 2


if __name__ == "__main__":
    sys.exit(run(os.environ))
