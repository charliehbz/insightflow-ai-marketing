"""Generate a deterministic, clearly labeled simulated review dataset."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path


POSITIVE_REVIEWS = [
    "质地很轻薄，上脸吸收快，早上使用也不会搓泥。",
    "连续用了两周，皮肤泛红的情况有明显改善。",
    "成分比较温和，敏感肌使用没有出现刺激。",
    "包装设计简洁，按压泵控制用量很方便。",
    "保湿效果不错，晚上使用后第二天皮肤不会紧绷。",
    "活动价格很划算，容量和使用感都符合预期。",
    "物流速度快，收到时包装完整，客服回复也很及时。",
    "没有明显香精味，肤感清爽，夏天使用很舒服。",
]

NEUTRAL_REVIEWS = [
    "使用感比较清爽，但目前还没有看到明显变化。",
    "包装和详情页一致，效果还需要继续观察。",
    "质地偏水润，更适合晚上使用。",
    "价格不算便宜，等活动时可能会考虑回购。",
    "第一次购买，使用三天暂时没有不适。",
    "味道比较淡，个人可以接受。",
]

NEGATIVE_REVIEWS = [
    "价格偏高，实际容量比想象中小，性价比一般。",
    "用了以后有一点刺痛，敏感肌可能需要先做测试。",
    "按压泵不太好用，经常一下挤出太多。",
    "宣传说吸收很快，但在我脸上有点黏。",
    "物流等了很久，外包装到手时有轻微破损。",
    "使用一个月没有看到宣传中的明显效果。",
    "客服回复比较慢，退换货流程也不够清楚。",
    "香味有点重，和我期待的无香型不一样。",
]

PLATFORMS = ["小红书", "抖音", "天猫", "京东"]

CONTEXT_PREFIXES = [
    "",
    "我是敏感肌，",
    "换季期间使用，",
    "连续使用一段时间后，",
    "作为第一次购买的用户，",
    "在早晚护肤步骤中，",
    "看过详情页后下单，",
    "活动期间入手，",
]

SENTIMENT_SUFFIXES = {
    "positive": [
        "",
        "目前愿意继续使用。",
        "这点比我预期更好。",
        "会考虑购买正装。",
        "整体体验比较稳定。",
    ],
    "neutral": [
        "",
        "还需要继续观察。",
        "暂时没有明确结论。",
        "希望后续能看到更多变化。",
        "目前体验与预期基本一致。",
    ],
    "negative": [
        "",
        "希望品牌能给出更清楚的说明。",
        "暂时不会考虑回购。",
        "这点明显低于我的预期。",
        "希望后续版本能够改进。",
    ],
}


def build_rows(count: int, seed: int, duplicate_rate: float = 0.08) -> list[dict[str, object]]:
    random.seed(seed)
    start = date(2026, 7, 1)
    rows: list[dict[str, object]] = []

    sentiment_pool = (
        [("positive", text) for text in POSITIVE_REVIEWS] * 5
        + [("neutral", text) for text in NEUTRAL_REVIEWS] * 3
        + [("negative", text) for text in NEGATIVE_REVIEWS] * 4
    )

    generated_reviews: list[tuple[str, str]] = []
    seen_reviews: set[str] = set()

    for index in range(count):
        sentiment, base_review = random.choice(sentiment_pool)
        make_duplicate = bool(generated_reviews) and random.random() < duplicate_rate
        if make_duplicate:
            sentiment, review = random.choice(generated_reviews)
        else:
            prefix = random.choice(CONTEXT_PREFIXES)
            suffix = random.choice(SENTIMENT_SUFFIXES[sentiment])
            review = f"{prefix}{base_review}{suffix}"
            attempts = 0
            while review in seen_reviews and attempts < 20:
                prefix = random.choice(CONTEXT_PREFIXES)
                suffix = random.choice(SENTIMENT_SUFFIXES[sentiment])
                review = f"{prefix}{base_review}{suffix}"
                attempts += 1
            if review in seen_reviews:
                days = 7 + index % 24
                review = f"{review}这是连续使用第 {days} 天的记录。"
            seen_reviews.add(review)

        generated_reviews.append((sentiment, review))
        rating_ranges = {
            "positive": [4, 4, 5, 5, 5],
            "neutral": [3, 3, 4],
            "negative": [1, 2, 2, 3],
        }
        rows.append(
            {
                "review_id": f"SIM-{index + 1:04d}",
                "review": review,
                "rating": random.choice(rating_ranges[sentiment]),
                "date": (start + timedelta(days=random.randint(0, 89))).isoformat(),
                "platform": random.choice(PLATFORMS),
                "data_notice": "模拟数据，仅用于产品演示",
            }
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=180, help="Number of rows to generate")
    parser.add_argument("--seed", type=int, default=20271009, help="Random seed")
    parser.add_argument(
        "--duplicate-rate",
        type=float,
        default=0.08,
        help="Share of intentionally duplicated review text (0–0.3)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "sample_reviews.csv",
    )
    args = parser.parse_args()

    if not 1 <= args.count <= 10_000:
        raise SystemExit("--count must be between 1 and 10,000")
    if not 0 <= args.duplicate_rate <= 0.3:
        raise SystemExit("--duplicate-rate must be between 0 and 0.3")

    rows = build_rows(args.count, args.seed, args.duplicate_rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} simulated reviews at {args.output}")


if __name__ == "__main__":
    main()
