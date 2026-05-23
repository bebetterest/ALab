# TSP Harbor Template

Implement `build_route(cities)` in `solution.py`. Return a list of city indexes
that visits every city exactly once. The route is evaluated as a closed tour:
after the final city, it returns to the first city.

The public starter includes `instances.json` with 15 deterministic TSP instance
specifications: five 100-city instances, five 500-city instances, and five
1000-city instances. The verifier generates fixed coordinates from those specs,
checks every route for permutation validity, computes each Euclidean closed-tour
length, and minimizes the sum of all instance tour lengths.
