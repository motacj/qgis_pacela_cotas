#!/usr/bin/env python3
"""Build the distributable QGIS plugin ZIP from the repository source."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

PLUGIN_NAME = "qgis_pacela_cotas"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DIST_DIRECTORY = REPOSITORY_ROOT / "dist"
ARCHIVE_PATH = DIST_DIRECTORY / f"{PLUGIN_NAME}.zip"

EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".idea",
    ".pytest_cache",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "tests",
    "tools",
}
EXCLUDED_NAMES = {".coverage", ".DS_Store", ".gitignore", "Thumbs.db"}
EXCLUDED_SUFFIXES = {".gpkg", ".pyc", ".pyo", ".qgs", ".qgz", ".zip"}


def package_files() -> list[Path]:
    files = []
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPOSITORY_ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def build() -> Path:
    DIST_DIRECTORY.mkdir(exist_ok=True)
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with zipfile.ZipFile(ARCHIVE_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in package_files():
            relative = source.relative_to(REPOSITORY_ROOT)
            archive.write(source, Path(PLUGIN_NAME) / relative)
    return ARCHIVE_PATH


if __name__ == "__main__":
    archive_path = build()
    print(f"Built {archive_path} ({archive_path.stat().st_size} bytes)")
