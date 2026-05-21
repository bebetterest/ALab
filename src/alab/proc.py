from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from .errors import AlabError


def run_cmd(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
    timeout: int | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            list(args),
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env is not None else None,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AlabError("GIT_ERROR", f"executable not found: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise AlabError("RUNNER_TIMEOUT", "process timed out") from exc
    if check and completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        reason = stderr or f"command failed with exit code {completed.returncode}"
        code = "GIT_ERROR" if args and args[0] == "git" else "RUNNER_ERROR"
        raise AlabError(code, reason)
    return completed
