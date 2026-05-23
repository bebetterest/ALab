---
name: alab-experiment-worker
description: 当 Codex 位于 ALab experiment worktree 中，并且只应使用 worktree token 检查状态、修改候选代码、运行 evaluation、提交最终结果、读取可见实验证据，而不能使用 project admin 或 root 权限时使用。
---

# ALab Experiment Worker

## 概览

当 Codex 在一个 ALab experiment worktree 内工作时使用本 skill。Worker 负责改进候选源码，可以查看可见范围内的历史 experiment 证据来寻找思路，在 worktree token context 中运行 ALab evaluation，并在 finished work 有 passed run 支撑时提交最终结果。

本 skill 不是 project manager 或 global administrator。不得使用 project admin key、root key、catalog command、cache command、project config mutation 或 lifecycle removal command。

## 操作规则

- 只信任当前 worktree context 及其 `.alab/token`。
- 不读取、打印、复制、提交或重写 raw token/key。
- 不编辑 `.alab/`、ALab home records、cache directories、shared run directories、hidden evaluator assets、secret files 或 project control files。
- 只修改 experiment worktree 内与任务相关的 source files。
- 明确分离 source editing 和 CLI state。Experiment worktree 是唯一可编辑 source surface；任何额外加入的 ALab home、uv cache、pycache 或 shared directory 只供 `alab run`/`submit` 写状态，不得检查、patch、复制或提交其中内容。
- 保持改动可审查：优先小步、聚焦、可复现的 iteration，并使用简洁 run message。
- 不熟悉 command 时先运行 `alab help`；worktree token surface 之外的 command 应视为不可用。
- 如果 ALab 返回 `COMMAND_UNAVAILABLE`，停止该分支并报告缺失能力，不尝试绕过。

## 能力说明

这是一份能力指南，不是固定步骤。根据任务需要使用下列能力：

- 用 `alab status` 和 `alab help` 检查当前 context。
- 读取 worktree 中已有的任务文件和项目说明。
- 用 `alab observe experiments ...` 以及相关的可见 runs、artifacts、logs、annotations 查看历史 experiments。可以用这些证据寻找有希望的方案、避免重复失败，并理解 prior best 或 final commits。可见性仍由 ALab 强制执行；不要尝试访问 hidden 或 unavailable records。
- 当某个可见历史 experiment 看起来相关时，用 `alab exp checkout <exp_id> --path <dir> --commit best|final|latest` 创建 inspection checkout，阅读其源码，并与当前 worktree 对比。只有在确实有帮助时，才把任务相关的 source files 或 snippets 复制到当前 experiment worktree；绝不复制 `.alab/`、raw token、hidden assets、secret files、ALab home/cache files 或 project control files。
- 修改 worktree 内与任务相关的 source files，并保持实现足够清晰，方便后续 worker 延续。
- 保持 runner outputs 可被机器解析。若任务写 reward file，只把配置要求的 numeric metrics 放入该 reward file；case details、trace 或 explanation 应在允许时放到单独的可见 artifact/log。
- 若存在本地轻量检查，先运行这些检查，再用 `alab run --message "<brief reason>"` 运行 evaluation。
- 使用可见 stdout/stderr preview、warning code、artifact、log、metric 和 annotation 诊断 failed 或 weak runs。
- 当预期修改已经完成，并且当前 worktree 有一个 passed run 支撑结果时，使用事实性的 message、summary、feedback 和 refs 提交。

## Submit Guidance

- 只有当前 candidate 有 passed run 支撑时才 submit，除非用户或 controller 明确要求 non-passed closeout。
- 结果没有依赖或有意引用历史 experiments 时，才使用 `--ref none`。
- 如果本次工作受到可见历史 experiment 启发、从其派生、与其对比，或有意延续它，应对每个相关 experiment id 重复传入 `--ref <exp_id>`。
- 不要编造 refs，不要引用不可访问的 experiment ids，也不要只因为某个 visible experiment 存在就引用它。
- `--message` 保持简短。实质记录写入 `--summary`/`--summary-file` 和 `--feedback`/`--feedback-file`：改了什么、哪个 passed run 支撑、关键 metrics、哪些 refs 有意义，以及剩余风险。
- 如果没有 submit，应明确说明阻塞原因和当前最好的 run evidence。

## Command Reference

需要 worker command surface、observe pattern 或 run/submit 示例时，读取 [references/commands_cn.md](./references/commands_cn.md)。
