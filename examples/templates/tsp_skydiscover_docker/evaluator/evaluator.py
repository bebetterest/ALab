from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


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
        if isinstance(item, bool):
            return []
        try:
            normalized.append(int(item))
        except (TypeError, ValueError):
            return []
    return normalized


def main() -> None:
    root = Path(sys.argv[1])
    solution = _load_solution(root)
    payload = json.loads((root / "cities.json").read_text(encoding="utf-8"))
    cities = list(payload["cities"])
    route = _normalize_route(solution.build_route(cities))
    valid = len(route) == len(cities) and sorted(route) == list(range(len(cities)))
    if valid:
        tour_length = sum(_distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True))
        score = 1.0 / tour_length
    else:
        tour_length = 0.0
        score = 0.0
    metrics = {
        "combined_score": round(score, 6),
        "score": round(score, 6),
        "reward": round(score, 6),
        "tour_length": round(tour_length, 6),
        "valid": 1.0 if valid else 0.0,
        "city_count": float(len(cities)),
    }
    print(
        json.dumps(
            {
                "combined_score": metrics["combined_score"],
                "metrics": metrics,
                "artifacts": {
                    "route": json.dumps(route),
                    "summary": f"valid={metrics['valid']} tour_length={metrics['tour_length']}",
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
