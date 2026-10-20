"""generate(seed, generator_version, as_of, n_companies) → dict, serialized byte-for-byte the same.

Format: docs/data-spec.md §2 (draft, see reference.SPEC_REF). Applications, scores and decisions
(stage 2, §7) and PDF stubs (§7.6) are not generated yet: `applications` stays empty.
"""

import hashlib
import json
from datetime import date

from apps.demo_data import people
from apps.demo_data.assemble import Bundle, Registries, assemble
from apps.demo_data.companies import draft_population
from apps.demo_data.edge_cases import build_edge_cases
from apps.demo_data.personas import PERSONAS, persona_inputs, persona_rng
from apps.demo_data.reference import GENERATOR_VERSION, SPEC_REF
from apps.demo_data.rng import Rng

DEFAULT_SEED = 2026
DEFAULT_AS_OF = date(2026, 10, 1)
DEFAULT_N_COMPANIES = 240
BANK_USERS = ("demo_bank", "demo_bank_2", "demo_bank_3")  # §8


class Dataset:
    def __init__(self) -> None:
        self.companies: list[dict] = []
        self.users: list[dict] = []
        self.memberships: list[dict] = []
        self.snapshots: list[dict] = []
        self.statements: list[dict] = []
        self.egrul: dict[str, dict] = {}
        self.transparent_business: dict[str, dict] = {}
        self.bki: dict[str, dict] = {}
        self.personas: dict[str, dict] = {}
        self.edge_cases: list[dict] = []
        self.latent: dict[str, dict] = {}

    def add(self, bundle: Bundle) -> None:
        inn = bundle.company["inn"]
        self.companies.append(bundle.company)
        self.users.extend(bundle.users)
        self.memberships.extend(bundle.memberships)
        self.snapshots.append(bundle.snapshot)
        self.statements.append(bundle.statement)
        if bundle.egrul is not None:
            self.egrul[inn] = bundle.egrul
        self.transparent_business[inn] = bundle.transparent_business
        self.bki[inn] = bundle.bki


def _bank_users(generator_version: str) -> list[dict]:
    rng = persona_rng(generator_version, "people", "bank")
    return [
        people.user(f"u_{username}", username, "bank", people.random_fio(rng), login_enabled=True)
        for username in BANK_USERS
    ]


def generate(
    seed: int = DEFAULT_SEED,
    generator_version: str = GENERATOR_VERSION,
    as_of: date = DEFAULT_AS_OF,
    n_companies: int = DEFAULT_N_COMPANIES,
) -> dict:
    if n_companies < 0:
        raise ValueError("n_companies must be >= 0")
    data = Dataset()
    registries = Registries()
    # §6.6 order: personas, edge cases, then the population — fixed parts never depend on seed.
    for spec in PERSONAS:
        inputs = persona_inputs(spec, generator_version, as_of)
        bundle = assemble(
            inputs,
            persona_rng(generator_version, "company", spec.code),
            persona_rng(generator_version, "statement", spec.code),
            registries,
            as_of,
        )
        data.add(bundle)
        data.personas[spec.code] = {
            "company": inputs.key,
            "application": None,  # stage 2 (§7.1)
            "users": [user["_key"] for user in bundle.users],
        }
    data.users.extend(_bank_users(generator_version))
    data.edge_cases = build_edge_cases(generator_version, as_of, registries)

    for draft in draft_population(seed, generator_version, n_companies, as_of):
        key = str(draft.index)
        bundle = assemble(
            draft.inputs,
            Rng(seed, generator_version, "registry", key),
            Rng(seed, generator_version, "statement", key),
            registries,
            as_of,
        )
        data.add(bundle)
        data.latent[draft.inputs.key] = draft.latent

    sections = {
        "companies": data.companies,
        "users": data.users,
        "memberships": data.memberships,
        "financial_snapshots": data.snapshots,
        "statements": data.statements,
        "applications": [],
        "personas": data.personas,
        "edge_cases": data.edge_cases,
        "_latent": data.latent,
    }
    simulators = {
        "egrul": data.egrul,
        "transparent_business": data.transparent_business,
        "bki": data.bki,
    }
    counts = {name: len(value) for name, value in sections.items()}
    counts["transactions"] = sum(len(s["transactions"]) for s in data.statements)
    counts.update({f"simulators.{name}": len(value) for name, value in simulators.items()})
    return {
        "meta": {
            "generator_version": generator_version,
            "spec_ref": SPEC_REF,
            "seed": seed,
            "as_of": as_of.isoformat(),
            "n_companies": n_companies,
            "is_demo": True,
            "counts": counts,
        },
        **sections,
        "simulators": simulators,
    }


def dumps(dataset: dict) -> bytes:
    """Canonical JSON (§1): sorted keys, UTF-8, indent 2, trailing newline."""
    text = json.dumps(dataset, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
