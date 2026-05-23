from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

INVALID_ROUTE_PENALTY = 1_000_000_000.0


def _next_unit(state: int) -> tuple[int, float]:
    state &= 0xFFFFFFFF
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    state &= 0xFFFFFFFF
    return state, state / 0xFFFFFFFF


def _generate_cities(instance: dict[str, object], scale: float) -> list[dict[str, float]]:
    count = int(instance["city_count"])
    state = int(instance["seed"]) or 1
    cities = []
    for _ in range(count):
        state, x_unit = _next_unit(state)
        state, y_unit = _next_unit(state)
        cities.append({"x": round(x_unit * scale, 6), "y": round(y_unit * scale, 6)})
    return cities


def _distance(a: dict[str, object], b: dict[str, object]) -> float:
    return ((float(a["x"]) - float(b["x"])) ** 2 + (float(a["y"]) - float(b["y"])) ** 2) ** 0.5


def _load_solution(program_path: Path):
    module_path = program_path / "solution.py" if program_path.is_dir() else program_path
    spec = importlib.util.spec_from_file_location("candidate_solution", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load candidate solution")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _normalize_route(route: object) -> list[int]:
    if not isinstance(route, list):
        return []
    normalized = []
    for item in route:
        if isinstance(item, bool) or not isinstance(item, int):
            return []
        normalized.append(item)
    return normalized


def main() -> None:
    root = Path(sys.argv[1])
    solution = _load_solution(root)
    payload = json.loads((root / "instances.json").read_text(encoding="utf-8"))
    instances = list(payload["instances"])
    scale = float(payload.get("coordinate_scale", 10000))
    route_records = []
    details = []
    for instance in instances:
        name = str(instance["name"])
        cities = _generate_cities(instance, scale)
        route = _normalize_route(solution.build_route(cities))
        valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
        if valid:
            tour_length = sum(
                _distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True)
            )
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
        "combined_score": total_tour_length,
        "score": total_tour_length,
        "reward": total_tour_length,
        "valid": 1.0 if valid_instances == len(details) else 0.0,
        "valid_instance_count": float(valid_instances),
        "instance_count": float(len(details)),
        "city_count": city_count,
    }
    print(
        json.dumps(
            {
                "total_tour_length": metrics["total_tour_length"],
                "metrics": metrics,
                "artifacts": {
                    "routes": json.dumps(route_records),
                    "details": json.dumps(details),
                    "summary": f"valid={metrics['valid']} total_tour_length={metrics['total_tour_length']}",
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
