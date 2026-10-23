"""Dialogue scenarios of the assistant (interface И4): one format for the eval (AI10), the mock
(AI20), the e2e (AI8) and the red team (AI7).

`<kind>/*.yaml` — kind is `client`, `bank` or `attacks`:

    id: client-cash-gap-1
    profile: client            # client | bank
    persona: coffee_shop       # a persona of seed_demo (docs/demo.md); bank: whose application
    application: null          # null — no application; latest — the persona's scenario application
    setup:                     # optional
      failing: [bki]           # sources down while the application is decided (scenario 7)
      company_short_name: "…"  # the company's label — indirect injection (attack 6)
    turns:
      - user: "Зарплата 5-го, а клиенты платят 10-го"
        expect_tools: [{name: recommend_products, args: {need_type: cash_gap}}]  # args ⊆ call
        must_include: ["овердрафт"]          # case and spaces do not matter
        must_not_include: ["одобрено"]
        forbid_tools: [create_draft]

`load()` validates every file: a broken scenario is an error with its file name, never skipped.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from apps.assistant import tools, tools_bank
from apps.assistant.scenarios.fixtures import SAME_COMPANY, SPECS

ROOT = Path(__file__).parent
KINDS = ("client", "bank", "attacks")
PERSONAS = frozenset(SPECS) | frozenset(SAME_COMPANY)
SETUP_KEYS = frozenset({"failing", "company_short_name"})
TURN_KEYS = frozenset({"user", "expect_tools", "must_include", "must_not_include", "forbid_tools"})
KEYS = frozenset({"id", "profile", "persona", "application", "setup", "turns", "description"})
SOURCES = frozenset({"egrul", "transparent_business", "bki", "bank_account"})


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class ExpectedCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Turn:
    user: str
    expect_tools: tuple[ExpectedCall, ...] = ()
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()
    forbid_tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    id: str
    kind: str
    profile: str
    persona: str
    application: str | None
    turns: tuple[Turn, ...]
    failing: tuple[str, ...] = ()
    company_short_name: str | None = None
    description: str = ""


def _toolset(profile: str) -> set[str]:
    return set((tools if profile == "client" else tools_bank).TOOLS)


def _parse(path: Path, kind: str) -> Scenario:
    def fail(message: str) -> ScenarioError:
        where = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.name
        return ScenarioError(f"{where}: {message}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise fail("a scenario is a mapping")
    unknown = set(data) - KEYS
    if unknown:
        raise fail(f"unknown keys {sorted(unknown)}")
    for key in ("id", "profile", "persona", "turns"):
        if key not in data:
            raise fail(f"{key} is required")
    if data["id"] != path.stem:
        raise fail(f"id {data['id']!r} must match the file name")
    profile = data["profile"]
    if profile not in ("client", "bank"):
        raise fail("profile is client or bank")
    if kind != "attacks" and profile != kind:
        raise fail(f"a {kind} scenario has profile {kind}")
    if data["persona"] not in PERSONAS:
        raise fail(f"unknown persona {data['persona']!r}")
    application = data.get("application")
    if application not in (None, "latest"):
        raise fail("application is null or latest")
    if profile == "bank" and application != "latest":
        raise fail("the bank assistant works on an application: application: latest")
    setup = data.get("setup") or {}
    if set(setup) - SETUP_KEYS:
        raise fail(f"unknown setup keys {sorted(set(setup) - SETUP_KEYS)}")
    failing = tuple(setup.get("failing") or ())
    if set(failing) - SOURCES:
        raise fail(f"unknown sources {sorted(set(failing) - SOURCES)}")
    available = _toolset(profile)
    turns = []
    if not isinstance(data["turns"], list) or not data["turns"]:
        raise fail("turns is a non-empty list")
    for number, raw in enumerate(data["turns"], 1):
        if not isinstance(raw, dict) or set(raw) - TURN_KEYS or not raw.get("user"):
            raise fail(f"turn {number}: user is required, keys {sorted(TURN_KEYS)}")
        expected = []
        for call in raw.get("expect_tools") or []:
            if call.get("name") not in available:
                raise fail(f"turn {number}: {call.get('name')!r} is not a {profile} tool")
            expected.append(ExpectedCall(call["name"], dict(call.get("args") or {})))
        forbid = tuple(raw.get("forbid_tools") or ())
        if set(forbid) - available - _toolset("bank" if profile == "client" else "client"):
            raise fail(f"turn {number}: forbid_tools names unknown tools")
        turns.append(
            Turn(
                user=str(raw["user"]),
                expect_tools=tuple(expected),
                must_include=tuple(str(item) for item in raw.get("must_include") or ()),
                must_not_include=tuple(str(item) for item in raw.get("must_not_include") or ()),
                forbid_tools=forbid,
            )
        )
    return Scenario(
        id=data["id"],
        kind=kind,
        profile=profile,
        persona=data["persona"],
        application=application,
        turns=tuple(turns),
        failing=failing,
        company_short_name=setup.get("company_short_name"),
        description=str(data.get("description") or ""),
    )


def load(kind: str | None = None, root: Path = ROOT) -> list[Scenario]:
    """All scenarios (or one kind), validated, sorted by id."""
    kinds = KINDS if kind in (None, "all") else (kind,)
    scenarios: list[Scenario] = []
    for name in kinds:
        if name not in KINDS:
            raise ScenarioError(f"unknown kind {name!r}: {', '.join(KINDS)}")
        for path in sorted((root / name).glob("*.yaml")):
            scenarios.append(_parse(path, name))
    ids = [scenario.id for scenario in scenarios]
    duplicates = {item for item in ids if ids.count(item) > 1}
    if duplicates:
        raise ScenarioError(f"duplicate ids {sorted(duplicates)}")
    return scenarios


def by_user_text(profile: str) -> dict[str, tuple[ExpectedCall, ...]]:
    """Turn text → the tool calls it expects (the scenario mock, AI20). Loaded once per call."""
    index: dict[str, tuple[ExpectedCall, ...]] = {}
    for scenario in load():
        if scenario.profile != profile:
            continue
        for turn in scenario.turns:
            index.setdefault(turn.user.strip(), turn.expect_tools)
    return index
