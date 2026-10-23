"""«Сводка для решения» (interface И2а): the bank model answers a «[СВОДКА]» message with JSON
{"risks": [...], "to_verify": [...], "draft_comment": "...", "sources": [...]}.

`parse` accepts only that shape (a broken answer is None, never a half summary); `from_facts`
builds the same summary from the bank tools' results — the mock answers with it, and the engine
falls back to it when a live model returns something else. Every line comes from a tool result.
"""

import json
import re

PREFIX = "[СВОДКА]"  # the bank prompt answers a message starting with it with JSON only
KEYS = ("risks", "to_verify", "draft_comment", "sources")
MAX_ITEMS = 8
_JSON = re.compile(r"\{.*\}", re.DOTALL)


def parse(text: str) -> dict | None:
    """The summary from the model's text (a code fence or words around the JSON are tolerated)."""
    match = _JSON.search(text or "")
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or set(data) != set(KEYS):
        return None
    lists = [data[key] for key in ("risks", "to_verify", "sources")]
    if not all(
        isinstance(items, list) and all(isinstance(i, str) for i in items) for items in lists
    ):
        return None
    if not isinstance(data["draft_comment"], str):
        return None
    return {
        "risks": [item.strip() for item in data["risks"] if item.strip()][:MAX_ITEMS],
        "to_verify": [item.strip() for item in data["to_verify"] if item.strip()][:MAX_ITEMS],
        "draft_comment": data["draft_comment"].strip(),
        "sources": [item.strip() for item in data["sources"] if item.strip()][:MAX_ITEMS],
    }


def from_facts(results: dict[str, dict]) -> dict:
    """The summary from bank tool results by tool name (application_summary, score_breakdown,
    checks_with_provenance, missing_documents…): risks by weight, what to verify, a draft."""
    risks: list[str] = []
    to_verify: list[str] = []
    sources: list[str] = []

    score = results.get("score_breakdown") or {}
    for factor in score.get("factors") or []:
        if factor.get("passed") is False and factor.get("value") is not None:
            risks.append(f"{factor['message']} (скоринг: {factor['name']})")
            sources.append(f"скоринг: {factor['name']}")
    for factor in score.get("factors") or []:
        if factor.get("value") is None:
            to_verify.append(f"{factor['message']} (нет данных — проверить вручную)")

    checks = results.get("checks_with_provenance") or {}
    for check in checks.get("checks") or []:
        if check.get("status") not in ("ok", None):
            to_verify.append(f"{check['source_name']}: {check['meaning']}")
            sources.append(f"проверка: {check['source_name']}")
    summary = results.get("application_summary") or {}
    for source, status in (summary.get("checks") or {}).items():
        if status != "ok" and not checks:
            to_verify.append(f"Проверка {source}: статус {status}")
            sources.append(f"проверка: {source}")

    documents = results.get("missing_documents") or {}
    for document in documents.get("missing_product_documents") or []:
        to_verify.append(f"Запросить документ: {document['name']}")
    for item in documents.get("because_of_sources") or []:
        to_verify.append(f"Запросить: {item['ask']}")

    grade = score.get("grade") or (summary.get("decision") or {}).get("grade")
    total = score.get("total")
    head = f"Грейд {grade} ({total} из 100)." if grade and total is not None else ""
    if risks:
        draft = f"{head} Основные риски: " + "; ".join(r.split(" (")[0] for r in risks[:3]) + "."
    else:
        draft = f"{head} Существенных рисков по факторам скоринга нет."
    if to_verify:
        draft += " Перед решением проверить: " + "; ".join(to_verify[:2]) + "."
    return {
        "risks": _unique(risks)[:MAX_ITEMS],
        "to_verify": _unique(to_verify)[:MAX_ITEMS],
        "draft_comment": draft.strip(),
        "sources": _unique(sources)[:MAX_ITEMS] or ["карточка заявки"],
    }


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))
