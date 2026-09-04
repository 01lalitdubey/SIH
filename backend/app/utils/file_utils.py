import re
import uuid
from pathlib import Path

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
    # Browsers/tools don't always send a specific TIFF mime type for .tif.
    "application/octet-stream",
}

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")


def get_extension(original_filename: str) -> str:
    return Path(original_filename).suffix.lower()


def is_allowed_upload(original_filename: str, content_type: str | None) -> bool:
    ext_ok = get_extension(original_filename) in ALLOWED_EXTENSIONS
    type_ok = content_type is None or content_type in ALLOWED_CONTENT_TYPES
    return ext_ok and type_ok


def sanitize_filename(original_filename: str) -> str:
    """Strips path components and unsafe characters from a client-supplied name."""
    name = Path(original_filename).name
    return _UNSAFE_CHARS.sub("_", name) or "upload"


def generate_stored_filename(original_filename: str) -> str:
    ext = get_extension(original_filename)
    return f"{uuid.uuid4().hex}{ext}"
