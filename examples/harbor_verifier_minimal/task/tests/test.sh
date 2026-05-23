#!/bin/sh
set -eu

mkdir -p /logs/alab/logs/verifier
python - <<'PY'
import json
from pathlib import Path

import main

CASES = [
    ("regional outage down for clinic network", True),
    ("cosmetic documentation question about button text", False),
    ("security breach with customer impact for vip account", True),
    ("unable to login customer impact for hospital admins", True),
    ("billing question about invoice wording", False),
    ("data loss reported by normal customer", True),
]

correct = 0
margins = []
details = []
for text, expected in CASES:
    score = main.score_ticket(text)
    predicted = main.classify_ticket(text)
    correct += int(predicted == expected)
    margin = score if expected else 1.0 - score
    margins.append(max(0.0, min(1.0, margin)))
    details.append(
        {
            "text": text,
            "expected_urgent": expected,
            "predicted_urgent": predicted,
            "score": round(score, 6),
        }
    )

accuracy = correct / len(CASES)
mean_margin = sum(margins) / len(margins)
reward = round(0.75 * accuracy + 0.25 * mean_margin, 6)
Path("/logs/alab/logs/verifier/reward.json").write_text(
    json.dumps(
        {
            "reward": reward,
            "accuracy": round(accuracy, 6),
            "mean_margin": round(mean_margin, 6),
            "case_count": len(CASES),
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
Path("/logs/alab/logs/verifier/details.json").write_text(
    json.dumps(details, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"verified reward={reward}")
PY
