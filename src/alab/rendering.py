from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MultilineText:
    text: str | None


Scalar = str | int | float | bool | None
Value = Scalar | list[Scalar] | MultilineText


@dataclass
class ResultBlock:
    object_type: str
    fields: list[tuple[str, Value]] = field(default_factory=list)


def multiline_text(value: str | None) -> MultilineText:
    return MultilineText(value)


def _render_scalar(value: Scalar) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_field(label: str, value: Value) -> list[str]:
    if isinstance(value, MultilineText):
        if value.text is None:
            return [f"{label}: none"]
        lines = [f"{label}:"]
        if value.text == "":
            lines.append("  [empty]")
        else:
            for line in value.text.splitlines():
                lines.append(f"  {line}")
        return lines
    if isinstance(value, list):
        return [f"{label}: {_render_scalar(item)}" for item in value]
    if isinstance(value, str) and "\n" in value:
        lines = [f"{label}:"]
        if value == "":
            lines.append("  [empty]")
        else:
            for line in value.splitlines():
                lines.append(f"  {line}")
        return lines
    return [f"{label}: {_render_scalar(value)}"]


def render_text(blocks: Iterable[ResultBlock]) -> str:
    rendered_blocks: list[str] = []
    for block in blocks:
        lines = [f"object: {block.object_type}"]
        for label, value in block.fields:
            lines.extend(_render_field(label, value))
        rendered_blocks.append("\n".join(lines))
    if not rendered_blocks:
        return ""
    return "\n\n".join(rendered_blocks) + "\n"


def error_block(
    *,
    message: str,
    code: str,
    exit_code: int,
    reason: str,
    next_action: str | None = None,
    project_id: str | None = None,
) -> ResultBlock:
    fields: list[tuple[str, Value]] = [
        ("message", message),
        ("error code", code),
        ("exit code", exit_code),
    ]
    if project_id is not None:
        fields.append(("project id", project_id))
    fields.append(("reason", reason))
    fields.append(("next", next_action))
    return ResultBlock("error", fields)
