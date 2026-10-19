"""Allow-list of file types detected from magic bytes, never from the client header."""

PDF = "application/pdf"
PNG = "image/png"
JPEG = "image/jpeg"

EXTENSIONS = {
    PDF: "pdf",
    PNG: "png",
    JPEG: "jpg",
}

_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"%PDF", PDF),
    (b"\x89PNG\r\n\x1a\n", PNG),
    (b"\xff\xd8\xff", JPEG),
)


def detect_content_type(header: bytes) -> str | None:
    for magic, content_type in _SIGNATURES:
        if header.startswith(magic):
            return content_type
    return None
