# TSP 参考解

当你需要一个强参考目标时，可以把 `solution.py` 复制到任意 TSP template
worktree 中可编辑的 `solution.py` 上。

该实现使用确定性的多起点 nearest-neighbor 构造，再基于候选邻居做有界
2-opt 改进。它保持相同的公开接口：

```python
def build_route(cities) -> list[int]:
    ...
```

它不声称是全局最优解，只是一个可复现、明显强于 starter 的目标，用来检查
template 和 evaluator 的行为是否符合预期。

在内置 15 组 benchmark 上，这个参考解应达到：

- `total_tour_length <= 2650000`
- `valid = 1`
- `instance_count = 15`
- `city_count = 8000`

starter baseline 会故意返回 `list(range(len(cities)))`，表现明显更差。在同一
benchmark 上 baseline 约为 `42000612.353972`，因此 agent 在达到这个参考目标前有
清晰的优化空间。
