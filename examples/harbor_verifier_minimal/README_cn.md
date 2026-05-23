# Harbor Verifier Minimal 示例

这个示例展示 ALab Harbor adapter 的 hidden verifier task。只有
`starter/main.py` 会成为 editable source；`tests/`、verifier logic 和 task-private
files 不会暴露给 worker，也不会作为 token-visible artifacts。

## Demo 任务

editable candidate 实现 incident-ticket urgency classifier，提供
`score_ticket(text)` 和 `classify_ticket(text)`。hidden verifier 会导入这些函数，
并用 outage、breach、login、cosmetic documentation 等私有 SLA cases 评分。

baseline 会漏掉几个 high-impact phrases。`scripts/run_demo.sh` 会在 worktree
candidate 中加入 breach、login 和 customer-impact signals，然后运行 Harbor verifier，
并用 project admin key 查看 hidden-capable logs。

任务形态：

- Editable file：`task/starter/main.py`，导入 experiment worktree 后是 `main.py`。
- Public contract：保留 `score_ticket(text)` 和 `classify_ticket(text)`。
- Hidden verifier：`task/tests/test.sh` 会导入 candidate 并用 private cases 评分。
  workers 不会把 verifier 当成 editable source 拿到。
- Baseline behavior：能识别明显 outage/data-loss 文案，但漏掉 breach、login 和
  customer-impact language。
- Demo improvement：加入这些 high-impact signals，并为 private SLA cases 降低
  urgency threshold。
- Reward source：Harbor 读取 `logs/verifier/reward.json`；该文件必须只包含 finite
  numeric metrics，格式是 string-to-finite-number map。详细 case diagnostics 写入
  hidden verifier log content。

这个示例适合展示为什么 verifier assets 和 hidden logs 必须留在 worker access
之外。worker 可以改进 public interface，但看不到 private test cases。

## 环境要求

- Docker daemon，并且可以使用 `python:3.11-alpine`。

## 运行

```sh
examples/harbor_verifier_minimal/scripts/setup_project.sh --dry-run
examples/harbor_verifier_minimal/scripts/setup_project.sh
examples/harbor_verifier_minimal/scripts/run_demo.sh
```

排障分层：

- ALab config/runner error：检查 `.run/logs/02-project-init.redacted.log`，并确认
  generated config 仍指向 Harbor task directory。
- Docker daemon 或 image error：先运行 `docker version`；Harbor verifier 通过
  Docker 执行，所以 Docker 可用性是环境前提。
- Reward parse error：保持 `logs/verifier/reward.json` 只包含 numeric metrics。
  数组、对象、bool、`NaN` 和 string 都是 invalid metrics；详细内容写 hidden
  verifier logs。
- Hidden-log access error：worker tokens 不能读取 hidden verifier logs；只有
  controller/admin surface 使用 project admin/root `--include-hidden`。

## 覆盖内容

- Harbor `source = "starter"` editable-source import；
- 在 Docker 中执行 private verifier；
- 从 `logs/verifier/reward.json` 解析 Harbor reward；
- hidden verifier logs 只有 admin/root 使用 `--include-hidden` 时可见。
