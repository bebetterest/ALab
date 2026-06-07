#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def load_project_version(repo_root: Path) -> str:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = str(pyproject["project"]["version"])
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"pyproject.toml project.version must be semver; got {version!r}.")
    return version


def load_init_version(repo_root: Path) -> str:
    init_path = repo_root / "src" / "alab" / "__init__.py"
    module = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    raise ValueError("src/alab/__init__.py must assign string __version__.")


def changelog_has_version(repo_root: Path, filename: str, version: str) -> bool:
    heading = f"## [{version}]"
    return any(line.startswith(heading) for line in (repo_root / filename).read_text(encoding="utf-8").splitlines())


def load_lock_version(repo_root: Path) -> str:
    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    package = next((entry for entry in lock["package"] if entry.get("name") == "alab-cli"), None)
    if not package:
        raise ValueError("uv.lock must include the editable alab-cli package.")
    return str(package["version"])


def validate_version_sync(repo_root: Path) -> list[str]:
    version = load_project_version(repo_root)
    errors: list[str] = []

    init_version = load_init_version(repo_root)
    if init_version != version:
        errors.append(f"src/alab/__init__.py __version__ is {init_version!r}; expected {version!r}.")

    lock_version = load_lock_version(repo_root)
    if lock_version != version:
        errors.append(f"uv.lock alab-cli version is {lock_version!r}; expected {version!r}.")

    for filename in ("CHANGELOG.md", "CHANGELOG_cn.md"):
        if not changelog_has_version(repo_root, filename, version):
            errors.append(f"{filename} must contain a '## [{version}]' release heading.")

    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv or []
    repo_root = Path(args[0]).resolve() if args else REPO_ROOT
    errors = validate_version_sync(repo_root)
    if errors:
        for error in errors:
            print(f"version sync error: {error}", file=sys.stderr)
        return 1
    print(f"Version files are synchronized for {load_project_version(repo_root)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
