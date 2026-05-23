from __future__ import annotations

import json
import os
from pathlib import Path

STRATEGY = "baseline_fifo"
RESERVE_EXPRESS_STOCK = False
MAX_SPLIT_WAREHOUSES = 4

PRIORITY_WEIGHT = {
    "critical": 4.0,
    "high": 2.5,
    "normal": 1.0,
}


def load_json(name: str) -> object:
    return json.loads((Path(__file__).parent / "data" / name).read_text(encoding="utf-8"))


def order_key(order: dict[str, object]) -> tuple[float, float, str]:
    if STRATEGY == "priority_compact":
        return (
            -PRIORITY_WEIGHT[str(order["priority"])],
            float(order["sla_hours"]),
            str(order["id"]),
        )
    return (float(order["created_seq"]), 0.0, str(order["id"]))


def warehouse_rank(warehouse: dict[str, object], remaining: dict[str, int], order: dict[str, object]) -> tuple[float, float, str]:
    stock = warehouse["stock"]
    assert isinstance(stock, dict)
    covered = sum(min(int(stock.get(sku, 0)), qty) for sku, qty in remaining.items())
    if STRATEGY == "priority_compact":
        cold_bonus = 0 if (not order["cold_chain"] or warehouse["cold_chain"]) else 10
        return (-covered, cold_bonus, float(warehouse["distance_km"]), str(warehouse["id"]))
    return (float(warehouse["created_seq"]), 0.0, str(warehouse["id"]))


def allocate_order(order: dict[str, object], warehouses: list[dict[str, object]]) -> dict[str, object]:
    remaining = {sku: int(qty) for sku, qty in dict(order["items"]).items()}
    allocations: list[dict[str, object]] = []
    candidates = [
        warehouse
        for warehouse in warehouses
        if not order["cold_chain"] or bool(warehouse["cold_chain"])
    ]
    candidates.sort(key=lambda warehouse: warehouse_rank(warehouse, remaining, order))

    if RESERVE_EXPRESS_STOCK and order["priority"] != "critical":
        candidates = sorted(candidates, key=lambda warehouse: bool(warehouse["express_lane"]))

    for warehouse in candidates[:MAX_SPLIT_WAREHOUSES]:
        stock = warehouse["stock"]
        assert isinstance(stock, dict)
        picked: dict[str, int] = {}
        for sku, qty in list(remaining.items()):
            take = min(int(stock.get(sku, 0)), qty)
            if take <= 0:
                continue
            picked[sku] = take
            stock[sku] = int(stock.get(sku, 0)) - take
            remaining[sku] -= take
            if remaining[sku] == 0:
                del remaining[sku]
        if picked:
            allocations.append({"warehouse": warehouse["id"], "items": picked})
        if not remaining:
            break

    requested = sum(int(qty) for qty in dict(order["items"]).values())
    shipped = requested - sum(remaining.values())
    return {
        "order_id": order["id"],
        "priority": order["priority"],
        "cold_chain": order["cold_chain"],
        "requested_units": requested,
        "shipped_units": shipped,
        "fill_rate": shipped / requested,
        "split_count": len(allocations),
        "allocations": allocations,
        "unfilled": remaining,
    }


def score_manifest(manifest: list[dict[str, object]]) -> dict[str, float]:
    total_weight = 0.0
    weighted_fill = 0.0
    completed_weight = 0.0
    cold_weight = 0.0
    split_penalty = 0.0
    for row in manifest:
        weight = PRIORITY_WEIGHT[str(row["priority"])]
        total_weight += weight
        fill_rate = float(row["fill_rate"])
        weighted_fill += weight * fill_rate
        if fill_rate >= 1.0:
            completed_weight += weight
        if not row["cold_chain"] or fill_rate >= 1.0:
            cold_weight += weight
        split_penalty += max(0, int(row["split_count"]) - 1) * weight

    fill_component = weighted_fill / total_weight
    completion_component = completed_weight / total_weight
    cold_component = cold_weight / total_weight
    compactness = max(0.0, 1.0 - split_penalty / (2.5 * total_weight))
    score = 0.50 * fill_component + 0.25 * completion_component + 0.15 * cold_component + 0.10 * compactness
    return {
        "score": round(score, 6),
        "weighted_fill": round(fill_component, 6),
        "completed_weight": round(completion_component, 6),
        "cold_chain_success": round(cold_component, 6),
        "compactness": round(compactness, 6),
    }


def main() -> None:
    run_dir = Path(os.environ["ALAB_RUN_DIR"])
    run_dir.mkdir(parents=True, exist_ok=True)
    orders_payload = load_json("orders.json")
    warehouses = load_json("warehouses.json")
    assert isinstance(orders_payload, dict)
    assert isinstance(warehouses, list)
    orders = list(orders_payload["orders"])
    orders.sort(key=order_key)

    manifest = [allocate_order(order, warehouses) for order in orders]
    metrics = score_manifest(manifest)
    reward = {
        **metrics,
        "strategy": STRATEGY,
        "reserve_express_stock": RESERVE_EXPRESS_STOCK,
        "max_split_warehouses": MAX_SPLIT_WAREHOUSES,
    }

    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "reward.json").write_text(json.dumps(reward, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Fulfillment Planner Summary",
                "",
                f"- Strategy: `{STRATEGY}`",
                f"- Score: `{metrics['score']}`",
                f"- Weighted fill: `{metrics['weighted_fill']}`",
                f"- Completed priority weight: `{metrics['completed_weight']}`",
                f"- Cold-chain success: `{metrics['cold_chain_success']}`",
                f"- Compactness: `{metrics['compactness']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"strategy={STRATEGY}")
    print(f"score={metrics['score']:.6f}")


if __name__ == "__main__":
    main()
