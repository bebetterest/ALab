from __future__ import annotations

import json
import os
from pathlib import Path

POLICY = "baseline_queue"
ENABLE_RUNBOOK_SHORTCUTS = False
ESCALATE_SECURITY = False

SEVERITY_WEIGHT = {
    "critical": 5.0,
    "high": 3.0,
    "medium": 1.5,
    "low": 0.5,
}


def load_incidents() -> list[dict[str, object]]:
    path = Path(__file__).parent / "data" / "incidents.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload["incidents"])


def estimated_hours(incident: dict[str, object]) -> float:
    hours = float(incident["estimated_hours"])
    if ENABLE_RUNBOOK_SHORTCUTS and incident["runbook_ready"]:
        hours *= 0.70
    return hours


def priority_score(incident: dict[str, object]) -> float:
    severity = SEVERITY_WEIGHT[str(incident["severity"])]
    affected = float(incident["affected_users"])
    sla = float(incident["sla_hours"])
    security_bonus = 12.0 if ESCALATE_SECURITY and incident["category"] == "security" else 0.0
    outage_bonus = 1.5 if incident["category"] == "outage" else 0.0
    return severity * 10 + affected / 100 + security_bonus + outage_bonus - sla / 10


def schedule_key(incident: dict[str, object]) -> tuple[float, float, str]:
    if POLICY == "severity_first":
        return (-SEVERITY_WEIGHT[str(incident["severity"])], float(incident["sla_hours"]), str(incident["id"]))
    if POLICY == "sla_balanced":
        return (-priority_score(incident), float(incident["sla_hours"]), str(incident["id"]))
    return (float(incident["created_seq"]), 0.0, str(incident["id"]))


def build_plan(incidents: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, float]]:
    budget_hours = 10.0
    elapsed = 0.0
    rows = []
    total_weight = 0.0
    resolved_weight = 0.0
    on_time_weight = 0.0
    security_weight = 0.0
    security_on_time = 0.0

    for incident in sorted(incidents, key=schedule_key):
        weight = SEVERITY_WEIGHT[str(incident["severity"])]
        total_weight += weight
        if incident["category"] == "security":
            security_weight += weight

        hours = estimated_hours(incident)
        starts_at = elapsed
        ends_at = elapsed + hours
        elapsed = ends_at
        scheduled = ends_at <= budget_hours
        on_time = scheduled and ends_at <= float(incident["sla_hours"])
        if scheduled:
            resolved_weight += weight
        if on_time:
            on_time_weight += weight
            if incident["category"] == "security":
                security_on_time += weight

        rows.append(
            {
                "id": incident["id"],
                "category": incident["category"],
                "severity": incident["severity"],
                "estimated_hours": round(hours, 2),
                "starts_at": round(starts_at, 2),
                "ends_at": round(ends_at, 2),
                "scheduled": scheduled,
                "on_time": on_time,
            }
        )

    resolved = resolved_weight / total_weight
    on_time = on_time_weight / total_weight
    security = security_on_time / security_weight if security_weight else 1.0
    runbook_coverage = sum(1 for row in rows if row["scheduled"]) / len(rows)
    reward = 0.45 * resolved + 0.30 * on_time + 0.15 * security + 0.10 * runbook_coverage
    metrics = {
        "reward": round(reward, 6),
        "resolved_weight": round(resolved, 6),
        "on_time_weight": round(on_time, 6),
        "security_on_time": round(security, 6),
        "scheduled_fraction": round(runbook_coverage, 6),
    }
    return rows, metrics


def main() -> None:
    run_dir = Path(os.environ.get("ALAB_RUN_DIR", "."))
    run_dir.mkdir(parents=True, exist_ok=True)
    plan, metrics = build_plan(load_incidents())
    result = {
        **metrics,
        "policy": POLICY,
        "enable_runbook_shortcuts": ENABLE_RUNBOOK_SHORTCUTS,
        "escalate_security": ESCALATE_SECURITY,
        "plan": plan,
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Incident Triage Plan",
        "",
        f"- Policy: `{POLICY}`",
        f"- Reward: `{metrics['reward']}`",
        f"- Resolved weight: `{metrics['resolved_weight']}`",
        f"- On-time weight: `{metrics['on_time_weight']}`",
        "",
        "| incident | category | severity | ends_at | on_time |",
        "|---|---|---:|---:|---|",
    ]
    for row in plan:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['severity']} | {row['ends_at']} | {row['on_time']} |"
        )
    (run_dir / "triage_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"policy={POLICY}")
    print(f"reward={metrics['reward']:.6f}")


if __name__ == "__main__":
    main()
