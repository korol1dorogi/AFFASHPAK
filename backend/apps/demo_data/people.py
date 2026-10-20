"""Synthetic people: names (§3.3), users and memberships (§8), founders (§5.1)."""

from apps.demo_data.ids import INSPECTION_FOUNDER, Counter, make_inn12
from apps.demo_data.reference import (
    DEMO,
    DIRECTOR_IS_FOUNDER_SHARE,
    FEMALE_NAMES,
    FOUNDER_SHARES,
    MALE_NAMES,
    PATRONYMICS,
    SURNAMES,
)
from apps.demo_data.rng import Rng


def random_fio(rng: Rng) -> str:
    """«Фамилия Имя Отчество» with gender agreement; no «(демо)» yet."""
    female = rng.chance("0.5")
    surname = rng.choice(SURNAMES) + ("а" if female else "")
    first = rng.choice(FEMALE_NAMES if female else MALE_NAMES)
    patronymic = rng.choice(PATRONYMICS)
    if female:
        patronymic = patronymic.removesuffix("вич") + "вна"
    return f"{surname} {first} {patronymic}"


def demo(text: str) -> str:
    return text + DEMO


def user(key: str, username: str, kind: str, fio: str, *, login_enabled: bool) -> dict:
    return {
        "_key": key,
        "_login_enabled": login_enabled,
        "username": username,
        "profile": {"kind": kind, "full_name": demo(fio), "is_demo": True},
    }


def membership(user_key: str, company_key: str, role: str, position: str) -> dict:
    return {"user": user_key, "company": company_key, "role": role, "position": position}


class FounderRegistry:
    """One INN per person (inspection 03), so a founder of two companies keeps one INN."""

    def __init__(self) -> None:
        self._counter = Counter(1)
        self._inns: dict[str, str] = {}

    def inn(self, fio: str) -> str:
        if fio not in self._inns:
            self._inns[fio] = make_inn12(self._counter.next(), INSPECTION_FOUNDER)
        return self._inns[fio]


def founders(
    rng: Rng,
    *,
    legal_form: str,
    company_inn: str,
    director_fio: str,
    registry: FounderRegistry,
) -> list[dict]:
    """ИП — the entrepreneur with the company INN; ООО — 1–3 founders, director among them 60 %."""
    if legal_form == "ip":
        return [{"name": demo(director_fio), "inn": company_inn, "share": "1.0000"}]
    shares = rng.choice(FOUNDER_SHARES)
    names = [random_fio(rng) for _ in shares]
    if rng.chance(DIRECTOR_IS_FOUNDER_SHARE):
        names[0] = director_fio
    return [
        {"name": demo(name), "inn": registry.inn(name), "share": share}
        for name, share in zip(names, shares, strict=True)
    ]
