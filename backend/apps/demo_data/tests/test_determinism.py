import ast
from pathlib import Path

from apps.demo_data.__main__ import main
from apps.demo_data.build import dumps, generate, sha256

PACKAGE = Path(__file__).resolve().parent.parent
SMALL = 12


def test_same_seed_gives_byte_identical_file(dataset_bytes):
    """§11.1: two runs with seed 2026 and 240 companies are byte-for-byte equal."""
    assert sha256(dumps(generate(2026))) == sha256(dataset_bytes)


def test_other_seed_changes_the_population_only():
    """§11.1: seed 2027 differs in the population; personas and edge cases stay the same."""
    first, second = generate(2026, n_companies=SMALL), generate(2027, n_companies=SMALL)
    assert dumps(first) != dumps(second)
    assert first["personas"] == second["personas"]
    assert first["edge_cases"] == second["edge_cases"]
    fixed = {c["_key"] for c in first["companies"] if c["_persona"]}
    for name in ("companies", "financial_snapshots", "statements"):
        key = "_key" if name == "companies" else "company"

        def pick(data, name=name, key=key):
            return [r for r in data[name] if r[key] in fixed]

        assert pick(first) == pick(second)


def test_cli_writes_the_same_bytes(tmp_path):
    out = tmp_path / "demo.json"
    assert main(["--seed", "7", "--n-companies", "3", "--out", str(out)]) == 0
    assert out.read_bytes() == dumps(generate(7, n_companies=3))


FORBIDDEN_CALLS = {"now", "utcnow", "today", "uuid1", "uuid4", "time_ns", "urandom"}
FORBIDDEN_MODULES = {"random", "uuid", "secrets", "time"}


def test_no_hidden_sources_of_randomness_or_time():
    sources = [p for p in PACKAGE.rglob("*.py") if "tests" not in p.parts]
    assert sources
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {alias.name.split(".")[0] for alias in node.names}
                assert not names & FORBIDDEN_MODULES, (path.name, names)
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in FORBIDDEN_MODULES, path.name
            elif isinstance(node, ast.Attribute):
                assert node.attr not in FORBIDDEN_CALLS, (path.name, node.attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "hash", path.name
