from __future__ import annotations

import re
from datetime import UTC, datetime

RFC3339_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_rfc3339_utc(value: str) -> str:
    if not (value.endswith("Z") or "+" in value[10:] or "-" in value[10:]):
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "timestamps must include Z or a numeric offset")
    if not RFC3339_RE.match(value):
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "invalid RFC 3339 timestamp")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "invalid RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "timestamps must include Z or a numeric offset")
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
