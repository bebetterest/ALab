# TSP Reference Solution

Copy `solution.py` over the editable `solution.py` in any TSP template
worktree when you want a strong local reference target.

The implementation uses deterministic multi-start nearest-neighbor
construction followed by bounded 2-opt improvement over nearest-neighbor
candidates. It keeps the same required public interface:

```python
def build_route(cities) -> list[int]:
    ...
```

This is not claimed to be globally optimal. It is a reproducible target that is
substantially better than the starter and useful for checking whether the
template and evaluator behave as expected.

On the bundled 15-instance benchmark, this reference solution should achieve:

- `total_tour_length <= 2650000`
- `valid = 1`
- `instance_count = 15`
- `city_count = 8000`

The starter baseline intentionally returns `list(range(len(cities)))` and is
much worse. On the same benchmark it measures about `42000612.353972`, so
agents have a clear optimization gap before reaching this reference target.
