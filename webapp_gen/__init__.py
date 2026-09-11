"""webapp-gen GUI package."""

from pathlib import Path


def _read_version() -> str:
    version_file = Path(__file__).resolve().parent.parent / "version.md"
    return version_file.read_text(encoding="utf-8").strip()


__version__ = _read_version()
