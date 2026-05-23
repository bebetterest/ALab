import json
import os
from pathlib import Path

SCORE = 0.40
STRATEGY = "baseline constant"


def compute_score() -> float:
    return SCORE


def main() -> None:
    score = compute_score()
    run_dir = Path(os.environ.get("ALAB_RUN_DIR", "."))
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "score.json").write_text(
        json.dumps({"score": score, "strategy": STRATEGY}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"strategy={STRATEGY}")
    print(f"reward={score:.3f}")


if __name__ == "__main__":
    main()
