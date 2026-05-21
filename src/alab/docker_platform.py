from __future__ import annotations


def normalize_docker_platform(value: str | None, *, collapse_variant: bool = False) -> str | None:
    if not value:
        return None
    parts = [part.strip().lower() for part in value.split("/") if part.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    os_name = parts[0]
    arch_aliases = {
        "x86_64": "amd64",
        "x64": "amd64",
        "aarch64": "arm64",
        "arm64v8": "arm64",
    }
    arch = arch_aliases.get(parts[1], parts[1])
    if len(parts) > 2 and not collapse_variant:
        return "/".join([os_name, arch, *parts[2:]])
    return f"{os_name}/{arch}"
