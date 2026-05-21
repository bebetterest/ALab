from __future__ import annotations

import fnmatch
import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import AlabError
from .proc import run_cmd

BUILTIN_EXCLUDES = [
    ".git",
    ".alab",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    "node_modules",
    "dist",
    "build",
    "coverage",
]

GITLINK_NEXT_ACTION = "vendor or expand submodule contents before import"


@dataclass(frozen=True)
class SourceCopyResult:
    warnings: list[str]
    imported_files: int


class _FallbackIgnoreSpec:
    def __init__(self, lines: list[str]) -> None:
        self.patterns = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                continue
            self.patterns.append(stripped)

    def match_file(self, rel: str) -> bool:
        rel = rel.strip("/")
        for pattern in self.patterns:
            dir_only = pattern.endswith("/")
            raw = pattern.strip("/")
            if not raw:
                continue
            if dir_only and (rel == raw or rel.startswith(raw + "/")):
                return True
            if "/" not in raw:
                if any(part == raw for part in rel.split("/")) or fnmatch.fnmatch(Path(rel).name, raw):
                    return True
            elif fnmatch.fnmatch(rel, raw) or rel.startswith(raw + "/"):
                return True
        return False


def _ignore_spec_from_lines(lines: list[str]):
    try:
        import pathspec

        if hasattr(pathspec, "GitIgnoreSpec"):
            return pathspec.GitIgnoreSpec.from_lines(lines)
        return pathspec.PathSpec.from_lines("gitignore", lines)
    except Exception:
        return _FallbackIgnoreSpec(lines)


def _load_ignore_spec(root: Path, names: tuple[str, ...]):
    lines: list[str] = []
    for name in names:
        path = root / name
        if path.is_file():
            lines.extend(path.read_text(encoding="utf-8").splitlines())
    return _ignore_spec_from_lines(lines) if lines else None


def _spec_matches(spec, rel: str) -> bool:
    if spec is None:
        return False
    rel = rel.strip("/")
    return bool(spec.match_file(rel) or spec.match_file(rel + "/"))


def _builtin_excluded(rel: str) -> bool:
    parts = rel.split("/")
    for pattern in BUILTIN_EXCLUDES:
        if pattern in parts or fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(parts[-1], pattern):
            return True
    return False


def _always_excluded(rel: str) -> bool:
    return any(part in {".git", ".alab"} for part in rel.split("/"))


def _copy_entry(source_file: Path, dst: Path, rel: str) -> None:
    target = dst / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if source_file.is_symlink():
        if target.exists() or target.is_symlink():
            target.unlink()
        os.symlink(os.readlink(source_file), target)
    else:
        shutil.copy2(source_file, target)


def _git_root_for(src: Path) -> Path | None:
    cwd = src if src.is_dir() else src.parent
    completed = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=cwd, check=False)
    if completed.returncode != 0:
        return None
    try:
        root = Path(completed.stdout.decode("utf-8", errors="replace").strip()).resolve()
    except OSError:
        return None
    return root if src.resolve() == root or root in src.resolve().parents else None


def _git_list(root: Path, args: list[str]) -> set[str]:
    completed = run_cmd(["git", *args, "-z"], cwd=root, check=False)
    if completed.returncode != 0:
        return set()
    text = completed.stdout.decode("utf-8", errors="surrogateescape")
    return {item for item in text.split("\0") if item}


def _git_gitlinks(root: Path) -> set[str]:
    completed = run_cmd(["git", "ls-files", "-s", "-z"], cwd=root, check=False)
    if completed.returncode != 0:
        return set()
    gitlinks: set[str] = set()
    text = completed.stdout.decode("utf-8", errors="surrogateescape")
    for item in text.split("\0"):
        if item.startswith("160000 "):
            parts = item.split("\t", 1)
            if len(parts) == 2:
                gitlinks.add(parts[1])
    return gitlinks


def _under_source(repo_rel: str, git_root: Path, source_root: Path) -> tuple[Path, str] | None:
    candidate = (git_root / repo_rel).resolve()
    if source_root.is_file():
        if candidate == source_root:
            return candidate, source_root.name
        return None
    if candidate == source_root or source_root in candidate.parents:
        return candidate, candidate.relative_to(source_root).as_posix()
    return None


def _copy_git_worktree_source(src: Path, dst: Path, git_root: Path) -> SourceCopyResult:
    tracked = _git_list(git_root, ["ls-files", "--full-name"])
    untracked = _git_list(git_root, ["ls-files", "--others", "--exclude-standard", "--full-name"])
    gitlinks = _git_gitlinks(git_root)
    alabignore = _load_ignore_spec(git_root, (".alabignore",))
    warnings: set[str] = set()
    imported = 0
    for repo_rel in sorted(tracked):
        selected = _under_source(repo_rel, git_root, src)
        if selected is None:
            continue
        if repo_rel in gitlinks:
            raise AlabError("SOURCE_INVALID", "Git submodules/gitlinks are not supported", GITLINK_NEXT_ACTION)
        source_file, rel = selected
        if _always_excluded(rel) or _always_excluded(repo_rel) or not source_file.exists() or source_file.is_dir():
            continue
        if _builtin_excluded(rel) or _builtin_excluded(repo_rel) or _spec_matches(alabignore, repo_rel):
            warnings.add("TRACKED_SENSITIVE_SOURCE_FILE")
        _copy_entry(source_file, dst, rel)
        imported += 1
    for repo_rel in sorted(untracked):
        selected = _under_source(repo_rel, git_root, src)
        if selected is None:
            continue
        source_file, rel = selected
        if _always_excluded(rel) or _always_excluded(repo_rel) or source_file.is_dir():
            continue
        if _builtin_excluded(rel) or _builtin_excluded(repo_rel) or _spec_matches(alabignore, repo_rel):
            continue
        _copy_entry(source_file, dst, rel)
        imported += 1
    if imported == 0:
        warnings.add("SOURCE_EMPTY_AFTER_FILTER")
    return SourceCopyResult(sorted(warnings), imported)


def _copy_plain_source(src: Path, dst: Path) -> SourceCopyResult:
    ignore_spec = _load_ignore_spec(src, (".gitignore", ".alabignore")) if src.is_dir() else None
    imported = 0
    if src.is_file():
        rel = src.name
        if not _builtin_excluded(rel):
            _copy_entry(src, dst, rel)
            imported += 1
    else:
        for root, dirs, files in os.walk(src):
            root_path = Path(root)
            rel_root = root_path.relative_to(src)
            kept_dirs = []
            for directory in dirs:
                rel = (rel_root / directory).as_posix()
                if _always_excluded(rel) or _builtin_excluded(rel) or _spec_matches(ignore_spec, rel):
                    continue
                kept_dirs.append(directory)
            dirs[:] = kept_dirs
            for file_name in files:
                rel = (rel_root / file_name).as_posix()
                if _always_excluded(rel) or _builtin_excluded(rel) or _spec_matches(ignore_spec, rel):
                    continue
                _copy_entry(root_path / file_name, dst, rel)
                imported += 1
    warnings = ["SOURCE_EMPTY_AFTER_FILTER"] if imported == 0 else []
    return SourceCopyResult(warnings, imported)


def copy_filtered_source(src: Path | None, dst: Path, *, empty: bool = False) -> SourceCopyResult:
    dst.mkdir(parents=True, exist_ok=True)
    if empty:
        return SourceCopyResult([], 0)
    if src is None:
        raise AlabError("SOURCE_INVALID", "source path is required")
    src = src.expanduser().resolve()
    if not src.exists():
        raise AlabError("SOURCE_INVALID", f"source path not found: {src}")
    git_root = _git_root_for(src)
    if git_root is not None:
        return _copy_git_worktree_source(src, dst, git_root)
    return _copy_plain_source(src, dst)


def canonical_tree_hash(path: Path) -> str:
    entries: list[str] = []
    for root, dirs, files in os.walk(path):
        dirs.sort()
        files.sort()
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            rel = file_path.relative_to(path).as_posix()
            if file_path.is_symlink():
                target = os.readlink(file_path)
                entries.append(f"L {rel}\0{target}")
            else:
                digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
                mode = "100755" if os.access(file_path, os.X_OK) else "100644"
                entries.append(f"F {mode} {rel}\0{digest}")
    manifest = "\n".join(entries).encode("utf-8")
    return "sha256:" + hashlib.sha256(manifest).hexdigest()


def init_snapshot_repo(workdir: Path, *, author_name: str, author_email: str, message: str) -> str:
    run_cmd(["git", "init"], cwd=workdir)
    run_cmd(["git", "config", "user.name", author_name], cwd=workdir)
    run_cmd(["git", "config", "user.email", author_email], cwd=workdir)
    run_cmd(["git", "config", "commit.gpgsign", "false"], cwd=workdir)
    run_cmd(["git", "add", "-A"], cwd=workdir)
    status = run_cmd(["git", "status", "--porcelain"], cwd=workdir, check=False).stdout
    if status.strip():
        run_cmd(["git", "commit", "-m", message], cwd=workdir)
    else:
        run_cmd(["git", "commit", "--allow-empty", "-m", message], cwd=workdir)
    return (
        run_cmd(["git", "rev-parse", "HEAD"], cwd=workdir)
        .stdout.decode("utf-8", errors="replace")
        .strip()
    )


def reject_gitlinks(workdir: Path) -> None:
    output = run_cmd(["git", "ls-files", "-s"], cwd=workdir).stdout.decode("utf-8", errors="replace")
    for line in output.splitlines():
        if line.startswith("160000 "):
            raise AlabError("SOURCE_INVALID", "Git submodules/gitlinks are not supported", GITLINK_NEXT_ACTION)
