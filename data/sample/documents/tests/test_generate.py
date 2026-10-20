"""S9 PDF stubs: structure, determinism, size, S3 signature check, committed files are fresh.

Run: see data/sample/documents/README.md («Проверки»).
"""

import hashlib
import re
from pathlib import Path

import pytest

import generate as gen
from generate import DOCUMENTS, build_pdf, file_name, generate

HERE = Path(__file__).resolve().parent.parent
MAX_SIZE = 20 * 1024


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="module")
def pdfs() -> dict[str, bytes]:
    return {kind: build_pdf(kind, title) for kind, title in DOCUMENTS}


def test_documents_of_scenario_4():
    """data-spec §9.3: persona 4 uploads four, financial_report comes on the officer's request."""
    kinds = [kind for kind, _ in DOCUMENTS]
    assert kinds == ["bank_statement", "tax_return", "contract", "invoice", "financial_report"]


def test_structure_header_xref_trailer(pdfs):
    for kind, data in pdfs.items():
        assert data.startswith(b"%PDF-1.4\n"), kind
        assert data.endswith(b"%%EOF\n"), kind
        startxref = int(re.search(rb"startxref\n(\d+)\n%%EOF\n$", data).group(1))
        assert data[startxref:].startswith(b"xref\n0 7\n"), kind
        entries = re.findall(rb"(\d{10}) (\d{5}) ([nf]) \n", data[startxref:])
        assert len(entries) == 7 and entries[0] == (b"0000000000", b"65535", b"f")
        for number, (offset, _, _) in enumerate(entries[1:], start=1):
            assert data[int(offset) :].startswith(f"{number} 0 obj\n".encode()), (kind, number)
        trailer = data[data.index(b"trailer") :]
        assert b"/Root 1 0 R" in trailer and b"/Size 7" in trailer


def test_stream_length_matches(pdfs):
    for kind, data in pdfs.items():
        length = int(re.search(rb"/Length (\d+) >>\nstream\n", data).group(1))
        start = data.index(b"stream\n") + len(b"stream\n")
        assert data[start + length :].startswith(b"\nendstream"), kind


def test_content(pdfs):
    for kind, data in pdfs.items():
        assert b"(DEMO) Tj" in data and b"0.7071 0.7071 -0.7071 0.7071" in data
        assert f"(Document kind: {kind}) Tj".encode() in data
        assert b"(INN: 0001000042) Tj" in data
        assert b"Synthetic document" in data
        assert b"/CreationDate (D:20261001000000Z)" in data


def test_cyrillic_demo_is_drawn_without_a_font(pdfs):
    """«ДЕМО» is vector strokes: no Cyrillic bytes, no second font, stroked paths present."""
    strokes = gen.cyrillic_demo_strokes()
    assert len(strokes) == 6  # Д: 2 lines, Е: 2, М: 1, О: 1 ellipse
    for data in pdfs.values():
        assert data.count(b"/BaseFont") == 1
        assert all(stroke.encode("ascii") in data for stroke in strokes)
        assert re.search(rb"0\.85 G 1 J 1 j 0\.7071 0\.7071 -0\.7071 0\.7071 150 230 cm", data)


def test_watermark_fits_the_page_and_does_not_hit_latin_demo():
    """Glyph box (with half the stroke width) mapped to the page stays inside A4."""
    scale, half = gen._WATERMARK_SCALE, gen._STROKE * gen._WATERMARK_SCALE / 2
    ox, oy = gen._CYRILLIC_ORIGIN
    width = 3 * gen._ADVANCE + 60
    local = [(ox + x * scale, oy + y * scale) for x in (0, width) for y in (-15, 100)]
    for x, y in local:
        for dx in (-half, half):
            for dy in (-half, half):
                page_x = 150 + 0.7071 * (x + dx) - 0.7071 * (y + dy)
                page_y = 230 + 0.7071 * (x + dx) + 0.7071 * (y + dy)
                assert 0 < page_x < gen.PAGE_WIDTH and 0 < page_y < gen.PAGE_HEIGHT
    assert oy + 100 * scale + half < 0  # top of «ДЕМО» stays below the DEMO baseline


def test_file_names_are_ascii():
    """Deviation from data-spec §7.6 («_демо»): Cyrillic names break zip on Windows."""
    for kind, _ in DOCUMENTS:
        assert file_name(kind) == f"{kind}_0001000042_demo.pdf" and file_name(kind).isascii()


def test_deterministic(tmp_path):
    first = {p.name: sha256(p.read_bytes()) for p in generate(tmp_path / "a")}
    second = {p.name: sha256(p.read_bytes()) for p in generate(tmp_path / "b")}
    assert first == second


def test_size_limit(pdfs):
    assert all(len(data) < MAX_SIZE for data in pdfs.values())


def test_s3_signature_check(pdfs):
    signatures = pytest.importorskip("apps.documents.signatures")
    for data in pdfs.values():
        assert signatures.detect_content_type(data[:16]) == signatures.PDF


def test_committed_files_match_the_generator(pdfs):
    for kind, data in pdfs.items():
        path = HERE / file_name(kind)
        assert path.exists(), f"run generate.py: {path.name} is missing"
        assert path.read_bytes() == data, f"{path.name} is stale: run generate.py"
