"""CSV loading, field normalization, and validation for InsightFlow."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd


STANDARD_COLUMNS = ("review", "rating", "date", "platform")
REQUIRED_COLUMNS = ("review",)
MAX_ROWS = 50_000

COLUMN_ALIASES: dict[str, set[str]] = {
    "review": {
        "review",
        "reviews",
        "comment",
        "comments",
        "text",
        "content",
        "feedback",
        "评论",
        "评论内容",
        "用户评论",
        "反馈",
        "内容",
    },
    "rating": {
        "rating",
        "ratings",
        "score",
        "star",
        "stars",
        "评分",
        "星级",
        "打分",
    },
    "date": {
        "date",
        "datetime",
        "created_at",
        "created",
        "time",
        "日期",
        "时间",
        "创建时间",
    },
    "platform": {
        "platform",
        "channel",
        "source",
        "平台",
        "渠道",
        "来源",
    },
}


@dataclass
class ValidationResult:
    """Result returned after validating and normalizing uploaded data."""

    dataframe: pd.DataFrame
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    renamed_columns: dict[str, str] = field(default_factory=dict)
    dropped_blank_reviews: int = 0
    duplicate_reviews: int = 0

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _canonicalize_header(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_").replace("-", "_")


def infer_column_mapping(columns: list[object]) -> dict[str, str]:
    """Return a source-to-standard column mapping based on known aliases."""

    normalized_to_source = {_canonicalize_header(column): str(column) for column in columns}
    mapping: dict[str, str] = {}

    for standard, aliases in COLUMN_ALIASES.items():
        normalized_aliases = {_canonicalize_header(alias) for alias in aliases}
        matches = [
            source
            for normalized, source in normalized_to_source.items()
            if normalized in normalized_aliases
        ]
        if matches:
            source = matches[0]
            if source != standard:
                mapping[source] = standard

    return mapping


def read_csv(source: str | Path | bytes | BinaryIO) -> pd.DataFrame:
    """Read a UTF-8 CSV and provide a clear error for common encoding issues."""

    if isinstance(source, bytes):
        source = BytesIO(source)

    try:
        return pd.read_csv(source)
    except UnicodeDecodeError:
        if hasattr(source, "seek"):
            source.seek(0)
        try:
            return pd.read_csv(source, encoding="gb18030")
        except UnicodeDecodeError as exc:
            raise ValueError("无法识别文件编码，请将文件另存为 UTF-8 CSV 后重试。") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError("CSV 文件为空，请上传包含表头和评论数据的文件。") from exc
    except pd.errors.ParserError as exc:
        raise ValueError("CSV 格式无法解析，请检查引号、逗号和换行是否完整。") from exc


def validate_and_normalize(df: pd.DataFrame) -> ValidationResult:
    """Normalize supported headers and validate rows for downstream analysis."""

    if df is None or df.empty:
        return ValidationResult(
            dataframe=pd.DataFrame(columns=STANDARD_COLUMNS),
            errors=["数据为空，请至少提供一条消费者评论。"],
        )

    working = df.copy()
    working.columns = [str(column).strip() for column in working.columns]

    duplicate_headers = working.columns[working.columns.duplicated()].tolist()
    if duplicate_headers:
        return ValidationResult(
            dataframe=working,
            errors=[f"存在重复列名：{', '.join(duplicate_headers)}。请修改后重新上传。"],
        )

    mapping = infer_column_mapping(list(working.columns))
    working = working.rename(columns=mapping)

    missing = [column for column in REQUIRED_COLUMNS if column not in working.columns]
    if missing:
        available = "、".join(str(column) for column in df.columns)
        return ValidationResult(
            dataframe=working,
            errors=[
                "未找到评论文本列。请使用 review、comment、text、评论或评论内容作为列名。"
                f" 当前列：{available}"
            ],
            renamed_columns=mapping,
        )

    if len(working) > MAX_ROWS:
        return ValidationResult(
            dataframe=working,
            errors=[f"当前文件包含 {len(working):,} 行，超过 {MAX_ROWS:,} 行上限。请抽样后重试。"],
            renamed_columns=mapping,
        )

    original_count = len(working)
    working["review"] = working["review"].fillna("").astype(str).str.strip()
    working = working[working["review"].ne("")].copy()
    dropped_blank_reviews = original_count - len(working)

    if working.empty:
        return ValidationResult(
            dataframe=working,
            errors=["评论文本列全部为空，无法继续分析。"],
            renamed_columns=mapping,
            dropped_blank_reviews=dropped_blank_reviews,
        )

    warnings: list[str] = []
    if dropped_blank_reviews:
        warnings.append(f"已忽略 {dropped_blank_reviews} 条空评论。")

    duplicate_reviews = int(working["review"].duplicated().sum())
    if duplicate_reviews:
        warnings.append(f"检测到 {duplicate_reviews} 条重复评论；当前保留，正式分析时可选择去重。")

    for column in STANDARD_COLUMNS:
        if column not in working.columns:
            working[column] = pd.NA

    if working["rating"].notna().any():
        numeric_rating = pd.to_numeric(working["rating"], errors="coerce")
        invalid_count = int((working["rating"].notna() & numeric_rating.isna()).sum())
        out_of_range = numeric_rating.notna() & ~numeric_rating.between(1, 5)
        if invalid_count:
            warnings.append(f"有 {invalid_count} 条评分无法转为数字，已设为空值。")
        if out_of_range.any():
            warnings.append(f"有 {int(out_of_range.sum())} 条评分不在 1–5 范围内，已设为空值。")
            numeric_rating = numeric_rating.mask(out_of_range)
        working["rating"] = numeric_rating
    else:
        warnings.append("未提供评分列；后续情绪判断将仅依据评论文本。")

    if working["date"].notna().any():
        parsed_dates = pd.to_datetime(working["date"], errors="coerce")
        invalid_dates = int((working["date"].notna() & parsed_dates.isna()).sum())
        if invalid_dates:
            warnings.append(f"有 {invalid_dates} 条日期无法识别，已设为空值。")
        working["date"] = parsed_dates
    else:
        warnings.append("未提供日期列；后续无法展示时间趋势。")

    if working["platform"].isna().all():
        warnings.append("未提供平台列；后续无法进行渠道对比。")
    else:
        working["platform"] = working["platform"].fillna("未知平台").astype(str).str.strip()

    ordered_columns = [*STANDARD_COLUMNS]
    extra_columns = [column for column in working.columns if column not in ordered_columns]
    working = working[ordered_columns + extra_columns].reset_index(drop=True)

    return ValidationResult(
        dataframe=working,
        warnings=warnings,
        renamed_columns=mapping,
        dropped_blank_reviews=dropped_blank_reviews,
        duplicate_reviews=duplicate_reviews,
    )


def load_and_validate(source: str | Path | bytes | BinaryIO) -> ValidationResult:
    """Convenience wrapper used by the Streamlit app and tests."""

    return validate_and_normalize(read_csv(source))
