"""Names of companies and counterparties, addresses (docs/data-spec.md §3.3)."""

from apps.demo_data.reference import CITIES, DEMO, GROUPS, REGION, STREETS, OkvedGroup
from apps.demo_data.rng import Rng

_ADJECTIVES = tuple(sorted({a for g in GROUPS for a in g.ooo_words[0]}))
_NOUNS = tuple(sorted({n for g in GROUPS for n in g.ooo_words[1]}))
_REGION_NAME = REGION.split(" (")[0]  # «Демо-регион»


def ooo_name(rng: Rng, group: OkvedGroup) -> str:
    adjectives, nouns = group.ooo_words
    return f"ООО «{rng.choice(adjectives)} {rng.choice(nouns)}»{DEMO}"


def ip_name(rng: Rng, group: OkvedGroup, fio: str) -> str:
    return f"ИП {fio} — {rng.choice(group.ip_kinds)} «{rng.choice(group.ip_signs)}»{DEMO}"


def counterparty_name(rng: Rng) -> str:
    """An ООО that only pays or gets paid: buyer, supplier, landlord (not in companies[])."""
    return f"ООО «{rng.choice(_ADJECTIVES)} {rng.choice(_NOUNS)}»{DEMO}"


def counterparty_names(rng: Rng, count: int, taken: set[str]) -> list[str]:
    """`count` names, distinct from each other and from `taken` (updated in place): two payers
    with one name would be one INN and break the concentration."""
    names = []
    while len(names) < count:
        name = counterparty_name(rng)
        if name not in taken:
            taken.add(name)
            names.append(name)
    return names


def address(rng: Rng) -> str:
    index = f"0000{rng.between(1, 99):02d}"
    city, street, house = rng.choice(CITIES), rng.choice(STREETS), rng.between(1, 120)
    return f"{index}, {_REGION_NAME}, г. {city}, ул. {street}, д. {house}{DEMO}"
