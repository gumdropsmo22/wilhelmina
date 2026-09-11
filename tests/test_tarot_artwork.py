from __future__ import annotations

from pathlib import Path

from services import tarot, tarot_artwork


def _drawn(*, orientation: tarot.Orientation) -> tarot.DrawnCard:
    return tarot.DrawnCard(position="Card", card=tarot.CARD_BY_ID["major_00_the_fool"], orientation=orientation)


def test_missing_artwork_is_a_clean_noop(tmp_path: Path):
    assert tarot_artwork.prepare_artwork(_drawn(orientation=tarot.Orientation.UPRIGHT), root=tmp_path) is None


def test_upright_artwork_is_loaded_without_pillow(tmp_path: Path):
    target = tmp_path / "major" / "00_the_fool.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"source")
    prepared = tarot_artwork.prepare_artwork(_drawn(orientation=tarot.Orientation.UPRIGHT), root=tmp_path)
    assert prepared is not None
    assert prepared.data == b"source"
    assert prepared.visually_reversed is False


def test_reversed_artwork_uses_optional_rotation_when_available(monkeypatch, tmp_path: Path):
    target = tmp_path / "major" / "00_the_fool.webp"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"source")
    monkeypatch.setattr(tarot_artwork, "_rotated_bytes", lambda path: b"rotated")
    prepared = tarot_artwork.prepare_artwork(_drawn(orientation=tarot.Orientation.REVERSED), root=tmp_path)
    assert prepared is not None
    assert prepared.data == b"rotated"
    assert prepared.visually_reversed is True


def test_reversed_artwork_survives_without_rotation_plugin(monkeypatch, tmp_path: Path):
    target = tmp_path / "major" / "00_the_fool.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"source")
    monkeypatch.setattr(tarot_artwork, "_rotated_bytes", lambda path: None)
    prepared = tarot_artwork.prepare_artwork(_drawn(orientation=tarot.Orientation.REVERSED), root=tmp_path)
    assert prepared is not None
    assert prepared.data == b"source"
    assert prepared.visually_reversed is False
