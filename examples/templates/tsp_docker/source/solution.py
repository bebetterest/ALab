from __future__ import annotations

IMPROVE_WITH_NEAREST_NEIGHBOR = False


def _distance(a: dict[str, object], b: dict[str, object]) -> float:
    ax, ay = float(a["x"]), float(a["y"])
    bx, by = float(b["x"]), float(b["y"])
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _nearest_neighbor(cities: list[dict[str, object]]) -> list[int]:
    if not cities:
        return []
    route = [0]
    unvisited = set(range(1, len(cities)))
    while unvisited:
        current = route[-1]
        next_city = min(unvisited, key=lambda city: (_distance(cities[current], cities[city]), city))
        route.append(next_city)
        unvisited.remove(next_city)
    return route


def build_route(cities: list[dict[str, object]]) -> list[int]:
    if IMPROVE_WITH_NEAREST_NEIGHBOR:
        return _nearest_neighbor(cities)
    return list(range(len(cities)))
