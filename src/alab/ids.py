from __future__ import annotations

import base64
import re
import secrets
import unicodedata


def random_suffix() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return slug or fallback


def new_id(prefix: str, name: str | None = None) -> str:
    hint = slugify(name, prefix) if name else prefix
    return f"{prefix}-{hint}-{random_suffix()}"


def require_complete_id(value: str, prefix: str | None = None) -> str:
    if not value or value.endswith("-") or len(value) < 8:
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "object ids must be complete")
    if prefix and not value.startswith(prefix + "-"):
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", f"expected {prefix} id")
    separator_index = len(value) - 23
    if (
        separator_index <= 0
        or (prefix is not None and separator_index <= len(prefix))
        or value[separator_index] != "-"
        or not re.fullmatch(r"[A-Za-z0-9_-]{22}", value[separator_index + 1 :])
    ):
        from .errors import AlabError

        raise AlabError("CONFIG_INVALID", "object ids must be complete")
    return value
