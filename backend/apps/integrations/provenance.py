"""Provenance of a source answer (SRC4): when it came, its sha256 and the simulator version.

The hash is taken over the canonical JSON of {status, data} — sorted keys, UTF-8, no spaces,
dates as strings (the same normalisation the pipeline stores in Check.data), so the same answer
always has the same hash, whatever the key order or a round trip through the database.
A source that did not answer has no provenance.
"""

import hashlib
import json

from django.utils import timezone

from apps.integrations.simulator_data import dataset

NO_ANSWER = frozenset({"unavailable", "consent_missing"})


def canonical(answer: dict) -> bytes:
    payload = {"status": answer["status"], "data": answer["data"]}
    text = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return text.encode("utf-8")


def response_sha256(answer: dict) -> str:
    return hashlib.sha256(canonical(answer)).hexdigest()


def simulator_version() -> str:
    """The version of the synthetic world the simulators answer from; S1 takes it from HTTP."""
    return dataset()["meta"]["generator_version"]


def provenance(answer: dict) -> dict | None:
    """Fields for Check: received_at, response_sha256, simulator_version; None — no answer."""
    if answer["status"] in NO_ANSWER:
        return None
    return {
        "received_at": timezone.now(),
        "response_sha256": response_sha256(answer),
        "simulator_version": simulator_version(),
    }
