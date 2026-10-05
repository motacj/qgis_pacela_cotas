#!/usr/bin/env python3
"""Local preflight checks for a QGIS plugin repository ZIP."""

from __future__ import annotations

import argparse
import ast
import configparser
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_PACKAGE_BYTES = 25 * 1024 * 1024
REQUIRED_METADATA = (
    "name",
    "qgisMinimumVersion",
    "description",
    "about",
    "version",
    "author",
    "email",
    "license",
    "repository",
)
REQUIRED_LINKS = ("homepage", "repository", "tracker")
BANNED_SUFFIXES = {".dll", ".dylib", ".exe", ".jar", ".pyd", ".so"}
BANNED_PARTS = {".git", "__MACOSX", "__pycache__"}
NETWORK_IMPORTS = {"http", "requests", "socket", "urllib", "urllib2"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(?:api[_-]?key|password|secret|token)\s*=\s*['\"][^'\"]{8,}['\"]"),
)
LEGACY_ENUM_PATTERNS = (
    re.compile(r"QDialogButtonBox\.(?:Ok|Cancel)\b"),
    re.compile(r"QDialog\.Accepted\b"),
    re.compile(r"QgsWkbTypes\.PolygonGeometry\b"),
    re.compile(r"QStandardPaths\.DocumentsLocation\b"),
    re.compile(
        r"QgsVectorFileWriter\."
        r"(?:CreateOrOverwriteLayer|CreateOrOverwriteFile|NoError)\b"
    ),
)
CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def check_python(path: str, source: str, errors: list[str], warnings: list[str]) -> None:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        errors.append(f"Python syntax error in {path}: {exc}")
        return

    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    found_network = sorted(imported_roots & NETWORK_IMPORTS)
    if found_network:
        warnings.append(f"Network imports in {path}: {', '.join(found_network)}")
    if max((len(line) for line in source.splitlines()), default=0) > 119:
        warnings.append(f"Line longer than 119 characters in {path}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(source):
            errors.append(f"Possible credential or private key in {path}")
    for pattern in LEGACY_ENUM_PATTERNS:
        if pattern.search(source):
            errors.append(f"Legacy enum access rejected by QGIS in {path}: {pattern.pattern}")


def validate(archive: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not archive.is_file():
        return [f"Package not found: {archive}"], warnings
    if archive.stat().st_size > MAX_PACKAGE_BYTES:
        errors.append("Package exceeds the official 25 MB limit")

    try:
        with zipfile.ZipFile(archive) as package:
            bad_member = package.testzip()
            if bad_member:
                errors.append(f"Corrupt ZIP member: {bad_member}")
            names = [name for name in package.namelist() if name and not name.endswith("/")]
            roots = {PurePosixPath(name).parts[0] for name in names}
            if len(roots) != 1:
                errors.append("ZIP must contain exactly one top-level plugin directory")
                return errors, warnings
            root = next(iter(roots))
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", root):
                errors.append(f"Invalid ASCII plugin directory name: {root}")

            for name in names:
                relative = PurePosixPath(name)
                if relative.is_absolute() or ".." in relative.parts:
                    errors.append(f"Unsafe ZIP path: {name}")
                if BANNED_PARTS & set(relative.parts):
                    errors.append(f"Forbidden cache or hidden directory: {name}")
                if relative.suffix.lower() in BANNED_SUFFIXES:
                    errors.append(f"Compiled binary is not allowed: {name}")

            required_files = {
                f"{root}/__init__.py",
                f"{root}/metadata.txt",
                f"{root}/LICENSE",
                f"{root}/README.md",
            }
            missing = sorted(required_files - set(names))
            if missing:
                errors.append("Missing required/documentation files: " + ", ".join(missing))

            metadata_name = f"{root}/metadata.txt"
            if metadata_name not in names:
                return errors, warnings
            metadata_text = package.read(metadata_name).decode("utf-8")
            metadata = configparser.ConfigParser(interpolation=None)
            metadata.optionxform = str
            metadata.read_string(metadata_text)
            if not metadata.has_section("general"):
                errors.append("metadata.txt has no [general] section")
                return errors, warnings
            section = metadata["general"]
            for key in REQUIRED_METADATA:
                if not section.get(key, "").strip():
                    errors.append(f"Required metadata is empty: {key}")
            email = section.get("email", "").strip()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                errors.append("Author email is not valid")
            for key in REQUIRED_LINKS:
                value = section.get(key, "").strip()
                if not value.startswith(("https://", "http://")):
                    errors.append(f"Missing or invalid public URL: {key}")
            if section.get("category") not in {"Vector", "Raster", "Database", "Mesh", "Web"}:
                errors.append("Invalid plugin category")
            for key in ("experimental", "deprecated", "server", "hasProcessingProvider"):
                if section.get(key, "").lower() not in {"true", "false"}:
                    errors.append(f"Metadata {key} must be True or False")
            if not re.fullmatch(r"\d+(?:\.\d+){1,2}", section.get("version", "")):
                errors.append("Version must use dotted numeric notation")
            if "<" in section.get("description", "") or ">" in section.get("description", ""):
                errors.append("HTML is not allowed in the description")
            if "parcel" not in section.get("description", "").lower():
                warnings.append("Short English description could not be confirmed")
            icon = section.get("icon", "").strip()
            if PurePosixPath(icon).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                errors.append("Metadata icon must be PNG or JPEG")
            if icon and f"{root}/{icon}" not in names:
                errors.append(f"Referenced icon is missing: {icon}")

            init_name = f"{root}/__init__.py"
            if init_name in names:
                init_source = package.read(init_name).decode("utf-8")
                init_tree = ast.parse(init_source, filename=init_name)
                if not any(
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "classFactory"
                    for node in init_tree.body
                ):
                    errors.append("__init__.py does not define classFactory")

            for name in names:
                if name.endswith(".py"):
                    source = package.read(name).decode("utf-8")
                    if any(marker in source for marker in CONFLICT_MARKERS):
                        errors.append(f"Unresolved merge conflict in {name}")
                    check_python(name, source, errors, warnings)

            if any(marker in metadata_text for marker in CONFLICT_MARKERS):
                errors.append("Unresolved merge conflict in metadata.txt")
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        errors.append(f"Cannot validate package: {exc}")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    errors, warnings = validate(args.archive)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASSED: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
