from __future__ import annotations

from pathlib import Path

from .errors import AlabError
from .service_args import command_arg, require_options_at_most_once


def _assert_utf8_max_bytes(label: str, value: str, max_bytes: int) -> None:
    if len(value.encode("utf-8")) > max_bytes:
        raise AlabError("CONFIG_INVALID", f"{label} exceeds {max_bytes} bytes")


def _read_text_input_file(path_value: str, label: str) -> str:
    path = Path(path_value)
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file not found") from exc
    except IsADirectoryError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file is a directory") from exc
    except UnicodeDecodeError as exc:
        raise AlabError("CONFIG_INVALID", f"{label} file must be UTF-8") from exc
    except OSError as exc:
        reason = exc.strerror or str(exc)
        raise AlabError("CONFIG_INVALID", f"{label} file cannot be read: {reason}") from exc


def _assert_non_empty_text(label: str, value: str) -> None:
    if not value:
        raise AlabError("CONFIG_INVALID", f"{label} must be non-empty")


def _assert_display_name(label: str, value: str) -> None:
    _assert_non_empty_text(label, value)
    _assert_utf8_max_bytes(label, value, 120)


def _lifecycle_reason(args: list[str]) -> str | None:
    require_options_at_most_once(args, ("--reason",))
    reason = command_arg(args, "--reason")
    if reason is not None:
        _assert_utf8_max_bytes("reason", reason, 65536)
    return reason
