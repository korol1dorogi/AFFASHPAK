"""User-supplied file names are display-only. They never become a storage path."""

from pathlib import PurePosixPath

from apps.documents.signatures import EXTENSIONS

_MAX_ORIGINAL_LENGTH = 255
_MAX_STEM_LENGTH = 180
_FORBIDDEN = str.maketrans(dict.fromkeys('<>:"/\\|?*', "_"))


def safe_original_name(raw: str | None) -> str:
    """Basename only, with control characters removed so it cannot break a header."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(character for character in name if character.isprintable())
    name = name.strip()
    if not name or name in {".", ".."}:
        return "document"
    return name[:_MAX_ORIGINAL_LENGTH]


def attachment_filename(original_name: str, content_type: str) -> str:
    """Download name whose extension matches the detected type, not the client's.

    Characters no file system accepts (and that only markup needs: < > " …) become «_».
    """
    extension = EXTENSIONS[content_type]
    stem = PurePosixPath(original_name).stem.translate(_FORBIDDEN).strip().strip(".")
    if not stem or stem in {".", ".."}:
        stem = "document"
    return f"{stem[:_MAX_STEM_LENGTH]}.{extension}"
