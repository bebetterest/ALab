from __future__ import annotations

KEYWORD_WEIGHTS = {
    "outage": 0.35,
    "down": 0.25,
    "data loss": 0.25,
    "security": 0.12,
    "latency": 0.08,
    "billing": 0.04,
    "vip": 0.04,
    "breach": 0.00,
    "unable to login": 0.00,
    "customer impact": 0.00,
}

NEGATIVE_WEIGHTS = {
    "cosmetic": -0.18,
    "documentation": -0.12,
    "question": -0.10,
}

THRESHOLD = 0.65


def score_ticket(text: str) -> float:
    normalized = text.lower()
    score = 0.10
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in normalized:
            score += weight
    for keyword, weight in NEGATIVE_WEIGHTS.items():
        if keyword in normalized:
            score += weight
    return max(0.0, min(1.0, score))


def classify_ticket(text: str) -> bool:
    return score_ticket(text) >= THRESHOLD


def main() -> None:
    demo_cases = [
        "regional outage down for clinic network",
        "billing question about invoice wording",
        "security breach with customer impact for vip account",
    ]
    reward = sum(1 for case in demo_cases if classify_ticket(case)) / len(demo_cases)
    print(f"reward={reward:.3f}")


if __name__ == "__main__":
    main()
