from __future__ import annotations

import re
from pathlib import Path

from alab.errors import ERROR_EXIT_CODES, AlabError, error_exit_code

_ROOT = Path(__file__).resolve().parents[1]
_SPEC_CLI_PATH = _ROOT / "docs" / "spec_cli.md"
_SPEC_CLI_CN_PATH = _ROOT / "docs" / "spec_cli_cn.md"


def _split_markdown_table_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    for char in text:
        if char == "`":
            in_code = not in_code
            current.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def _documented_error_exit_mapping(path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    in_table = False

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("Stable error-code exit mapping"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            if mapping:
                break
            continue
        if line.startswith("| ---") or line.startswith("| Error code"):
            continue
        cells = _split_markdown_table_row(line)
        if len(cells) != 2:
            continue
        code_match = re.fullmatch(r"`([^`]+)`", cells[0])
        exit_match = re.search(r"\b([0-5])\b", cells[1])
        if code_match and exit_match:
            mapping[code_match.group(1)] = int(exit_match.group(1))

    return mapping


def test_error_exit_mapping_matches_cli_specs() -> None:
    english = _documented_error_exit_mapping(_SPEC_CLI_PATH)
    chinese = _documented_error_exit_mapping(_SPEC_CLI_CN_PATH)

    assert english == ERROR_EXIT_CODES
    assert chinese == english


def test_documented_not_found_errors_exit_two() -> None:
    expected = {
        "CONTEXT_NOT_FOUND",
        "PROJECT_NOT_FOUND",
        "EXPERIMENT_NOT_FOUND",
        "RUN_NOT_FOUND",
        "VALIDATION_NOT_FOUND",
        "SOURCE_NOT_FOUND",
        "ARTIFACT_NOT_FOUND",
        "LOG_NOT_FOUND",
        "ANNOTATION_NOT_FOUND",
        "CREDENTIAL_NOT_FOUND",
        "AUDIT_NOT_FOUND",
        "CATALOG_NOT_FOUND",
        "CACHE_NOT_FOUND",
        "FEEDBACK_NOT_FOUND",
    }

    assert expected <= set(ERROR_EXIT_CODES)
    assert {code for code in ERROR_EXIT_CODES if code.endswith("_NOT_FOUND")} == expected
    assert all(error_exit_code(code) == 2 for code in expected)


def test_documented_error_exit_mapping_edges() -> None:
    expected = {
        "PROJECT_INVALID": 4,
        "COMMAND_UNAVAILABLE": 4,
        "RUNNER_FAILED": 1,
        "RUNNER_TIMEOUT": 1,
        "RUNNER_ERROR": 1,
        "REWARD_PARSE_ERROR": 1,
        "BASELINE_VALIDATION_FAILED": 1,
        "OUTPUT_EXISTS": 2,
        "STORAGE_ERROR": 5,
    }

    for code, exit_code in expected.items():
        assert error_exit_code(code) == exit_code
        assert AlabError(code, "reason").exit_code == exit_code

    assert error_exit_code("UNREGISTERED_INTERNAL_ERROR") == 5
    assert AlabError("UNREGISTERED_INTERNAL_ERROR", "reason").exit_code == 5
