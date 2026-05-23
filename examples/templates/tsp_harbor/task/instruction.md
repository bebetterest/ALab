# TSP Harbor Template

Implement `build_route(cities)` in `solution.py`. Return a list of city indexes
that visits every city exactly once. The route is evaluated as a closed tour:
after the final city, it returns to the first city.

The public starter includes the city coordinates in `cities.json`. The verifier
checks route validity, computes Euclidean tour length, and maximizes a score
derived from `1 / tour_length`.
