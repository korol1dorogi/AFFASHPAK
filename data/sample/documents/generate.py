"""PDF stubs with a «DEMO» watermark for scenario 4 (S9; docs/data-spec.md §7.6, §9.3).

Pure standard library, no PDF dependency: one A4 page, the standard Helvetica font (not embedded),
fixed metadata — the same bytes on every run. Helvetica has no Cyrillic, so the text is Latin.

    python data/sample/documents/generate.py            # writes the PDFs next to this file
    python data/sample/documents/generate.py --out DIR
"""

import argparse
from pathlib import Path

# Persona 4 `furniture_maker` (data-spec §9.1): synthetic company, region 00.
COMPANY = "OOO Dubrava Mebel (demo)"
INN = "0001000042"
DOCUMENT_DATE = "2026-10-01"  # data-spec as_of
CREATION_DATE = "D:20261001000000Z"

# data-spec §9.3: uploaded by demo_accountant; financial_report — on the officer's request.
DOCUMENTS = (
    ("bank_statement", "Bank statement"),
    ("tax_return", "Tax return"),
    ("contract", "Supply contract: CNC milling machine"),
    ("invoice", "Invoice"),
    ("financial_report", "Financial report for the last year"),
)

PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 in points


def file_name(kind: str) -> str:
    """data-spec §7.6: original_name = "{kind}_{inn}_демо.pdf"."""
    return f"{kind}_{INN}_демо.pdf"


def _text(value: str) -> str:
    """PDF literal string; the content is ASCII by construction (standard font)."""
    if not value.isascii():
        raise ValueError(f"standard Helvetica cannot show non-ASCII text: {value!r}")
    return "(" + value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def _content(kind: str, title: str) -> bytes:
    lines = [
        # Watermark: light grey, 45°, drawn first so the text stays on top.
        "q 0.85 g BT /F1 150 Tf 0.7071 0.7071 -0.7071 0.7071 150 230 Tm",
        f"{_text('DEMO')} Tj ET Q",
        "BT /F1 22 Tf 60 760 Td",
        f"{_text(title)} Tj ET",
        "BT /F1 12 Tf 60 720 Td 16 TL",
        f"{_text('Document kind: ' + kind)} Tj T*",
        f"{_text('Company: ' + COMPANY)} Tj T*",
        f"{_text('INN: ' + INN)} Tj T*",
        f"{_text('Date: ' + DOCUMENT_DATE)} Tj T*",
        "T*",
        f"{_text('Synthetic document created by the demo data generator.')} Tj T*",
        f"{_text('Not a real document. For demo only.')} Tj ET",
    ]
    return "\n".join(lines).encode("ascii")


def build_pdf(kind: str, title: str) -> bytes:
    content = _content(kind, title)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        (
            f"<< /Title {_text(title + ' (demo)')} /Producer {_text('S2/S9 demo data generator')}"
            f" /CreationDate {_text(CREATION_DATE)} /ModDate {_text(CREATION_DATE)} >>"
        ).encode("ascii"),
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


def generate(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for kind, title in DOCUMENTS:
        path = out_dir / file_name(kind)
        path.write_bytes(build_pdf(kind, title))
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    for path in generate(args.out):
        print(f"{path.name}: {path.stat().st_size} bytes")  # noqa: T201 — CLI output
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
