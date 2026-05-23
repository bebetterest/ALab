from __future__ import annotations


def _xy(city: dict[str, object]) -> tuple[float, float]:
    return float(city["x"]), float(city["y"])


def _distance(a: dict[str, object], b: dict[str, object]) -> float:
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def _distance_sq(a: dict[str, object], b: dict[str, object]) -> float:
    ax, ay = _xy(a)
    bx, by = _xy(b)
    return (ax - bx) ** 2 + (ay - by) ** 2


def _route_length(route: list[int], cities: list[dict[str, object]]) -> float:
    if not route:
        return 0.0
    return sum(_distance(cities[a], cities[b]) for a, b in zip(route, route[1:] + route[:1], strict=True))


def _candidate_starts(cities: list[dict[str, object]]) -> list[int]:
    if not cities:
        return []
    xs = [float(city["x"]) for city in cities]
    ys = [float(city["y"]) for city in cities]
    center = (sum(xs) / len(cities), sum(ys) / len(cities))
    starts = {
        0,
        min(range(len(cities)), key=lambda idx: (xs[idx], idx)),
        max(range(len(cities)), key=lambda idx: (xs[idx], -idx)),
        min(range(len(cities)), key=lambda idx: (ys[idx], idx)),
        max(range(len(cities)), key=lambda idx: (ys[idx], -idx)),
        min(range(len(cities)), key=lambda idx: ((xs[idx] - center[0]) ** 2 + (ys[idx] - center[1]) ** 2, idx)),
        max(range(len(cities)), key=lambda idx: ((xs[idx] - center[0]) ** 2 + (ys[idx] - center[1]) ** 2, -idx)),
    }
    for fraction in (0.25, 0.5, 0.75):
        starts.add(min(len(cities) - 1, int((len(cities) - 1) * fraction)))
    return sorted(starts)


def _nearest_neighbor(cities: list[dict[str, object]], start: int) -> list[int]:
    route = [start]
    unvisited = set(range(len(cities)))
    unvisited.remove(start)
    while unvisited:
        current = route[-1]
        next_city = min(unvisited, key=lambda city: (_distance_sq(cities[current], cities[city]), city))
        route.append(next_city)
        unvisited.remove(next_city)
    return route


def _nearest_candidates(cities: list[dict[str, object]], limit: int) -> list[list[int]]:
    candidates = []
    for idx, city in enumerate(cities):
        nearest = [
            (_distance_sq(city, other), other_idx)
            for other_idx, other in enumerate(cities)
            if other_idx != idx
        ]
        nearest.sort()
        candidates.append([other_idx for _distance_value, other_idx in nearest[:limit]])
    return candidates


def _two_opt(route: list[int], cities: list[dict[str, object]]) -> list[int]:
    if len(route) < 4:
        return route
    route = route[:]
    candidates = _nearest_candidates(cities, limit=24)
    positions = [0] * len(route)
    for index, city in enumerate(route):
        positions[city] = index

    for _pass in range(6):
        improved = False
        left = 0
        while left < len(route) - 2:
            a = route[left]
            b = route[left + 1]
            for c in candidates[a]:
                right = positions[c]
                if right <= left + 1 or right >= len(route) - 1:
                    continue
                d = route[right + 1]
                if a == d or b == c:
                    continue
                before = _distance(cities[a], cities[b]) + _distance(cities[c], cities[d])
                after = _distance(cities[a], cities[c]) + _distance(cities[b], cities[d])
                if before > after + 1e-9:
                    route[left + 1 : right + 1] = reversed(route[left + 1 : right + 1])
                    for index in range(left + 1, right + 1):
                        positions[route[index]] = index
                    improved = True
                    left = max(left - 2, 0)
                    break
            else:
                left += 1
        if not improved:
            break
    return route


def build_route(cities: list[dict[str, object]]) -> list[int]:
    if not cities:
        return []
    best = min(
        (_nearest_neighbor(cities, start) for start in _candidate_starts(cities)),
        key=lambda route: _route_length(route, cities),
    )
    return _two_opt(best, cities)
