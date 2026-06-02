from __future__ import annotations

from dataclasses import dataclass

ERROR_EXIT_CODES: dict[str, int] = {
    "AUTH_REQUIRED": 3,
    "AUTH_DENIED": 3,
    "HOME_EXISTS": 2,
    "CONTEXT_NOT_FOUND": 2,
    "CONTEXT_CONFLICT": 4,
    "PROJECT_NOT_FOUND": 2,
    "PROJECT_INVALID": 4,
    "PROJECT_ARCHIVED": 4,
    "EXPERIMENT_NOT_FOUND": 2,
    "EXPERIMENT_CLOSED": 4,
    "EXPERIMENT_ARCHIVED": 4,
    "RUN_NOT_FOUND": 2,
    "VALIDATION_NOT_FOUND": 2,
    "SOURCE_NOT_FOUND": 2,
    "SOURCE_INVALID": 2,
    "SOURCE_LIMIT_EXCEEDED": 2,
    "ARTIFACT_NOT_FOUND": 2,
    "LOG_NOT_FOUND": 2,
    "ANNOTATION_NOT_FOUND": 2,
    "CREDENTIAL_NOT_FOUND": 2,
    "AUDIT_NOT_FOUND": 2,
    "CATALOG_NOT_FOUND": 2,
    "CACHE_NOT_FOUND": 2,
    "FEEDBACK_NOT_FOUND": 2,
    "COMMAND_UNAVAILABLE": 4,
    "NAME_CONFLICT": 2,
    "SCOPE_VIOLATION": 4,
    "EXPERIMENT_BUSY": 4,
    "RESOURCE_BUSY": 4,
    "GIT_STATE_INVALID": 4,
    "GIT_ERROR": 5,
    "RUNNER_FAILED": 1,
    "RUNNER_TIMEOUT": 1,
    "RUNNER_ERROR": 1,
    "REWARD_PARSE_ERROR": 1,
    "CONFIG_INVALID": 2,
    "BASELINE_VALIDATION_FAILED": 1,
    "OUTPUT_EXISTS": 2,
    "STORAGE_ERROR": 5,
}


def error_exit_code(code: str) -> int:
    if code in ERROR_EXIT_CODES:
        return ERROR_EXIT_CODES[code]
    if code.endswith("_NOT_FOUND"):
        return 2
    return 5


@dataclass
class AlabError(Exception):
    code: str
    reason: str
    next_action: str | None = None
    message: str = "Command failed."
    exit_code: int | None = None

    def __post_init__(self) -> None:
        if self.exit_code is None:
            self.exit_code = error_exit_code(self.code)
        super().__init__(self.reason)
