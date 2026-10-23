"""Smoke of the model provider (AI19) from the repo root, without Docker:

    python scripts/llm_smoke.py

Reads LLM_* from the environment, else from .env, and runs backend/apps/assistant/llm/smoke.py
(standard library only). On the stand the same check runs in the container:

    docker compose exec backend python -m apps.assistant.llm.smoke

Prints «готово» or what is wrong; the key is never printed.
"""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


if __name__ == "__main__":
    env = {**read_env(ROOT / ".env"), **{k: v for k, v in os.environ.items() if k.startswith("LLM_")}}
    smoke = runpy.run_path(str(ROOT / "backend" / "apps" / "assistant" / "llm" / "smoke.py"))
    sys.exit(smoke["run"](env))
