import shutil
from pathlib import Path

from app.services.smart import typography_engine as te

_FONT_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "services" / "smart" / "fonts"


def test_font_path_prefers_valid_bundled_font(monkeypatch, tmp_path: Path) -> None:
    bundled_dir = tmp_path / "bundled"
    cache_dir = tmp_path / "cache"
    bundled_dir.mkdir()
    cache_dir.mkdir()

    shutil.copy(
        _FONT_FIXTURES_DIR / "Anton-Regular.ttf",
        bundled_dir / "Anton-Regular.ttf",
    )

    monkeypatch.setattr(te, "_BUNDLED_FONTS_DIR", bundled_dir)
    monkeypatch.setattr(te, "FONTS_DIR", cache_dir)
    monkeypatch.setattr(te, "_resolved_cache", {})

    resolved = te.font_path("anton")

    assert resolved == bundled_dir / "Anton-Regular.ttf"
