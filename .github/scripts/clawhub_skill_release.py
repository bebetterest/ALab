#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLAWHUB_REGISTRY = "https://clawhub.ai"
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


@dataclass(frozen=True)
class SkillRelease:
    slug: str
    path: str
    display_name: str
    changelog: str
    frontmatter_name: str | None = None


SKILL_RELEASES: tuple[SkillRelease, ...] = (
    SkillRelease(
        slug="alab-skills",
        path="ALabSkills",
        display_name="ALab Skills",
        changelog="Release the ALab role skill bundle.",
    ),
    SkillRelease(
        slug="alab-global-admin-skill",
        path="ALabSkills/alab-global-admin",
        display_name="ALab Global Admin",
        changelog="Release the ALab root administration role skill.",
        frontmatter_name="alab-global-admin",
    ),
    SkillRelease(
        slug="alab-project-controller",
        path="ALabSkills/alab-project-controller",
        display_name="ALab Project Controller",
        changelog="Release the ALab project coordination role skill.",
    ),
    SkillRelease(
        slug="alab-experiment-worker",
        path="ALabSkills/alab-experiment-worker",
        display_name="ALab Experiment Worker",
        changelog="Release the ALab experiment worktree role skill.",
    ),
)


VersionExists = Callable[[str, str, str], bool]


def load_project_version(repo_root: Path) -> str:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    if not SEMVER_RE.fullmatch(version):
        raise ValueError(f"ClawHub skill versions must be semver; got {version!r}.")
    return version


def read_frontmatter_name(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"Missing required skill file: {skill_md}")

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Missing YAML frontmatter in {skill_md}")

    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"Unclosed YAML frontmatter in {skill_md}") from exc

    for line in frontmatter.splitlines():
        match = re.fullmatch(r"name:\s*['\"]?([a-z0-9][a-z0-9-]*)['\"]?", line.strip())
        if match:
            return match.group(1)

    raise ValueError(f"Missing frontmatter name in {skill_md}")


def validate_releases(repo_root: Path) -> tuple[SkillRelease, ...]:
    seen_slugs: set[str] = set()
    for release in SKILL_RELEASES:
        if release.slug in seen_slugs:
            raise ValueError(f"Duplicate ClawHub skill slug: {release.slug}")
        seen_slugs.add(release.slug)

        skill_dir = repo_root / release.path
        actual_name = read_frontmatter_name(skill_dir)
        expected_name = release.frontmatter_name or release.slug
        if actual_name != expected_name:
            raise ValueError(
                f"{skill_dir / 'SKILL.md'} has name {actual_name!r}; expected {expected_name!r}."
            )
    return SKILL_RELEASES


def skill_version_url(base_url: str, slug: str, version: str) -> str:
    base = base_url.rstrip("/")
    return (
        f"{base}/api/v1/skills/"
        f"{urllib.parse.quote(slug, safe='')}/versions/{urllib.parse.quote(version, safe='')}"
    )


def clawhub_version_exists(base_url: str, slug: str, version: str) -> bool:
    request = urllib.request.Request(
        skill_version_url(base_url, slug, version),
        headers={
            "Accept": "application/json",
            "User-Agent": "ALab-GitHub-Actions",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30):
            return True
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        raise


def build_plan(
    repo_root: Path,
    base_url: str,
    *,
    version: str | None = None,
    version_exists: VersionExists = clawhub_version_exists,
) -> dict[str, object]:
    resolved_version = version or load_project_version(repo_root)
    releases = validate_releases(repo_root)
    skills: list[dict[str, object]] = []

    for release in releases:
        exists = version_exists(base_url, release.slug, resolved_version)
        skills.append(
            {
                "slug": release.slug,
                "path": release.path,
                "display_name": release.display_name,
                "version": resolved_version,
                "exists": exists,
                "should_publish": not exists,
            }
        )

    missing_slugs = [str(skill["slug"]) for skill in skills if skill["should_publish"]]
    return {
        "version": resolved_version,
        "base_url": base_url.rstrip("/"),
        "should_publish": bool(missing_slugs),
        "missing_slugs": missing_slugs,
        "skills": skills,
    }


def write_github_output(path: str | None, plan: dict[str, object]) -> None:
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"version={plan['version']}\n")
        output.write(f"should_publish={str(plan['should_publish']).lower()}\n")
        output.write(f"missing_slugs={','.join(plan['missing_slugs'])}\n")


def normalize_owner(owner: str | None) -> str:
    if owner is None:
        return ""
    return owner.strip().removeprefix("@").lower()


def publish_missing_skills(repo_root: Path, plan: dict[str, object], *, owner: str, clawhub_bin: str) -> None:
    if not plan["should_publish"]:
        print(f"ClawHub already has all ALab skill versions for {plan['version']}; skipping publish.")
        return

    owner_args = ["--owner", owner] if owner else []
    releases_by_slug = {release.slug: release for release in validate_releases(repo_root)}

    for skill in plan["skills"]:
        if not skill["should_publish"]:
            print(f"ClawHub already has {skill['slug']} {skill['version']}; skipping.")
            continue

        release = releases_by_slug[str(skill["slug"])]
        command = [
            clawhub_bin,
            "skill",
            "publish",
            str(repo_root / release.path),
            "--slug",
            release.slug,
            "--name",
            release.display_name,
            "--version",
            str(plan["version"]),
            "--changelog",
            release.changelog,
            *owner_args,
        ]
        print(f"Publishing {release.slug} {plan['version']} to ClawHub.")
        subprocess.run(command, check=True)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan and publish ALab skills to ClawHub.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root. Defaults to the checkout containing this script.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CLAWHUB_REGISTRY")
        or os.environ.get("CLAWHUB_BASE_URL")
        or DEFAULT_CLAWHUB_REGISTRY,
        help="ClawHub registry base URL.",
    )
    parser.add_argument(
        "--github-output",
        default=os.environ.get("GITHUB_OUTPUT"),
        help="Optional GitHub Actions output file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="Check which skill versions are missing.")
    plan_parser.add_argument("--plan-output", type=Path, help="Optional JSON plan output path.")

    publish_parser = subparsers.add_parser("publish", help="Publish missing skill versions.")
    publish_parser.add_argument(
        "--owner",
        default=os.environ.get("CLAWHUB_OWNER", ""),
        help="Optional ClawHub owner handle. Defaults to CLAWHUB_OWNER.",
    )
    publish_parser.add_argument(
        "--clawhub-bin",
        default=os.environ.get("CLAWHUB_BIN", "clawhub"),
        help="ClawHub CLI executable.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    repo_root = args.repo_root.resolve()
    base_url = args.base_url.rstrip("/")
    plan = build_plan(repo_root, base_url)
    write_github_output(args.github_output, plan)

    if args.command == "plan":
        body = json.dumps(plan, indent=2, sort_keys=True)
        if args.plan_output:
            args.plan_output.write_text(body + "\n", encoding="utf-8")
        print(body)
        return 0

    if args.command == "publish":
        publish_missing_skills(
            repo_root,
            plan,
            owner=normalize_owner(args.owner),
            clawhub_bin=args.clawhub_bin,
        )
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
