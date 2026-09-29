"""可解释的 Google Trends 需求真实性与 Amazon 机会分析。"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from difflib import SequenceMatcher


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _slope(values):
    if len(values) < 2:
        return 0.0
    x_mean = (len(values) - 1) / 2
    y_mean = statistics.fmean(values)
    denominator = sum((i - x_mean) ** 2 for i in range(len(values)))
    return sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values)) / denominator


def analyze_series(series: list[dict], keyword: str) -> dict:
    values = [
        _number(row.get("values", {}).get(keyword))
        for row in series
        if not row.get("is_partial")
    ]
    values = [value for value in values if value is not None]
    coverage = round(len(values) / len(series), 3) if series else 0.0
    if len(values) < 6:
        return {
            "keyword": keyword,
            "classification": "数据不足",
            "confidence": 0.2,
            "evidence": ["完整数据点少于 6 个，暂不能区分趋势与噪音。"],
            "sample_count": len(values),
            "coverage": coverage,
            "average": None,
            "recent_average": None,
            "change_pct": None,
            "peak": None,
            "peak_duration": 0,
            "volatility": None,
            "slope": None,
        }
    split = max(4, min(len(values) // 2, 8))
    recent = values[-split:]
    prior = values[-split * 2 : -split]
    average = statistics.fmean(values)
    recent_average = statistics.fmean(recent)
    prior_average = statistics.fmean(prior) if prior else average
    change_pct = (
        round((recent_average / prior_average - 1) * 100, 1) if prior_average else 0.0
    )
    peak = max(values)
    threshold = peak * 0.8
    peak_duration = 0
    run = 0
    for value in values:
        run = run + 1 if value >= threshold else 0
        peak_duration = max(peak_duration, run)
    volatility = statistics.pstdev(values) / average if average else 0.0
    slope = _slope(values)
    evidence = []
    if change_pct >= 25:
        evidence.append(f"近期均值较前期上升 {change_pct:.1f}%。")
    elif change_pct <= -25:
        evidence.append(f"近期均值较前期下降 {abs(change_pct):.1f}%。")
    if peak_duration <= max(2, len(values) // 8) and peak >= max(70, average * 1.8):
        evidence.append("峰值持续时间较短，需警惕事件型爆发。")
    if volatility >= 0.65:
        evidence.append("波动率较高，方向性不足。")
    if slope > 0.35:
        evidence.append("长期斜率为正，关注度基线逐步抬升。")
    if not evidence:
        evidence.append("当前窗口内未发现显著异常，需求相对稳定。")
    if change_pct >= 30 and peak_duration <= max(2, len(values) // 8):
        classification = "短期爆发"
    elif slope > 0.25 and change_pct >= 8 and volatility < 0.65:
        classification = "持续趋势"
    elif volatility >= 0.65 and abs(change_pct) < 35:
        classification = "噪音"
    elif abs(change_pct) < 20 and volatility < 0.45:
        classification = "稳定"
    else:
        classification = "待观察"
    confidence = min(
        0.98,
        max(
            0.35, 0.45 + min(len(values) / 100, 0.3) + (0.15 if coverage >= 0.8 else 0)
        ),
    )
    return {
        "keyword": keyword,
        "classification": classification,
        "confidence": round(confidence, 2),
        "evidence": evidence,
        "sample_count": len(values),
        "coverage": coverage,
        "average": round(average, 1),
        "recent_average": round(recent_average, 1),
        "change_pct": change_pct,
        "peak": round(peak, 1),
        "peak_duration": peak_duration,
        "volatility": round(volatility, 3),
        "slope": round(slope, 3),
    }


def analyze_regions(regions: list[dict], keyword: str) -> dict:
    rows = [
        (str(r.get("name", "")), _number(r.get("values", {}).get(keyword)))
        for r in regions
    ]
    rows = [(name, value) for name, value in rows if value is not None and value > 0]
    if not rows:
        return {
            "keyword": keyword,
            "classification": "数据不足",
            "coverage": 0,
            "top_share": 0,
            "top5_share": 0,
            "concentration": 0,
            "evidence": ["当前范围没有有效地区数据。"],
            "top_regions": [],
        }
    rows.sort(key=lambda pair: pair[1], reverse=True)
    total = sum(value for _, value in rows)
    top_share = rows[0][1] / total if total else 0
    top5_share = sum(value for _, value in rows[:5]) / total if total else 0
    concentration = sum((value / total) ** 2 for _, value in rows) if total else 0
    classification = (
        "局部集中" if top_share >= 0.45 or concentration >= 0.28 else "跨地区"
    )
    evidence = [
        f"最高地区占有效地区总量 {top_share * 100:.1f}%。",
        f"前五地区占比 {top5_share * 100:.1f}%。",
    ]
    if classification == "局部集中":
        evidence.append("需求主要集中在少数地区，进入市场前应单独验证该区域。")
    else:
        evidence.append("需求分布较广，区域误判风险相对较低。")
    return {
        "keyword": keyword,
        "classification": classification,
        "coverage": round(len(rows) / max(len(regions), 1), 3),
        "top_share": round(top_share, 3),
        "top5_share": round(top5_share, 3),
        "concentration": round(concentration, 3),
        "evidence": evidence,
        "top_regions": [
            {"name": name, "value": round(value, 1)} for name, value in rows[:5]
        ],
    }


def normalize_keyword(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def match_score(google_keyword: str, amazon_keyword: str) -> tuple[float, str]:
    left, right = normalize_keyword(google_keyword), normalize_keyword(amazon_keyword)
    if not left or not right:
        return 0.0, "none"
    if left == right:
        return 1.0, "exact"
    left_tokens, right_tokens = set(left.split()), set(right.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    similarity = SequenceMatcher(None, left, right).ratio()
    score = max(overlap, similarity * 0.9)
    return round(score, 3), "token" if overlap >= similarity * 0.9 else "similar"


def opportunity_rows(trend: dict, amazon_rows: list[dict]) -> list[dict]:
    analyses = {
        item["keyword"]: item
        for item in [
            analyze_series(trend.get("series", []), k)
            for k in trend.get("request", {}).get("keywords", [])
        ]
    }
    rows = []
    for amazon in amazon_rows:
        candidate = str(amazon.get("keyword", "")).strip()
        if not candidate:
            continue
        best = max(
            ((*match_score(google, candidate), google) for google in analyses),
            default=(0.0, "none", ""),
        )
        similarity, match_type, google_keyword = best
        if similarity < 0.25:
            continue
        analysis = analyses[google_keyword]
        rise = max(0.0, min(100.0, float(analysis.get("change_pct") or 0) + 50))
        long_tail = min(20.0, max(0, len(normalize_keyword(candidate).split()) - 1) * 6)
        volume = _number(amazon.get("search_volume"))
        rank = _number(amazon.get("rank"))
        amazon_low = (
            10.0
            if (rank is not None and rank >= 50)
            or (volume is not None and volume < 1000)
            else 4.0
        )
        score = min(
            100.0, max(0.0, rise * 0.45 + similarity * 25 + long_tail + amazon_low)
        )
        rows.append(
            {
                "keyword": candidate,
                "google_keyword": google_keyword,
                "match_type": match_type,
                "similarity": similarity,
                "google_change_pct": analysis.get("change_pct"),
                "trend_classification": analysis.get("classification"),
                "search_volume": volume,
                "rank": rank,
                "competition": amazon.get("competition"),
                "opportunity_score": round(score, 1),
                "reason": f"Google 近期变化 {analysis.get('change_pct') if analysis.get('change_pct') is not None else '—'}%，匹配度 {similarity:.0%}，Amazon 竞争信号偏低。",
            }
        )
    return sorted(rows, key=lambda row: row["opportunity_score"], reverse=True)
