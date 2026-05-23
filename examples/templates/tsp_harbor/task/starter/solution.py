from __future__ import annotations

IMPROVE_WITH_TWO_OPT = False


def _distance(a: dict[str, object], b: dict[str, object]) -> float:
    ax, ay = float(a["x"]), float(a["y"])
    bx, by = float(b["x"]), float(b["y"])
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _route_length(route: list[int], cities: list[dict[str, object]]) -> float:
    if not route:
        return 0.0
    return sum(_distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True))


def _two_opt(route: list[int], cities: list[dict[str, object]]) -> list[int]:
    best = route[:]
    improved = True
    while improved:
        improved = False
        for start in range(1, len(best) - 2):
            for end in range(start + 2, len(best) + 1):
                candidate = best[:start] + list(reversed(best[start:end])) + best[end:]
                if _route_length(candidate, cities) + 1e-12 < _route_length(best, cities):
                    best = candidate
                    improved = True
                    break
            if improved:
                break
    return best


def build_route(cities: list[dict[str, object]]) -> list[int]:
    route = list(range(len(cities)))
    if IMPROVE_WITH_TWO_OPT:
        return _two_opt(route, cities)
    return route
