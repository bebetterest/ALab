# ALab V1 Runners, Rewards, Logs, Artifacts, And Adapters Spec

This spec defines runner contracts, reward parsing, artifact/log capture, Docker runner scope, Harbor support, and SkyDiscover support.

## 1. Runner Contract

All runners implement one contract.

Inputs:

- Project id.
- Experiment id or validation id.
- Config version.
- Commit sha.
- Temporary `workspace` path.
- Temporary `run_dir` path.
- Temporary `hidden_dir` path.
- Environment map.
- Secret environment map.
- Timeout.
- Artifact config.
- Reward policy.

Outputs:

- Status.
- Exit code when available.
- Started and ended timestamps.
- Stdout/stderr byte streams.
- Reward extraction result.
- Metrics map.
- Artifact candidates.
- Failure reason.
- Hidden log references for admin-only streams.

Invariants:

- Runners never mutate experiment worktrees.
- Runners execute against a temporary clean checkout.
- Runners may write to `workspace` and `run_dir`; those writes are discarded after capture.
- Runner stdin is closed. Local subprocesses receive `DEVNULL`; Docker-backed runners run non-interactively.
- Hidden validation assets and raw hidden verifier/evaluator logs must be written under `hidden_dir` or another adapter staging path outside `workspace` and `run_dir`.
- On timeout, ALab terminates the process/container and still attempts best-effort capture.
- Different experiments may run concurrently. The same experiment cannot run or submit concurrently.

Config-dependent path validation:

- Config schema validation checks that runner, reward, artifact, Dockerfile, and context paths are syntactically valid, rooted at an allowed root when applicable, and cannot escape the repository or runtime root after normalization.
- Schema validation does not require source-dependent paths such as `runner.working_directory`, `reward.path`, artifact globs, `runner.dockerfile`, or `runner.context` to exist in every future source snapshot.
- Missing source-dependent paths are recorded as saved baseline/run failures when the runner operation has a validation or run record. They use `RUNNER_ERROR`, `REWARD_PARSE_ERROR`, or artifact capture statuses according to the failing subsystem instead of silently rewriting config.

## 1.1 Free Evaluation

`runner.type = "none"` paired with `reward.type = "none"` is free evaluation mode. It is not an executable runner and does not call the runner contract.

Rules:

- Project init and config import write a `not_required` validation record and make the config active valid without executing a baseline evaluator.
- `alab run` is unavailable for experiments bound to free evaluation.
- `alab submit` closes the experiment directly after normal state, secret, ref visibility, Git state, and mutable-scope checks.
- Accepted free submissions create no run, log, artifact, reward, metric, or hidden-log rows and are not eligible for best-run ranking.
- Dirty free submissions create an `ALab submit: <message>` commit before storing the submission.

## 2. Runtime Directories

Temporary runtime directories:

```text
~/.ALab/tmp/<project_id>/<operation_id>/
├── workspace/
├── run/
├── hidden/
└── home/
```

Rules:

- `workspace/` is the clean editable checkout used by runners.
- `run/` is the runner output directory available for configured `run:` artifact capture.
- `hidden/` is reserved for hidden validation assets, verifier/evaluator bundles, and raw hidden verifier/evaluator logs.
- `hidden/` is not a valid artifact root and must never be exposed through token-scoped output.
- `home/` is the temporary HOME used by local runner `env_mode = "sanitized"`.
- Temporary directories may contain plaintext checkout content, logs, and artifacts while a command is running.
- ALab removes temporary directories after capture unless a future explicit debug retention flag is added. `ALAB_DEBUG=1` alone does not keep them.

## 3. Environment Injection

Effective runner environment:

1. selected inherited environment according to runner type and `env_mode`;
2. `[env]`;
3. `[secret_env]`;
4. ALab internal variables.

ALab internal variables are always injected and override previous values:

```text
ALAB_PROJECT_ID=<project_id>
ALAB_EXP_ID=<exp_id or empty for validation>
ALAB_RUN_ID=<run_id or validation_id>
ALAB_CONFIG_VERSION=<version>
ALAB_WORKSPACE=<workspace path inside runner context>
ALAB_RUN_DIR=<run_dir path inside runner context>
```

Rules:

- The values are fixed for the operation.
- They are not taken from user config.
- They must be present for local, Docker, Harbor, and SkyDiscover runners.
- Docker-backed runners receive container-visible paths for `ALAB_WORKSPACE` and `ALAB_RUN_DIR`.
- ALab credential variables such as `ALAB_KEY` are always stripped from the inherited environment before runner execution, even when `env_mode = "full"`.
- Docker, Harbor, and SkyDiscover Docker runners do not inherit host environment variables. Their effective environment starts from an empty inherited environment, then applies `[env]`, `[secret_env]`, and ALab internal variables.
- Runners never receive `.alab/context.json` or `.alab/token`; the temporary workspace is a clean code checkout, not a submit-capable ALab context.

## 4. Local Runner

Rules:

- `runner.command` executes as argv without a shell.
- `runner.shell` explicitly runs through `/bin/sh -c <shell>` on supported V1 hosts.
- `runner.shell` is supported only by the local runner and Docker runner shell mode in V1. Harbor, SkyDiscover Docker, and SkyDiscover Python runners reject user `runner.shell` because adapter verifier/evaluator commands are owned by the adapter contract.
- Local runner workspace containment checks use normalized path ancestry, not string-prefix matching, so sibling paths with the workspace name as a prefix still escape and fail.
- `env_mode = "sanitized"` inherits only `PATH`, `LANG`, `LC_*`, `TZ`, and `TMPDIR` when present, and sets `HOME` to the operation temporary `home/` directory.
- ALab creates the sanitized temporary `home/` directory before starting the local runner process.
- `env_mode = "full"` inherits the complete ALab process environment.
- `env_mode = "none"` inherits no host environment variables.
- Effective env is selected inherited environment, then `[env]`, then `[secret_env]`, then ALab internal variables.
- `env_mode = "full"` renders a stable warning because host environment variables outside `[secret_env]` are not guaranteed to be redacted from runner output.
- Local runner stdin is `DEVNULL`.
- Local runner starts the subprocess in a separate process group.
- On timeout, ALab terminates the process group, waits briefly, and then force-kills the process group if needed.
- Timeout status still attempts best-effort log and artifact capture.

## 5. Docker Runner

Scope:

- Supports exactly one image source: `runner.image` or `runner.dockerfile` plus `runner.context`.
- No Docker Compose in V1.
- No custom cache backend in V1.
- Docker configuration is an explicit allowlist. Raw Docker CLI argument passthrough is rejected.
- Whitelisted build/run fields are `runner.build_args`, `runner.target`, `runner.platform`, `runner.user`, `runner.cpus`, `runner.memory_mb`, `runner.network`, `runner.image`, `runner.dockerfile`, and `runner.context`.
- `runner.build_args` is a map of string keys to string values. Build args are plain config values, not secret values, and are included in config export.
- `runner.target` selects a Dockerfile build target.
- `runner.platform` passes a Docker platform selector when supported by the local Docker installation.
- V1 validates configured Docker platform selectors before config write. `linux` uses the coarse Linux container capability. `linux/amd64` and `linux/arm64` use per-architecture capability rows derived from Docker's native runtime architecture plus reported Buildx platforms.
- Unsupported or unknown platform selectors fail config validation with `CONFIG_INVALID` before a project config is written.
- `runner.user` passes the container user for the main runner process. ALab does not elevate privileges during capture.
- `runner.cpus` and `runner.memory_mb` pass Docker CPU and memory limits when supported.
- If configured Docker CPU or memory limits are not supported by the local Docker environment, config validation fails before write with `CONFIG_INVALID`.
- Extra user-configured host mounts, bind mounts, named volumes, devices, and privileged mode are not supported in V1.
- If `runner.image` is not present locally, ALab runs `docker pull` for that image before container execution. Pull failure records a saved validation/run status `error` with `RUNNER_ERROR` when a result record exists.
- Automatic image pull is the only V1 pull policy for `runner.image`; there is no `pull_policy` config field in V1.

Path rules:

- `runner.dockerfile` and `runner.context` are repo-relative paths resolved inside the temporary workspace.
- They must not escape the repository after path normalization.
- Dockerfile builds follow Docker `.dockerignore` semantics for the configured build context. Dockerfile images are built and cached by a key derived only from build inputs: Dockerfile content, `.dockerignore` content when present, effective filtered build context content, `runner.build_args`, `runner.target`, and `runner.platform`.
- Docker run-time fields such as `runner.command`, `runner.shell`, `runner.user`, `runner.network`, `runner.cpus`, `runner.memory_mb`, timeout, environment, and artifact/log/reward settings are stored in config/run records but do not change the image cache key.
- ALab tags cached Dockerfile images under an ALab-owned tag derived from project id and cache key and records safe cache metadata in SQLite.
- `alab cache prune --docker-images` and top-level `alab cache prune --all` remove ALab-owned image cache entries.

Container contract:

- Temporary workspace is mounted read-write at `/app`.
- Temporary run directory is mounted read-write at `/logs/alab`.
- `runner.working_directory` maps to `/app/<runner.working_directory>`.
- `ALAB_WORKSPACE=/app`.
- `ALAB_RUN_DIR=/logs/alab`.
- `runner.command` executes as argv in the container. `runner.shell` executes as `/bin/sh -c <shell>` in the container and fails with `RUNNER_ERROR` if `/bin/sh` is unavailable.

Network:

- `runner.network = "default"` uses Docker default networking.
- `runner.network = "none"` passes Docker no-network mode.
- `runner.network = "host"` is not supported in V1 and fails config validation with `CONFIG_INVALID`.
- Runtime capability probes are still used for Docker availability, coarse Linux platform support, per-architecture Linux platform support, and CPU/memory limit support. Probe results are cached by runtime fingerprint; if the fingerprint changes, ALab probes again.
- `alab config validate --refresh-capabilities` clears cached capability results and reruns probes.
- Unsupported configured CPU or memory limits fail before config write with `CONFIG_INVALID`.

Capture:

- ALab performs best-effort host-side readability checks before log/artifact capture.
- Files the host cannot read because of container ownership or permissions are recorded as artifact capture errors or skipped entries.
- ALab does not retry capture with elevated privileges.
- If `runner.user` makes workspace or run output unreadable to the host, the run status is still determined by runner exit and reward parsing; unreadable files become capture warnings or artifact errors.
- Docker image setup/build stdout or stderr is stored as hidden log output, redacted for configured secret bytes, and not merged into user-visible runner stdout/stderr. When setup output is captured, the saved run/validation renders `DOCKER_SETUP_OUTPUT_CAPTURED`.

## 6. Reward Types

Reward types:

- `none`: no reward extraction; valid only with `runner.type = "none"`.
- `exit_code`: exit code `0` maps to `1.0`; non-zero maps to `0.0`.
- `file`: read reward from configured `workspace:` or `run:` path.
- `stdout_regex`: extract reward from stdout capture.
- `harbor`: read Harbor verifier reward output.
- `skydiscover`: read configured primary metric from evaluator metrics.

General rules:

- ALab attempts reward extraction for every run, including non-zero exits.
- Runner exit code determines pass/fail.
- Reward parse failure with exit code `0` makes status `error`.
- Reward parse failure with non-zero exit keeps status `failed` and records reward parse failure.
- Ranking requires a parsed finite numeric reward.
- `NaN`, `Infinity`, missing values, empty strings, and non-numeric values fail reward parsing.
- Simple reward types store the parsed reward under the configured `reward.primary_metric` name in the run record's `metrics` map. When a file reward, Harbor verifier, or SkyDiscover evaluator produces a top-level string-to-finite-number metric object, ALab stores that full object in `metrics`. Project `metrics.reference` declarations may point at any of those metric names for dashboard reference curves, and each run may omit any reference metric.

File reward:

- `reward.path` must be rooted at `workspace:` or `run:`.
- Path resolution follows artifact root escape checks.
- The reward file read limit reuses `artifacts.per_file_limit_bytes`.
- Plain text is parsed as a stripped finite float.
- JSON reward files must contain a top-level string-to-finite-number object.
- JSON reward metrics are top-level keys only. Nested paths are not supported in V1.
- ALab reads `reward.primary_metric` from the top-level object.

Stdout regex reward:

- `reward.pattern` is required.
- Extraction reads redacted, truncated stdout as stored by ALab.
- If the regex has a named group `reward`, ALab parses that group.
- Otherwise ALab parses the first capture group.
- If stdout was truncated before the reward text, parsing may fail and records `REWARD_PARSE_ERROR`.

Harbor reward:

- Reads `run:/logs/verifier/reward.txt` or `run:/logs/verifier/reward.json`.
- `reward.json` must be a top-level string-to-finite-number object.
- ALab reads `reward.primary_metric`, default `reward`.
- Missing, non-finite, or non-numeric metric values fail reward parsing. Detailed verifier diagnostics must be written to separate logs or artifacts, not to the reward metrics object.

SkyDiscover reward:

- Default `reward.primary_metric` is `combined_score`.
- If the primary metric was explicitly configured and missing, reward parsing fails.
- If the default primary metric is missing, ALab averages all finite numeric top-level metrics.
- If no finite numeric top-level metrics exist, reward parsing fails.

## 7. Artifact Capture

Artifact roots:

- `workspace:` means temporary clean checkout root.
- `run:` means temporary run output directory.
- Unprefixed artifact globs mean `workspace:`.
- `hidden:` is not a valid artifact root.

Rules:

- Artifact paths must not escape their root after symlink/path normalization.
- Artifact root containment checks use normalized path ancestry, not string-prefix matching.
- Artifact glob matching uses Python `glob` semantics relative to the selected artifact root, including `**` recursive matching. ALab normalizes separators to `/`, deduplicates matches by resolved path, and sorts matched paths by normalized relative path before capture.
- When a glob matches a symlink, ALab resolves it.
- Symlinks whose resolved target stays inside the artifact root are captured as target bytes.
- Symlinks that escape the root are skipped and recorded with status `skipped`.
- Directory matches are recursively captured subject to per-file/per-run limits.
- Directory matches expand into one artifact record per captured file.
- V1 does not create directory artifacts or automatic zip archives.
- Stdout/stderr are logs, not artifacts.
- Oversized artifacts are skipped and recorded without changing run/validation status.
- Capture errors do not change run or validation status.
- Capture errors are recorded as artifact statuses and `ARTIFACT_CAPTURE_ERROR` warnings.
- ALab attempts artifact capture for passed, failed, error, and timeout results whenever a run or validation record exists and temporary runtime directories are still available. Runner exit failure, reward parse failure, and timeout do not by themselves disable artifact capture.
- Artifact export writes exact captured bytes.
- V1 does not redact artifact contents.
- If active `secret_env` values and artifact globs are both configured, run and validation output must warn that artifact bytes are exact and not automatically redacted.
- Artifact archive, unarchive, remove, and archived show/export rules are defined in [spec_lifecycle.md](spec_lifecycle.md).

Blob storage:

```text
~/.ALab/projects/<project_id>/artifacts/blobs/sha256/<first-two-hex>/<sha256>
```

- `artifacts.blob_path` stores a path relative to the project artifact store.
- Multiple artifact records may reference the same blob when content hashes match.
- Artifact blob files are deleted only when no remaining artifact row references them.

## 8. Logs

Rules:

- Stdout and stderr byte limits are independent.
- Secret redaction happens before truncation and storage. ALab applies exact UTF-8 byte replacement for every active secret value against the captured stream, then enforces the configured stored byte limit on the redacted stream.
- Logs exceeding limits are truncated and marked `truncated = true`.
- Logs are stored as byte files plus SQLite metadata, not as authoritative SQLite text.
- `preview_text` is a safe UTF-8 replacement-decoded prefix for CLI rendering only.
- `runs show` renders fixed-size stdout/stderr previews and log metadata.
- Full visible logs are accessed through `observe logs show|export`; `show` renders the stored log bytes as safe UTF-8 replacement-decoded `content`.
- Hidden logs require root/admin plus explicit `--include-hidden`.
- Log archive, unarchive, remove, and archived show/export rules are defined in [spec_lifecycle.md](spec_lifecycle.md).
- Shared log files are deleted only when no remaining log row references them.

Visible streams:

- `stdout`
- `stderr`

Hidden streams:

- `hidden_stdout`
- `hidden_stderr`

Hidden log rules:

- Harbor and SkyDiscover raw verifier/evaluator stdout/stderr are stored as admin-only hidden logs.
- Token-visible output shows only safe summaries, metric names, reward values, and sanitized feedback.
- Hidden logs are never exported through token-scoped commands.

## 9. Hidden Validation Assets

Hidden validation assets include private verifier scripts, private tests, private test data, evaluator bundles, and adapter metadata not intended for agents.

Rules:

- Hidden validation assets must never be imported into source refs.
- They must never be copied into experiment worktrees.
- They must never be copied into inspection worktrees.
- They must never be exported as artifacts.
- During validation and run execution, they may be materialized only outside temporary `workspace` and `run_dir`, such as `hidden_dir`, adapter staging, or a container path not mounted at the editable workspace.
- Token-scoped CLI output must not render hidden asset contents, absolute host paths, staging paths, full verifier commands, private test names, or private test data.
- Admin/root output may show safe summaries, stable hashes, catalog refs, runner type, evaluator type, and high-level task identifiers, but not hidden asset contents.
- These rules prevent CLI/worktree disclosure. They are not OS-level secrecy guarantees.

## 10. Harbor Adapter

Scope:

- V1 supports single-step Harbor tasks.
- V1 supports shared verifier and separate verifier.
- V1 does not support Windows tasks.
- V1 does not support multi-step tasks.

Supported task files:

- `instruction.md`
- `task.toml`
- `environment/`
- `tests/test.sh`
- `tests/Dockerfile` for separate verifier image builds.

Editable source:

- If a Harbor task declares a supported `source` file or directory, ALab imports only that source as editable source.
- A Harbor `source` value is supported only when it is a task-relative path that stays inside the task directory after normalization and does not point into `tests/`, `environment/`, `solution/`, verifier assets, or task-private files.
- If no supported source is declared and no explicit ALab source selector is supplied, ALab creates an empty source.
- Empty-source fallback is a supported Harbor V1 behavior, not an error. The resulting project still requires baseline validation before new experiments can be created.
- ALab never imports `tests/`, `environment/`, `solution/`, verifier assets, or task-private files as editable source.

Environment:

- Supported environment inputs are a Docker image or `environment/Dockerfile`.
- Missing OS is treated as Linux.
- `environment.allow_internet = false` maps to `runner.network = "none"` only when the user has not explicitly configured `runner.network`.
- `environment.allow_internet = true` or omitted maps to `runner.network = "default"` only when the user has not explicitly configured `runner.network`.
- `environment.cpus` maps to Docker `--cpus`.
- `environment.memory_mb` maps to Docker `--memory`.
- CPU and memory resource support is checked before config write.

Verifier:

- Shared verifier uses the task environment and `tests/test.sh`.
- Separate verifier supports either a verifier image or `tests/Dockerfile`.
- Verifier workspace mount is temporary and writable.
- Verifier assets are hidden validation assets.
- Raw verifier stdout/stderr are hidden logs and admin-only.
- Token-visible records may show verifier status, reward, metric names, and safe summaries only.

Task text:

- `instruction.md` may become visible project task text.
- If the user provides explicit ALab task text through CLI or config, explicit ALab task text wins and `instruction.md` is retained only as origin metadata.

Unsupported fields:

- Multi-step tasks.
- Windows or non-Linux OS.
- GPU requirements and `gpu_types`.
- `storage_mb`.
- MCP servers.
- Healthchecks.
- Custom resource scheduling.
- External services.
- Docker Compose or equivalent multi-container runtime.
- Host environment placeholders in `task.toml`.
- Raw Docker argument passthrough and task-declared extra host mounts.

Rules:

- Unsupported runtime-affecting fields fail with `CONFIG_INVALID`.
- Unsupported Harbor task capabilities are strict failures, not ignored compatibility hints. This includes Windows tasks, multi-step task declarations, Docker Compose or equivalent multi-container runtime, GPU, MCP, healthcheck, external services, storage, custom scheduling, raw Docker passthrough, and task-declared extra host mounts.
- Metadata and descriptive fields that do not affect execution may be ignored after recording safe origin metadata.
- Placeholder values such as `${TOKEN}` fail validation.
- All literal Harbor task environment values are injected as secret environment values and redacted like `secret_env`, regardless of whether the Harbor task schema labels them secret.
- `solution/` is excluded and must never become editable source.

## 11. SkyDiscover Adapter

Catalog commands:

```text
alab catalog skydiscover add [--origin-url <url>] [--ref <ref>|--commit <sha>]
alab catalog skydiscover update [--origin-url <url>] [--ref <ref>|--commit <sha>]
alab catalog skydiscover show
alab catalog skydiscover remove --force --confirm skydiscover [--reason <text>]
```

Rules:

- Catalog commands require root key.
- `add` clones SkyDiscover under `~/.ALab/sources/skydiscover/` when missing.
- `update` refreshes the existing catalog to a newer pinned upstream commit.
- `--origin-url` defaults to the official SkyDiscover repository URL.
- When neither `--ref` nor `--commit` is supplied, ALab resolves the current upstream `main` and pins the exact commit.
- `--ref` resolves a branch, tag, or commit-ish and stores the resolved exact commit.
- `--commit` requires a full commit SHA and stores that exact commit after verifying it exists in the selected origin.
- `show` renders pinned commit, origin URL, retrieval time, and local path without fetching from the network.
- The catalog pins an exact upstream commit.
- ALab does not follow upstream `main` automatically.
- Resolving a missing `skydiscover:<path>` never auto-updates the catalog.
- If no active SkyDiscover catalog exists, any command resolving `skydiscover:<path>` fails with `CONFIG_INVALID` and a next action to run `alab catalog skydiscover add`. Missing paths in an active catalog also fail with `CONFIG_INVALID`; ALab never auto-fetches or auto-updates the catalog while resolving a task or evaluator.
- `update` fails when the local catalog has non-ALab modifications, untracked files, or an unexpected remote URL.
- `remove` deletes the local catalog and marks catalog metadata removed only when no active project config and no open experiment bound config references SkyDiscover catalog tasks or evaluator bundles.
- Closed and archived experiment history remains observable after catalog removal because run records, metrics, safe feedback, logs, artifacts, and annotations do not depend on live catalog files.
- Cache cleanup for Docker images, SkyDiscover evaluator environments, and ALab trash entries is handled by `alab cache prune` as defined in [spec_lifecycle.md](spec_lifecycle.md).

Catalog references:

```text
skydiscover:<path-inside-benchmarks>
```

- Catalog references identify evaluator bundles or Harbor-compatible tasks.
- They do not identify editable source code by themselves.
- Missing paths or unrecognized evaluator/task formats fail config validation.

Source precedence:

- For `project init skydiscover`, explicit editable sources are limited to `--source-path`, `--source-git`, or `--source-empty`.
- `project init skydiscover` rejects `--source-ref`; existing ALab sources are project-scoped reproducibility records, not cross-project init inputs.
- If no explicit editable source is provided and the benchmark has an initial program file or directory, ALab imports only that initial file or directory as the editable source.
- If no initial program exists, init fails and asks for an explicit source.
- SkyDiscover benchmark directories are not imported wholesale as editable source.

Evaluator-only rule:

- SkyDiscover remains evaluator-only in ALab V1.
- ALab does not call SkyDiscover search loops, proposal generation, mutation, autonomous optimization commands, or scheduling loops.

### SkyDiscover Docker Evaluator

Rules:

- Materializes evaluator Dockerfile and `evaluate.sh` into a local task bundle.
- Evaluator Dockerfile, `evaluate.sh`, support files, and benchmark-private data are hidden validation assets.
- Builds and runs evaluator in Docker against a temporary workspace.
- Mounts editable temporary workspace separately from evaluator assets.
- Must not copy evaluator assets back into workspace.
- Parses stdout JSON into top-level metrics.
- Evaluator `artifacts` JSON is stored in run feedback, not converted to file artifacts unless captured by artifact globs.
- Token-visible output may show task ref, pinned catalog commit, evaluator mode, metric names, reward value, and sanitized feedback.
- Token-visible output must not show evaluator source contents, hidden test data, absolute catalog paths, or staging paths.

### SkyDiscover Python Evaluator

Rules:

- SkyDiscover Python evaluator support is a full V1 adapter capability, not an experimental or V2-only feature.
- Materializes evaluator Python files into a local task bundle.
- Evaluator files and benchmark-private data are hidden validation assets.
- Executes evaluator code in a subprocess through an ALab wrapper.
- The main ALab process must not import evaluator code.
- The Python evaluator is not an OS sandbox. Root/admin output and config summaries must make this explicit when a SkyDiscover Python runner is configured.
- Calls `evaluate(program_path)`, where `program_path` defaults to temporary workspace root.
- Python evaluator dependencies are installed into an ALab-managed `uv` environment outside project and experiment worktrees.
- If the evaluator bundle has `pyproject.toml` or `uv.lock`, ALab creates or reuses an environment with `uv sync`.
- If the evaluator bundle has `requirements.txt` and no `pyproject.toml`, ALab creates or reuses an environment and installs with `uv pip install -r requirements.txt`.
- The environment cache key is derived from evaluator dependency file hashes, the host platform, and the Python version used for the evaluator environment.
- Dependency installation may use the default network.
- Installation failure records `RUNNER_ERROR` and makes baseline/run fail.
- Parses returned JSON-serializable metrics and feedback.

## 12. Docker Unavailable

Rules:

- Docker/Harbor/SkyDiscover Docker validation records status `error` when Docker is unavailable.
- Project becomes invalid.
- Optional Docker-dependent tests skip when Docker is unavailable.

## 13. References

Planning references checked on 2026-05-16:

- Harbor task documentation: https://www.harborframework.com/docs/tasks
- Harbor multi-step task documentation: https://www.harborframework.com/docs/tasks/multi-step
- Harbor Windows task documentation: https://www.harborframework.com/docs/tasks/windows-container-support
- SkyDiscover README and evaluator formats: https://github.com/skydiscover-ai/skydiscover
- Docker none network driver documentation: https://docs.docker.com/engine/network/drivers/none/
