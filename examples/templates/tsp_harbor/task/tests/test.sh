#!/bin/sh
set -eu

mkdir -p /logs/alab/logs/verifier
cd /workspace
python - <<'PY'
import json
from pathlib import Path

import solution


def distance(a, b):
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5


def normalize_route(route):
    if not isinstance(route, list):
        return []
    normalized = []
    for item in route:
        if isinstance(item, bool):
            return []
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            return []
    return normalized


payload = json.loads(Path("cities.json").read_text(encoding="utf-8"))
cities = list(payload["cities"])
route = normalize_route(solution.build_route(cities))
valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
if valid:
    tour_length = sum(distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1]))
    score = 1.0 / tour_length
else:
    tour_length = 0.0
    score = 0.0
metrics = {
    "reward": round(score, 6),
    "score": round(score, 6),
    "combined_score": round(score, 6),
    "tour_length": round(tour_length, 6),
    "valid": 1.0 if valid else 0.0,
    "city_count": float(len(cities)),
}
Path("/logs/alab/logs/verifier/reward.json").write_text(
    json.dumps(metrics, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
Path("/logs/alab/logs/verifier/details.json").write_text(
    json.dumps({"route": route, "valid": valid}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"verified tour_length={metrics['tour_length']}")
print(f"verified reward={metrics['reward']}")
print("verified route=" + json.dumps(route))
PY
