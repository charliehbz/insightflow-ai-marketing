"""Explainable consumer-review analysis for InsightFlow.

The MVP intentionally combines light-weight NLP with transparent rules.  It can
run without paid APIs and degrades gracefully when optional NLP packages are not
installed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

import pandas as pd

try:  # Optional at development time; installed in production requirements.
    import jieba
except ImportError:  # pragma: no cover - exercised only in minimal environments
    jieba = None

try:
    from snownlp import SnowNLP
except ImportError:  # pragma: no cover
    SnowNLP = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover
    TfidfVectorizer = None


THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "功效表现": ("效果", "改善", "保湿", "补水", "修复", "泛红", "干燥", "紧绷", "持久", "变化", "有用"),
    "使用体验": ("质地", "吸收", "黏", "粘", "清爽", "搓泥", "刺激", "刺痛", "过敏", "香味", "味道", "肤感", "舒服"),
    "价格价值": ("价格", "贵", "便宜", "划算", "性价比", "容量", "优惠", "活动", "回购", "值"),
    "包装设计": ("包装", "按压", "泵", "设计", "破损", "瓶", "挤", "漏液"),
    "服务物流": ("物流", "客服", "退换", "发货", "收到", "快递", "售后"),
    "信任预期": ("宣传", "预期", "详情页", "正品", "真假", "成分", "温和", "安全", "承诺", "夸大"),
}

POSITIVE_WORDS = {
    "好", "很好", "喜欢", "满意", "惊喜", "推荐", "清爽", "舒服", "温和", "有效",
    "改善", "保湿", "补水", "修复", "划算", "方便", "快", "回购", "细腻", "稳定",
}
NEGATIVE_WORDS = {
    "差", "不好", "失望", "贵", "刺激", "刺痛", "过敏", "黏", "粘", "搓泥", "干燥",
    "紧绷", "破损", "漏液", "慢", "假", "夸大", "无效", "没用", "退货", "难用",
}
NEGATION_WORDS = ("不", "没", "无", "未", "并非")
STOPWORDS = {
    "的", "了", "和", "是", "也", "很", "都", "就", "但", "但是", "有点", "感觉", "这个",
    "产品", "使用", "用了", "一个", "没有", "还是", "比较", "真的", "非常", "我", "还", "在",
    "到", "与", "及", "而", "或", "后", "前", "会", "能", "更", "最", "被", "把", "又", "太",
}
FALLBACK_TERMS = tuple(
    sorted(
        {
            word
            for words in THEME_KEYWORDS.values()
            for word in words
            if len(word) > 1
        }
        | {
            "敏感肌", "轻薄", "水润", "用量", "客服", "及时", "完整", "一般", "明显",
            "好用", "不好用", "适合", "测试", "皮肤", "香精", "正装", "购买", "观察",
        },
        key=len,
        reverse=True,
    )
)


@dataclass
class AnalysisResult:
    dataframe: pd.DataFrame
    sentiment_summary: pd.DataFrame
    theme_summary: pd.DataFrame
    platform_summary: pd.DataFrame
    keywords: pd.DataFrame
    evidence: dict[str, list[dict[str, object]]]
    source_count: int
    analyzed_count: int
    duplicates_removed: int
    method_note: str


def _tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", " ", str(text)).strip().lower()
    if not cleaned:
        return []
    if jieba is not None:
        raw = jieba.lcut(cleaned)
    else:
        # Domain phrases keep the demo meaningful even before optional Chinese
        # tokenizers are installed.
        raw = [term for term in FALLBACK_TERMS for _ in range(cleaned.count(term))]
        raw.extend(re.findall(r"[a-z0-9]{2,}", cleaned))
    return [token.strip() for token in raw if token.strip() and token.strip() not in STOPWORDS]


def _lexicon_score(text: str) -> float:
    """Return a transparent 0–1 sentiment score."""

    positive = sum(text.count(word) for word in POSITIVE_WORDS)
    negative = sum(text.count(word) for word in NEGATIVE_WORDS)

    # Capture common negated-positive forms such as “不舒服/没有改善”.
    for negation in NEGATION_WORDS:
        for word in POSITIVE_WORDS:
            if f"{negation}{word}" in text:
                positive = max(0, positive - 1)
                negative += 1

    if positive + negative == 0:
        return 0.5
    return (positive + 1) / (positive + negative + 2)


def _text_sentiment(text: str) -> tuple[float, str]:
    lexicon_score = _lexicon_score(text)
    if SnowNLP is None:
        return lexicon_score, "情感词典"
    try:
        model_score = float(SnowNLP(text).sentiments)
        # Rules anchor obvious marketing-domain complaints; the statistical model
        # supplies nuance for phrases outside the small lexicon.
        return 0.55 * lexicon_score + 0.45 * model_score, "SnowNLP + 情感词典"
    except Exception:  # pragma: no cover - protects the UI from model edge cases
        return lexicon_score, "情感词典"


def _theme_for(text: str) -> tuple[str, int]:
    scores = {
        theme: sum(text.count(keyword) for keyword in keywords)
        for theme, keywords in THEME_KEYWORDS.items()
    }
    best_theme = max(scores, key=scores.get)
    return (best_theme, scores[best_theme]) if scores[best_theme] else ("其他", 0)


def _extract_keywords(texts: list[str], limit: int = 15) -> pd.DataFrame:
    tokenized = [_tokens(text) for text in texts]
    documents = [" ".join(tokens) for tokens in tokenized]
    documents = [document for document in documents if document]

    if documents and TfidfVectorizer is not None:
        try:
            vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
            matrix = vectorizer.fit_transform(documents)
            weights = matrix.mean(axis=0).A1
            pairs = sorted(
                zip(vectorizer.get_feature_names_out(), weights),
                key=lambda item: item[1],
                reverse=True,
            )[:limit]
            return pd.DataFrame(pairs, columns=["关键词", "重要度"]).assign(
                重要度=lambda frame: (frame["重要度"] * 100).round(1)
            )
        except ValueError:
            pass

    counts = Counter(token for row in tokenized for token in row)
    total = max(sum(counts.values()), 1)
    return pd.DataFrame(
        [(token, round(count / total * 100, 1)) for token, count in counts.most_common(limit)],
        columns=["关键词", "重要度"],
    )


def analyze_reviews(dataframe: pd.DataFrame, deduplicate: bool = True) -> AnalysisResult:
    """Analyze validated reviews and preserve every conclusion's source evidence."""

    source_count = len(dataframe)
    working = dataframe.copy().reset_index().rename(columns={"index": "source_row"})
    if deduplicate:
        working = working.drop_duplicates(subset=["review"], keep="first").copy()
    duplicates_removed = source_count - len(working)

    rows: list[dict[str, object]] = []
    methods: set[str] = set()
    for _, row in working.iterrows():
        text = str(row["review"])
        text_score, method = _text_sentiment(text)
        methods.add(method)
        rating = pd.to_numeric(row.get("rating"), errors="coerce")
        if pd.notna(rating):
            score = 0.65 * text_score + 0.35 * ((float(rating) - 1) / 4)
        else:
            score = text_score
        score = min(max(score, 0.0), 1.0)
        label = "正向" if score >= 0.62 else "负向" if score <= 0.38 else "中性"
        theme, theme_hits = _theme_for(text)
        rows.append(
            {
                **row.to_dict(),
                "情绪得分": round(score, 3),
                "情绪": label,
                "主题": theme,
                "主题命中词数": theme_hits,
            }
        )

    analyzed = pd.DataFrame(rows)
    if analyzed.empty:
        raise ValueError("去重后没有可分析的评论。")

    sentiment_order = ["正向", "中性", "负向"]
    sentiment_counts = analyzed["情绪"].value_counts().reindex(sentiment_order, fill_value=0)
    sentiment_summary = pd.DataFrame(
        {
            "情绪": sentiment_order,
            "评论数": sentiment_counts.values,
            "占比": (sentiment_counts.values / len(analyzed) * 100).round(1),
        }
    )

    theme_rows: list[dict[str, object]] = []
    evidence: dict[str, list[dict[str, object]]] = {}
    for theme, group in analyzed.groupby("主题", sort=False):
        negative = group[group["情绪"] == "负向"]
        share = len(group) / len(analyzed)
        negative_rate = len(negative) / len(group)
        negative_strength = (
            float((1 - negative["情绪得分"]).clip(lower=0).mean())
            if not negative.empty
            else 0.0
        )
        # A topic must be both common and negative to become a priority. Severity
        # adjusts the result but cannot let one isolated complaint dominate.
        priority_raw = share * negative_rate * (0.7 + 0.3 * negative_strength)
        theme_rows.append(
            {
                "主题": theme,
                "评论数": len(group),
                "声量占比": round(share * 100, 1),
                "负向数": len(negative),
                "负向率": round(negative_rate * 100, 1),
                "平均情绪": round(float(group["情绪得分"].mean()), 3),
                "_痛点原始值": priority_raw,
            }
        )
        candidates = negative.sort_values("情绪得分").head(3)
        if candidates.empty:
            candidates = group.sort_values("情绪得分").head(3)
        evidence[theme] = [
            {
                "review": item["review"],
                "score": item["情绪得分"],
                "sentiment": item["情绪"],
                "rating": item.get("rating"),
                "platform": item.get("platform"),
                "source_row": int(item["source_row"]) + 2,
            }
            for _, item in candidates.iterrows()
        ]

    theme_summary = pd.DataFrame(theme_rows)
    max_priority = float(theme_summary["_痛点原始值"].max())
    theme_summary["痛点优先级"] = (
        (theme_summary["_痛点原始值"] / max_priority * 100).round(1)
        if max_priority > 0
        else 0.0
    )
    theme_summary = theme_summary.drop(columns="_痛点原始值").sort_values(
        ["痛点优先级", "评论数"], ascending=False
    ).reset_index(drop=True)

    if analyzed["platform"].notna().any():
        platform_summary = (
            analyzed.assign(_count=1)
            .pivot_table(index="platform", columns="情绪", values="_count", aggfunc="sum", fill_value=0)
            .reindex(columns=sentiment_order, fill_value=0)
            .reset_index()
            .rename(columns={"platform": "平台"})
        )
    else:
        platform_summary = pd.DataFrame(columns=["平台", *sentiment_order])

    return AnalysisResult(
        dataframe=analyzed.reset_index(drop=True),
        sentiment_summary=sentiment_summary,
        theme_summary=theme_summary,
        platform_summary=platform_summary,
        keywords=_extract_keywords(analyzed["review"].astype(str).tolist()),
        evidence=evidence,
        source_count=source_count,
        analyzed_count=len(analyzed),
        duplicates_removed=duplicates_removed,
        method_note=f"文本情绪：{' / '.join(sorted(methods))}；评分权重 35%；主题：可解释关键词规则；关键词：TF-IDF。",
    )
