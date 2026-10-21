"""Malicious and malformed uploads are rejected before they are stored (inspection.py)."""

import zlib

import pytest

from apps.documents import inspection
from apps.documents.inspection import UnsafeFile, inspect
from apps.documents.signatures import JPEG, PDF, PNG
from apps.documents.tests.test_signatures import JPEG_BYTES, PDF_BYTES, PNG_BYTES, png_chunk


def pdf(body: bytes) -> bytes:
    return b"%PDF-1.7\n" + body + b"\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def stream(content: bytes) -> bytes:
    packed = zlib.compress(content)
    return (
        b"5 0 obj\n<< /Type /ObjStm /Filter /FlateDecode /Length "
        + str(len(packed)).encode()
        + b" >>\nstream\n"
        + packed
        + b"\nendstream\nendobj"
    )


CLEAN_PDF = pdf(
    b"1 0 obj << /Type /Catalog /Pages 2 0 R /OpenAction [3 0 R /Fit] >> endobj\n"
    b"3 0 obj << /Type /Annot /Subtype /Link "
    b"/A << /S /URI /URI (https://example.org) >> >> endobj\n"
    + stream(b"BT /F1 12 Tf 72 712 Td (Vypiska demo) Tj ET")
)


@pytest.mark.parametrize(
    "data",
    [PDF_BYTES, CLEAN_PDF, b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\n%%EOF\r\n\r\n"],
)
def test_ordinary_pdfs_pass(data):
    inspect(PDF, data)


@pytest.mark.parametrize(
    ("data", "why"),
    [
        (pdf(b"1 0 obj << /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >> endobj"), "JS"),
        (pdf(b"1 0 obj << /OpenAction << /S /J#61vaScript /J#53 (x) >> >> endobj"), "JavaScript"),
        (pdf(stream(b"<< /S /JavaScript /JS (this.exportDataObject()) >>")), "JavaScript"),
        (pdf(b"1 0 obj << /A << /S /Launch /F (cmd.exe) >> >> endobj"), "Launch"),
        (pdf(b"1 0 obj << /Names << /EmbeddedFiles 2 0 R >> >> endobj"), "EmbeddedFiles"),
        (pdf(b"1 0 obj << /AcroForm << /XFA 4 0 R >> >> endobj"), "XFA"),
        (pdf(b"1 0 obj << /AA << /O << /S /URI /URI (http://x) >> >> >> endobj"), "AA"),
        (pdf(b"1 0 obj << /A << /S /SubmitForm /F (http://x) >> >> endobj"), "SubmitForm"),
        (pdf(b"1 0 obj << /RichMedia 3 0 R >> endobj"), "RichMedia"),
        (pdf(b"trailer << /Encrypt 9 0 R >>"), "паролем"),
    ],
)
def test_pdf_with_active_or_hidden_content_is_rejected(data, why):
    with pytest.raises(UnsafeFile, match=why):
        inspect(PDF, data)


@pytest.mark.parametrize(
    ("data", "why"),
    [
        (PDF_BYTES + b"\n<html><script>alert(document.cookie)</script></html>", "HTML"),
        (PDF_BYTES + b"\nMZ\x90\x00 this is an appended program", "лишние данные"),
        (pdf(b"1 0 obj (<script>alert(1)</script>) endobj"), "HTML"),
        (pdf(stream(b"<html><body onload=x>")), "HTML"),
        (b"%PDF-9.9\n%%EOF", "заголовок"),
        (b"%PDF-1.4\n1 0 obj<<>>endobj\n", "лишние данные"),
    ],
)
def test_polyglots_and_broken_pdfs_are_rejected(data, why):
    with pytest.raises(UnsafeFile, match=why):
        inspect(PDF, data)


def test_a_decompression_bomb_stops_at_the_budget(monkeypatch):
    monkeypatch.setattr(inspection, "_INFLATE_BUDGET", 1024 * 1024)
    bomb = pdf(stream(b"\x00" * (4 * 1024 * 1024)))
    assert len(bomb) < 10_000
    with pytest.raises(UnsafeFile, match="слишком большой"):
        inspect(PDF, bomb)


def test_images_pass_when_well_formed():
    inspect(PNG, PNG_BYTES)
    inspect(JPEG, JPEG_BYTES)


@pytest.mark.parametrize(
    ("content_type", "data", "why"),
    [
        (PNG, PNG_BYTES + b"<?php system($_GET['c']); ?>", "HTML или скрипт"),
        (PNG, PNG_BYTES + b"\x00\x01trailing", "лишние данные"),
        (PNG, PNG_BYTES[:-6], "обрывается"),
        (PNG, PNG_BYTES[:8] + png_chunk(b"IDAT", b"x") + png_chunk(b"IEND", b""), "повреждённый"),
        (PNG, PNG_BYTES[:20] + b"\xff" + PNG_BYTES[21:], "повреждённый"),
        (JPEG, JPEG_BYTES + b"<html><script>x</script>", "HTML или скрипт"),
        (JPEG, JPEG_BYTES + b"PK\x03\x04hidden.zip", "лишние данные"),
        (JPEG, JPEG_BYTES[:-2], "оборван"),
    ],
)
def test_image_polyglots_and_damage_are_rejected(content_type, data, why):
    with pytest.raises(UnsafeFile, match=why):
        inspect(content_type, data)
