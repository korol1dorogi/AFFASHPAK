import pytest

from apps.documents.names import attachment_filename, safe_original_name
from apps.documents.signatures import JPEG, PDF, PNG, detect_content_type

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\ntrailer\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 8


@pytest.mark.parametrize(
    ("header", "content_type"),
    [
        (PDF_BYTES, PDF),
        (PNG_BYTES, PNG),
        (JPEG_BYTES, JPEG),
    ],
)
def test_known_signatures(header: bytes, content_type: str):
    assert detect_content_type(header) == content_type


@pytest.mark.parametrize(
    "header",
    [
        b"",
        b"<html><script>alert(1)</script>",
        b"<svg xmlns='http://www.w3.org/2000/svg'/>",
        b"MZ\x90\x00",
        b"PK\x03\x04",
        b"\n%PDF-1.4",
        b"GIF89a",
    ],
)
def test_rejected_signatures(header: bytes):
    assert detect_content_type(header) is None


def test_original_name_drops_directories_and_control_characters():
    assert safe_original_name(r"..\..\secret.pdf") == "secret.pdf"
    assert safe_original_name("/etc/passwd") == "passwd"
    assert safe_original_name("evil.pdf\r\nX-Injected: yes") == "evil.pdfX-Injected: yes"
    assert safe_original_name("") == "document"
    assert safe_original_name(None) == "document"


def test_attachment_name_uses_detected_extension():
    assert attachment_filename("note.html", PDF) == "note.pdf"
    assert attachment_filename("scan.pdf", JPEG) == "scan.jpg"
