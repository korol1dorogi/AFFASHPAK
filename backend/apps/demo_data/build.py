"""Assemble the dataset and serialize it byte-for-byte reproducibly.

Minimal on purpose: the format is a draft until docs/data-spec.md (D7) is approved.
"""

import hashlib
import json
from datetime import date

from apps.demo_data.companies import make_companies
from apps.demo_data.personas import make_personas
from apps.demo_data.rng import Rng

SCHEMA_VERSION = "0.1-draft"
DEFAULT_SEED = 42
DEFAULT_AS_OF = date(2026, 10, 1)
# Background companies on top of the personas; the plan asks for 200+ in total.
DEFAULT_COMPANY_COUNT = 200


def build_dataset(
    seed: int = DEFAULT_SEED,
    *,
    as_of: date = DEFAULT_AS_OF,
    company_count: int = DEFAULT_COMPANY_COUNT,
) -> dict:
    if company_count < 0:
        raise ValueError("company_count must be >= 0")
    rng = Rng(seed)
    taken_inns: set[str] = set()
    # Personas first: their identities must not depend on how many background companies exist.
    personas, persona_companies = make_personas(rng, as_of=as_of, taken_inns=taken_inns)
    companies = make_companies(
        rng.child("companies"), company_count, as_of=as_of, taken_inns=taken_inns
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "as_of": as_of.isoformat(),
        "is_demo": True,
        "companies": persona_companies + companies,
        "personas": personas,
    }


def dumps(dataset: dict) -> bytes:
    """Canonical JSON: sorted keys, UTF-8, fixed separators, trailing newline."""
    text = json.dumps(dataset, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
