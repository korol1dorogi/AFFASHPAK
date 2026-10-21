"""Deep content checks of an upload, after the magic bytes (signatures.py).

The server never opens, renders or executes uploads: no PDF or image library parses them, they
are stored under random names outside any public path and served only as attachments with
nosniff (views.py). These checks protect the people who open the files — a bank officer's PDF
viewer runs embedded JavaScript, launches attachments, follows auto-actions — and stop polyglots
(a valid header with HTML, a script or an executable appended).

Pure functions over bytes, stdlib only. A file is rejected when it is malformed, encrypted (its
content cannot be inspected) or carries active content.
"""

import re
import struct
import zlib

from apps.documents.signatures import JPEG, PDF, PNG

# PDF name objects that run code, open other files or act without the user (ISO 32000).
# /OpenAction alone is allowed: LibreOffice and scanners use it to open page 1; what it could
# run (JavaScript, Launch) is rejected wherever it appears.
PDF_ACTIVE_NAMES = frozenset(
    {
        b"JavaScript",
        b"JS",
        b"Launch",
        b"EmbeddedFile",
        b"EmbeddedFiles",
        b"RichMedia",
        b"XFA",
        b"SubmitForm",
        b"ImportData",
        b"GoToE",
        b"AA",
    }
)
# Markup and scripts have no business inside a scan or a photo of a document.
MARKUP = re.compile(rb"<\s*(script|html|body|iframe|svg|object|embed)\b|<\?php|javascript:", re.I)

_PDF_HEADER = re.compile(rb"\A%PDF-(1\.[0-7]|2\.0)")
_PDF_NAME = re.compile(rb"/([^\x00\t\n\f\r /<>\[\]()%{}]+)")
_PDF_HEX = re.compile(rb"#([0-9A-Fa-f]{2})")
_PDF_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)
_EOF_TAIL = 1024  # %%EOF must close the file; only whitespace may follow
_INFLATE_BUDGET = 64 * 1024 * 1024  # total bytes we agree to inflate: a zip bomb stops here

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class UnsafeFile(ValueError):
    """The message is shown to the client (Russian, no internals)."""


def inspect(content_type: str, data: bytes) -> None:
    """Raise UnsafeFile when the file must not be stored."""
    if MARKUP.search(data):
        raise UnsafeFile("внутри файла есть HTML или скрипт")
    if content_type == PDF:
        _inspect_pdf(data)
    elif content_type == PNG:
        _inspect_png(data)
    elif content_type == JPEG:
        _inspect_jpeg(data)
    else:  # signatures.py and this module must agree on the allow-list
        raise UnsafeFile("неизвестный тип файла")


def _inspect_pdf(data: bytes) -> None:
    if not _PDF_HEADER.match(data):
        raise UnsafeFile("повреждённый заголовок PDF")
    tail = data[-_EOF_TAIL:].rstrip()
    if not tail.endswith(b"%%EOF"):
        raise UnsafeFile("после конца PDF дописаны лишние данные")
    names = _pdf_names(data)
    if b"Encrypt" in names:
        raise UnsafeFile("PDF защищён паролем — его содержимое нельзя проверить")
    budget = _INFLATE_BUDGET
    for match in _PDF_STREAM.finditer(data):
        inflated, budget = _inflate(match.group(1), budget)
        if inflated:
            if MARKUP.search(inflated):
                raise UnsafeFile("внутри файла есть HTML или скрипт")
            names |= _pdf_names(inflated)
    active = sorted(name.decode("latin-1") for name in names & PDF_ACTIVE_NAMES)
    if active:
        raise UnsafeFile("в PDF есть активное содержимое (" + ", ".join(active) + ")")


def _pdf_names(data: bytes) -> set[bytes]:
    """Name objects with #xx escapes decoded: /J#61vaScript is /JavaScript."""
    return {
        _PDF_HEX.sub(lambda hex_: bytes([int(hex_.group(1), 16)]), name)
        for name in _PDF_NAME.findall(data)
    }


def _inflate(raw: bytes, budget: int) -> tuple[bytes, int]:
    """FlateDecode a stream within the remaining budget; not a zlib stream → nothing to scan."""
    if budget <= 0:
        raise UnsafeFile("PDF распаковывается в слишком большой объём")
    try:
        inflater = zlib.decompressobj()
        inflated = inflater.decompress(raw, budget)
    except zlib.error:
        return b"", budget
    if inflater.unconsumed_tail:
        raise UnsafeFile("PDF распаковывается в слишком большой объём")
    return inflated, budget - len(inflated)


def _inspect_png(data: bytes) -> None:
    position, first = len(_PNG_SIGNATURE), True
    while True:
        if position + 12 > len(data):
            raise UnsafeFile("PNG обрывается")
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        end = position + 12 + length
        if end > len(data):
            raise UnsafeFile("PNG обрывается")
        body = data[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", data[position + 8 + length : end])
        if zlib.crc32(kind + body) != crc:
            raise UnsafeFile("повреждённый PNG")
        if first and kind != b"IHDR":
            raise UnsafeFile("повреждённый PNG")
        first = False
        position = end
        if kind == b"IEND":
            break
    if position != len(data):
        raise UnsafeFile("после конца PNG дописаны лишние данные")


def _inspect_jpeg(data: bytes) -> None:
    if not data.rstrip(b"\x00").endswith(b"\xff\xd9"):
        raise UnsafeFile("после конца JPEG дописаны лишние данные или файл оборван")
