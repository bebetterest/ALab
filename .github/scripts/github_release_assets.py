#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from clawhub_skill_release import (  # noqa: E402
    SKILL_RELEASES,
    load_project_version,
    validate_releases,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PYPI_BASE_URL = "https://pypi.org/pypi"
CHANGELOG_HEADING_RE = re.compile(r"^##\s+\[?v?(?P<version>[^\]\s]+)\]?(?:\s+-\s+.*)?$")


def load_project_name(repo_root: Path) -> str:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject["project"]["name"])


def normalized_package_name(package_name: str) -> str:
    return re.sub(r"[-_.]+", "-", package_name).lower()


def safe_filename(filename: str) -> str:
    if not filename or "/" in filename or "\\" in filename:
        raise ValueError(f"Unsafe release asset filename from PyPI: {filename!r}")
    return filename


def extract_release_notes(repo_root: Path, version: str) -> str:
    lines = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    start = None
    for index, line in enumerate(lines):
        match = CHANGELOG_HEADING_RE.match(line.strip())
        if match and match.group("version") == version:
            start = index + 1
            break

    body_lines: list[str] = []
    if start is not None:
        for line in lines[start:]:
            if line.startswith("## "):
                break
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return body or f"See CHANGELOG.md for {version} release details."


def pypi_release_url(pypi_base_url: str, package_name: str) -> str:
    base_url = pypi_base_url.rstrip("/")
    normalized_name = normalized_package_name(package_name)
    return f"{base_url}/{urllib.parse.quote(normalized_name)}/json"


def pypi_version_url(pypi_base_url: str, package_name: str, version: str) -> str:
    base_url = pypi_base_url.rstrip("/")
    normalized_name = normalized_package_name(package_name)
    return f"{base_url}/{urllib.parse.quote(normalized_name)}/{urllib.parse.quote(version)}/json"


def load_pypi_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=30) as response:
        return dict(json.load(response))


def pypi_release_files(
    pypi_base_url: str,
    package_name: str,
    version: str,
    *,
    attempts: int = 6,
    delay_seconds: int = 10,
) -> list[dict[str, object]]:
    version_url = pypi_version_url(pypi_base_url, package_name, version)
    project_url = pypi_release_url(pypi_base_url, package_name)
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            version_payload = load_pypi_json(version_url)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            last_error = RuntimeError(f"PyPI package {package_name!r} has no version {version!r}.")
        else:
            files = version_payload.get("urls", [])
            if files:
                return list(files)
            last_error = RuntimeError(f"PyPI package {package_name!r} has no files for version {version!r}.")

        try:
            project_payload = load_pypi_json(project_url)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            if last_error is None:
                last_error = RuntimeError(f"PyPI package {package_name!r} does not exist.")
        else:
            releases = project_payload.get("releases", {})
            files = releases.get(version, []) if isinstance(releases, dict) else []
            if files:
                return list(files)
            if last_error is None:
                last_error = RuntimeError(f"PyPI package {package_name!r} has no files for version {version!r}.")

        if attempt < attempts:
            print(f"Waiting for PyPI files for {package_name} {version} ({attempt}/{attempts}).")
            time.sleep(delay_seconds)

    assert last_error is not None
    raise last_error


def download_pypi_distributions(
    output_dir: Path,
    *,
    package_name: str,
    version: str,
    pypi_base_url: str = DEFAULT_PYPI_BASE_URL,
) -> list[Path]:
    assets: list[Path] = []
    for file_info in pypi_release_files(pypi_base_url, package_name, version):
        filename = safe_filename(str(file_info["filename"]))
        url = str(file_info["url"])
        destination = output_dir / filename
        expected_sha256 = str(file_info.get("digests", {}).get("sha256", ""))

        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()

        if expected_sha256:
            actual_sha256 = hashlib.sha256(data).hexdigest()
            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    f"Downloaded {filename} has sha256 {actual_sha256}; expected {expected_sha256}."
                )

        destination.write_bytes(data)
        assets.append(destination)

    return assets


def write_zip_file(archive: zipfile.ZipFile, source: Path, archive_name: str) -> None:
    info = zipfile.ZipInfo(archive_name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o100644 & 0xFFFF) << 16
    archive.writestr(info, source.read_bytes())


def package_skill_archives(repo_root: Path, output_dir: Path, version: str) -> list[Path]:
    validate_releases(repo_root)
    assets: list[Path] = []

    for release in SKILL_RELEASES:
        source_dir = repo_root / release.path
        archive_path = output_dir / f"{release.slug}-{version}.zip"
        archive_root = Path(f"{release.slug}-{version}")
        with zipfile.ZipFile(archive_path, "w") as archive:
            for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
                archive_name = archive_root / source.relative_to(source_dir)
                write_zip_file(archive, source, archive_name.as_posix())
        assets.append(archive_path)

    return assets


def write_github_output(path: str | None, *, version: str, assets: list[Path]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"version={version}\n")
        output.write(f"tag=v{version}\n")
        output.write(f"asset_count={len(assets)}\n")


def prepare_release_assets(
    repo_root: Path,
    output_dir: Path,
    notes_output: Path,
    *,
    pypi_base_url: str,
) -> list[Path]:
    version = load_project_version(repo_root)
    package_name = load_project_name(repo_root)
    output_dir.mkdir(parents=True, exist_ok=True)

    notes = extract_release_notes(repo_root, version)
    notes_output.write_text(notes + "\n", encoding="utf-8")

    assets = [
        *download_pypi_distributions(
            output_dir,
            package_name=package_name,
            version=version,
            pypi_base_url=pypi_base_url,
        ),
        *package_skill_archives(repo_root, output_dir, version),
    ]
    for asset in assets:
        print(asset)
    return assets


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare ALab GitHub Release assets.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root. Defaults to the checkout containing this script.",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Optional GitHub Actions output file.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare release notes and asset files.")
    prepare_parser.add_argument(
        "--asset-output-dir",
        type=Path,
        default=Path("release-assets"),
        help="Directory for release asset files.",
    )
    prepare_parser.add_argument(
        "--notes-output",
        type=Path,
        default=Path("release-notes.md"),
        help="Release notes output file.",
    )
    prepare_parser.add_argument(
        "--pypi-base-url",
        default=os.environ.get("PYPI_BASE_URL", DEFAULT_PYPI_BASE_URL),
        help="PyPI JSON API base URL.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = args.repo_root.resolve()

    if args.command == "prepare":
        assets = prepare_release_assets(
            repo_root,
            args.asset_output_dir,
            args.notes_output,
            pypi_base_url=args.pypi_base_url,
        )
        write_github_output(args.github_output, version=load_project_version(repo_root), assets=assets)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
