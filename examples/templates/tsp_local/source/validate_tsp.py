from __future__ import annotations

import json
import os
from pathlib import Path

import solution


def _distance(a: dict[str, object], b: dict[str, object]) -> float:
    ax, ay = float(a["x"]), float(a["y"])
    bx, by = float(b["x"]), float(b["y"])
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _normalize_route(route: object) -> list[int]:
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


def _evaluate(cities: list[dict[str, object]], raw_route: object) -> tuple[list[int], dict[str, float]]:
    route = _normalize_route(raw_route)
    valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
    if valid:
        tour_length = sum(
            _distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True)
        )
        score = 1.0 / tour_length
    else:
        tour_length = 0.0
        score = 0.0
    metrics = {
        "score": round(score, 6),
        "reward": round(score, 6),
        "combined_score": round(score, 6),
        "tour_length": round(tour_length, 6),
        "valid": 1.0 if valid else 0.0,
        "city_count": float(len(cities)),
    }
    return route, metrics


def main() -> None:
    workspace = Path(__file__).parent
    run_dir = Path(os.environ["ALAB_RUN_DIR"])
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads((workspace / "cities.json").read_text(encoding="utf-8"))
    cities = list(payload["cities"])
    route, metrics = _evaluate(cities, solution.build_route(cities))

    (run_dir / "reward.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "route.json").write_text(json.dumps({"route": route}, indent=2) + "\n", encoding="utf-8")
    (run_dir / "summary.md").write_text(
        "\n".join(
            [
                "# TSP Route Summary",
                "",
                f"- Valid route: `{metrics['valid']}`",
                f"- Tour length: `{metrics['tour_length']}`",
                f"- Score: `{metrics['score']}`",
                f"- City count: `{int(metrics['city_count'])}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"tour_length={metrics['tour_length']:.6f}")
    print(f"score={metrics['score']:.6f}")


if __name__ == "__main__":
    main()
