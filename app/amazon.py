"""Amazon 关键词 CSV 解析与安全校验。"""

from __future__ import annotations

import csv
import io
import re

from .analytics import normalize_keyword

ALIASES = {
    "keyword": {
        "keyword",
        "keywords",
        "关键词",
        "搜索词",
        "search term",
        "term",
        "query",
    },
    "search_volume": {"search volume", "search_volume", "volume", "搜索量", "月搜索量"},
    "rank": {"rank", "ranking", "排名", "自然排名"},
    "competition": {"competition", "竞争度", "竞争", "difficulty"},
    "asin": {"asin", "asin码", "商品asin"},
}


def _header(value):
    return re.sub(
        r"\s+", " ", str(value or "").replace("\ufeff", "").strip().casefold()
    )


def _number(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if number >= 0 else None


def parse_csv(content: bytes | str) -> tuple[list[dict], list[str]]:
    text = (
        content.decode("utf-8-sig", errors="replace")
        if isinstance(content, bytes)
        else content.lstrip("\ufeff")
    )
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 缺少表头")
    columns = {}
    for field in reader.fieldnames:
        normalized = _header(field)
        for target, aliases in ALIASES.items():
            if normalized in aliases:
                columns[target] = field
    if "keyword" not in columns:
        raise ValueError("CSV 必须包含 keyword、关键词或 search term 列")
    rows, warnings = [], []
    for index, source in enumerate(reader, 2):
        keyword = " ".join(str(source.get(columns["keyword"], "")).split())
        if not keyword:
            warnings.append(f"第 {index} 行关键词为空，已跳过")
            continue
        if len(keyword) > 200:
            warnings.append(f"第 {index} 行关键词过长，已跳过")
            continue
        row = {"keyword": keyword, "normalized": normalize_keyword(keyword)}
        for field in ("search_volume", "rank"):
            row[field] = (
                _number(source.get(columns[field])) if field in columns else None
            )
            if (
                field in columns
                and source.get(columns[field], "").strip()
                and row[field] is None
            ):
                warnings.append(f"第 {index} 行 {field} 不是有效数字，按空值处理")
        row["competition"] = (
            str(source.get(columns["competition"], "")).strip()[:100]
            if "competition" in columns
            else ""
        )
        row["asin"] = (
            str(source.get(columns["asin"], "")).strip()[:30]
            if "asin" in columns
            else ""
        )
        rows.append(row)
    if not rows:
        raise ValueError("CSV 中没有可导入的关键词")
    return rows[:10000], warnings
