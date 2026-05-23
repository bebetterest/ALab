#!/bin/sh
set -eu

mkdir -p /logs/alab/logs/verifier
cd /workspace
python - <<'PY'
import json
from pathlib import Path

import solution

INVALID_ROUTE_PENALTY = 1_000_000_000.0


def next_unit(state):
    state &= 0xFFFFFFFF
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    state &= 0xFFFFFFFF
    return state, state / 0xFFFFFFFF


def generate_cities(instance, scale):
    count = int(instance["city_count"])
    state = int(instance["seed"]) or 1
    cities = []
    for _ in range(count):
        state, x_unit = next_unit(state)
        state, y_unit = next_unit(state)
        cities.append({"x": round(x_unit * scale, 6), "y": round(y_unit * scale, 6)})
    return cities


def distance(a, b):
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5


def normalize_route(route):
    if not isinstance(route, list):
        return []
    normalized = []
    for item in route:
        if isinstance(item, bool) or not isinstance(item, int):
            return []
        normalized.append(item)
    return normalized


payload = json.loads(Path("instances.json").read_text(encoding="utf-8"))
instances = list(payload["instances"])
scale = float(payload.get("coordinate_scale", 10000))
route_records = []
details = []
for instance in instances:
    name = str(instance["name"])
    cities = generate_cities(instance, scale)
    route = normalize_route(solution.build_route(cities))
    valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
    if valid:
        tour_length = sum(distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1]))
    else:
        tour_length = INVALID_ROUTE_PENALTY + len(cities)
    details.append(
        {
            "instance": name,
            "tour_length": round(tour_length, 6),
            "valid": 1.0 if valid else 0.0,
            "city_count": float(len(cities)),
        }
    )
    route_records.append({"instance": name, "route": route})

total_tour_length = round(sum(float(detail["tour_length"]) for detail in details), 6)
valid_instances = sum(1 for detail in details if detail["valid"] == 1.0)
city_count = sum(float(detail["city_count"]) for detail in details)
metrics = {
    "total_tour_length": total_tour_length,
    "reward": total_tour_length,
    "score": total_tour_length,
    "combined_score": total_tour_length,
    "valid": 1.0 if valid_instances == len(details) else 0.0,
    "valid_instance_count": float(valid_instances),
    "instance_count": float(len(details)),
    "city_count": city_count,
}
Path("/logs/alab/logs/verifier/reward.json").write_text(
    json.dumps(metrics, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
Path("/logs/alab/logs/verifier/details.json").write_text(
    json.dumps({"instances": route_records, "details": details}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"verified total_tour_length={metrics['total_tour_length']}")
print(f"verified valid={metrics['valid']}")
print("verified details=" + json.dumps(details))
PY
