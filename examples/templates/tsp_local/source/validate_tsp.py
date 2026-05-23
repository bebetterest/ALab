from __future__ import annotations

import json
import os
from pathlib import Path

import solution

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
    ax, ay = float(a["x"]), float(a["y"])
    bx, by = float(b["x"]), float(b["y"])
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _normalize_route(route: object) -> list[int]:
    if not isinstance(route, list):
        return []
    normalized = []
    for item in route:
        if isinstance(item, bool) or not isinstance(item, int):
            return []
        normalized.append(item)
    return normalized


def _evaluate_instance(
    name: str,
    cities: list[dict[str, object]],
    raw_route: object,
) -> tuple[list[int], dict[str, float | str]]:
    route = _normalize_route(raw_route)
    valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
    if valid:
        tour_length = sum(
            _distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True)
        )
    else:
        tour_length = INVALID_ROUTE_PENALTY + len(cities)
    detail: dict[str, float | str] = {
        "instance": name,
        "tour_length": round(tour_length, 6),
        "valid": 1.0 if valid else 0.0,
        "city_count": float(len(cities)),
    }
    return route, detail


def main() -> None:
    workspace = Path(__file__).parent
    run_dir = Path(os.environ["ALAB_RUN_DIR"])
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads((workspace / "instances.json").read_text(encoding="utf-8"))
    instances = list(payload["instances"])
    scale = float(payload.get("coordinate_scale", 10000))
    route_records = []
    details = []
    for instance in instances:
        name = str(instance["name"])
        cities = _generate_cities(instance, scale)
        route, detail = _evaluate_instance(name, cities, solution.build_route(cities))
        details.append(detail)
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

    (run_dir / "reward.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "route.json").write_text(
        json.dumps({"instances": route_records, "details": details}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "summary.md").write_text(
        "\n".join(
            [
                "# TSP Multi-Instance Route Summary",
                "",
                "- Score direction: `minimize`",
                f"- All instances valid: `{metrics['valid']}`",
                f"- Total tour length: `{metrics['total_tour_length']}`",
                f"- Instance count: `{int(metrics['instance_count'])}`",
                f"- City count: `{int(metrics['city_count'])}`",
                "",
                "| Instance | Cities | Valid | Tour length |",
                "| --- | ---: | ---: | ---: |",
                *[
                    f"| {detail['instance']} | {int(float(detail['city_count']))} | "
                    f"{int(float(detail['valid']))} | {float(detail['tour_length']):.6f} |"
                    for detail in details
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"total_tour_length={metrics['total_tour_length']:.6f}")
    print(f"valid={metrics['valid']:.0f}")


if __name__ == "__main__":
    main()
