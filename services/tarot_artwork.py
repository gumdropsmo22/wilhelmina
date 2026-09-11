from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path

from services.tarot import DrawnCard, Orientation, TarotCard

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTWORK_ROOT = PROJECT_ROOT / "assets" / "tarot"
ARTWORK_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(frozen=True)
class PreparedArtwork:
    """One optional card image prepared for Discord attachment."""

    filename: str
    data: bytes
    visually_reversed: bool


def artwork_root() -> Path:
    """Return the configured Tarot artwork root."""

    raw = os.getenv("TAROT_ARTWORK_DIR", "").strip()
    if not raw:
        return DEFAULT_ARTWORK_ROOT
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def find_artwork(card: TarotCard, *, root: Path | None = None) -> Path | None:
    """Find an artwork file for one card without making images a runtime requirement."""

    base = root or artwork_root()
    for extension in ARTWORK_EXTENSIONS:
        candidate = base / f"{card.artwork_key}{extension}"
        if candidate.is_file():
            return candidate
    return None


def _rotated_bytes(path: Path) -> bytes | None:
    """Rotate an image 180 degrees when Pillow is installed; otherwise return None."""

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(path) as image:
            rotated = image.rotate(180, expand=True)
            output = io.BytesIO()
            format_name = (image.format or path.suffix.lstrip(".") or "PNG").upper()
            if format_name == "JPG":
                format_name = "JPEG"
            rotated.save(output, format=format_name)
            return output.getvalue()
    except (OSError, ValueError):
        return None


def prepare_artwork(drawn: DrawnCard, *, root: Path | None = None) -> PreparedArtwork | None:
    """Load optional artwork and visually reverse it when the optional image plugin exists."""

    path = find_artwork(drawn.card, root=root)
    if path is None:
        return None

    try:
        original = path.read_bytes()
    except OSError:
        return None

    visually_reversed = False
    data = original
    if drawn.orientation is Orientation.REVERSED:
        rotated = _rotated_bytes(path)
        if rotated is not None:
            data = rotated
            visually_reversed = True

    filename = f"{drawn.card.card_id}_{drawn.orientation.value}{path.suffix.lower()}"
    return PreparedArtwork(filename=filename, data=data, visually_reversed=visually_reversed)
