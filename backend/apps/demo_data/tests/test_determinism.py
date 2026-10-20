import ast
from datetime import date
from pathlib import Path

from apps.demo_data.__main__ import main
from apps.demo_data.build import build_dataset, dumps, sha256

PACKAGE = Path(__file__).resolve().parent.parent


def test_same_seed_gives_byte_identical_file():
    assert sha256(dumps(build_dataset(42))) == sha256(dumps(build_dataset(42)))


def test_different_seed_gives_different_file():
    assert sha256(dumps(build_dataset(42))) != sha256(dumps(build_dataset(43)))


def test_as_of_is_the_only_clock():
    first = dumps(build_dataset(42, as_of=date(2026, 10, 1)))
    assert first == dumps(build_dataset(42, as_of=date(2026, 10, 1)))
    assert first != dumps(build_dataset(42, as_of=date(2025, 10, 1)))


def test_personas_do_not_depend_on_background_size():
    small, large = build_dataset(42, company_count=3), build_dataset(42, company_count=50)
    assert small["personas"] == large["personas"]
    persona_count = len(small["personas"])
    assert small["companies"][:persona_count] == large["companies"][:persona_count]


def test_cli_writes_the_same_bytes(tmp_path):
    out = tmp_path / "demo.json"
    assert main(["--seed", "7", "--companies", "5", "--out", str(out)]) == 0
    assert out.read_bytes() == dumps(build_dataset(7, company_count=5))


FORBIDDEN_CALLS = {"now", "utcnow", "today", "uuid1", "uuid4", "time", "time_ns", "urandom"}
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
