# ALab 文档指南

本目录包含 ALab 的 V1 产品契约、子系统规格、证据账本、进度队列、历史日志和同步中文翻译。英文文档是 canonical；英文文档变化时，必须在同一个 change 中更新匹配的 `*_cn.md` 文档。

## 默认阅读顺序

1. [progress.md](progress.md)：先读这里，了解当前项目状态、gate snapshot 和下一步指针。
2. [progress_pipeline.md](progress_pipeline.md)：开始工作前读这里；它负责 active batch、active queue、full-suite policy 和 update checklist。
3. [completion_audit.md](completion_audit.md)：用来定位精确 requirement evidence 和任何具体 proof gap。
4. [progress_closed_gaps.md](progress_closed_gaps.md)：只有 planned work 像过去已关闭的 proof family 时才打开。
5. [progress_log.md](progress_log.md)：只在需要历史上下文，或追溯某个 decision、implementation batch、validation run 的时间时使用。
6. [blueprint.md](blueprint.md) 和 `spec_*.md` 文件：修改 product behavior、command contracts、storage、lifecycle semantics、runners、observe behavior、dashboard behavior 或 tests 时使用。

## 文档分组

| 分组 | 文件 | 用途 |
| --- | --- | --- |
| Product overview | [blueprint.md](blueprint.md), [blueprint_cn.md](blueprint_cn.md) | V1 canonical overview：product definition、boundaries、runtime stack、home layout、CLI direction、source/experiment direction、runner/adapter direction、milestones 和 references。 |
| CLI contract | [spec_cli.md](spec_cli.md), [spec_cli_cn.md](spec_cli_cn.md) | Invocation model、output format、debug behavior、errors、exit codes、command groups、aliases 和 per-command contracts。 |
| Storage/auth/context contract | [spec_storage_auth_context.md](spec_storage_auth_context.md), [spec_storage_auth_context_cn.md](spec_storage_auth_context_cn.md) | Home layout、SQLite rules、DDL schema、JSON field contracts、credentials、secrets、global config、project config persistence、context markers、migrations 和 backup。 |
| Project/source/experiment contract | [spec_project_source_experiment.md](spec_project_source_experiment.md), [spec_project_source_experiment_cn.md](spec_project_source_experiment_cn.md) | Project config schema、project init、source model、experiment lifecycle、worktree maintenance、mutable scope、run lifecycle 和 submit lifecycle。 |
| Lifecycle contract | [spec_lifecycle.md](spec_lifecycle.md), [spec_lifecycle_cn.md](spec_lifecycle_cn.md) | Archive、unarchive、hard remove、restore、repair、revoke、prune、lifecycle blockers、trash staging 和 lifecycle audit visibility。 |
| Runner/adapter contract | [spec_runners_adapters.md](spec_runners_adapters.md), [spec_runners_adapters_cn.md](spec_runners_adapters_cn.md) | Runner contract、runtime directories、environment injection、local runner、Docker runner、rewards、artifacts、logs、hidden assets、Harbor、SkyDiscover 和 Docker-unavailable behavior。 |
| Observe/collaboration contract | [spec_observe_collaboration.md](spec_observe_collaboration.md), [spec_observe_collaboration_cn.md](spec_observe_collaboration_cn.md) | Visibility model、observe commands、search/pagination/sorting、filters、best ranking、logs、artifact export、tags、annotations 和 public safe status。 |
| Dashboard contract | [spec_dashboard.md](spec_dashboard.md), [spec_dashboard_cn.md](spec_dashboard_cn.md) | Root-only local read-only dashboard command、loopback HTTP server constraints、local API routes、frontend rules 和 security requirements。 |
| Verification contract | [spec_tests.md](spec_tests.md), [spec_tests_cn.md](spec_tests_cn.md) | CLI、storage、auth/context/lifecycle、project/source、run/submit、runner/reward/log/artifact、adapters 和 observe/collaboration 的 test strategy 与 acceptance gates。 |
| Current progress | [progress.md](progress.md), [progress_cn.md](progress_cn.md) | 当前状态、completion gates、do-not-reopen summary 和 next step 的短 dashboard。 |
| Active work queue | [progress_pipeline.md](progress_pipeline.md), [progress_pipeline_cn.md](progress_pipeline_cn.md) | Active batch 和 queue。这里必须保持 narrow；不要追加 stale backlog。 |
| Evidence ledger | [completion_audit.md](completion_audit.md), [completion_audit_cn.md](completion_audit_cn.md) | Requirement-to-evidence matrix，用于判断 V1 是否可以 claim completion。 |
| Closed-gap guardrails | [progress_closed_gaps.md](progress_closed_gaps.md), [progress_closed_gaps_cn.md](progress_closed_gaps_cn.md) | 已关闭 proof families 的 duplicate-work guardrails。 |
| Historical journal | [progress_log.md](progress_log.md), [progress_log_cn.md](progress_log_cn.md) | 按时间记录 implementation 和 validation history。用于 traceability，不作为当前 queue。 |
| Assets | [assets/readme-header.png](assets/readme-header.png) | README visual asset。 |

## 更新规则

- 将 [blueprint.md](blueprint.md) 和 subsystem specs 视为 normative product contract。
- 将 [completion_audit.md](completion_audit.md) 视为 requirement evidence 的 source of truth。
- 将 [progress_pipeline.md](progress_pipeline.md) 视为唯一 active queue。
- 将 [progress_closed_gaps.md](progress_closed_gaps.md) 视为 duplicate-work guard，不是 backlog。
- 将 [progress_log.md](progress_log.md) 视为 historical evidence，不是 current status。
- 当 requirement、command、warning/error code、lifecycle rule、visibility rule、runner contract、storage contract、release target 或 upstream catalog behavior 变化时，先更新相关 spec，再更新 audit/progress 文件。
- 保持英文和中文文档对在同一个 change 中同步。
