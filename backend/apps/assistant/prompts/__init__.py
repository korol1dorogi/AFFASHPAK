"""Master prompts of the assistant (interface И2 in docs/tasks.md).

`prompts/<profile>.md` holds the prompt; its first line is `version: N`. At request time only three
placeholders are filled: {today}, {user_name}, {application_context}. Filling is one regex pass,
not str.format: the prompt contains JSON with braces, and a value (a company name, a comment) must
never expand into another placeholder.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

Profile = Literal["client", "bank"]
PROFILES: tuple[Profile, ...] = ("client", "bank")
PLACEHOLDERS = ("today", "user_name", "application_context")

_DIR = Path(__file__).resolve().parent
_VERSION = re.compile(r"^version:\s*(\d+)\s*$")
_PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")
NO_CONTEXT = "Нет данных о заявке."


@dataclass(frozen=True)
class Prompt:
    profile: Profile
    version: int
    text: str

    def render(self, *, today: str, user_name: str, application_context: str = "") -> str:
        values = {
            "today": today,
            "user_name": user_name,
            "application_context": application_context.strip() or NO_CONTEXT,
        }
        return _PLACEHOLDER.sub(lambda match: values[match.group(1)], self.text)


@cache
def load(profile: Profile) -> Prompt:
    if profile not in PROFILES:
        raise ValueError(f"Unknown assistant profile: {profile!r}")
    raw = (_DIR / f"{profile}.md").read_text(encoding="utf-8")
    first, _, body = raw.partition("\n")
    match = _VERSION.match(first)
    if match is None:
        raise ValueError(f"prompts/{profile}.md must start with 'version: N'")
    return Prompt(profile=profile, version=int(match.group(1)), text=body.strip() + "\n")
