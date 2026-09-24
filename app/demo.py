"""Explicit synthetic fixtures. Never used as a fallback for real requests."""

import hashlib
import math
from datetime import UTC, datetime, timedelta

from .models import ExploreRequest


def now_iso():
    return datetime.now(UTC).isoformat()


def explore_demo(request: ExploreRequest):
    days = {
        "now 7-d": 7,
        "today 1-m": 30,
        "today 3-m": 90,
        "today 12-m": 365,
        "today 5-y": 1825,
    }[request.timeframe]
    count = 48 if days == 7 else 53
    start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=days)
    series = []
    seeds = [
        int(
            hashlib.sha256((k + request.geo + request.gprop).encode()).hexdigest()[:6],
            16,
        )
        for k in request.keywords
    ]
    for i in range(count):
        values = {}
        for j, word in enumerate(request.keywords):
            seed = seeds[j]
            baseline = 30 + seed % 20
            value = (
                baseline
                + i * (0.3 + (seed % 5) / 14)
                + 9 * math.sin(i * 0.37 + j)
                + 5 * math.sin(i * 1.4 + seed)
                + 21 * math.exp(-(((i - 35 - j * 3) / 2.7) ** 2))
            )
            values[word] = max(1, min(100, round(value)))
        series.append(
            {
                "date": (start + timedelta(days=days * i / (count - 1))).isoformat(),
                "values": values,
                "is_partial": i == count - 1,
            }
        )
    peak = max(v for p in series for v in p["values"].values())
    for point in series:
        point["values"] = {k: round(v / peak * 100) for k, v in point["values"].items()}
    regions = []
    names = (
        ["加利福尼亚州", "纽约州", "华盛顿州", "马萨诸塞州", "得克萨斯州"]
        if request.geo == "US"
        else ["示例地区 A", "示例地区 B", "示例地区 C", "示例地区 D", "示例地区 E"]
    )
    for i, name in enumerate(names):
        weights = [
            max(9, 100 - i * 12 - j * 9 + (i * j * 5))
            for j in range(len(request.keywords))
        ]
        if len(weights) > 1:
            shares = [round(v / sum(weights) * 100) for v in weights]
            shares[-1] += 100 - sum(shares)
        else:
            shares = weights
        regions.append(
            {
                "name": name,
                "code": f"demo-{i}",
                "values": dict(zip(request.keywords, shares)),
            }
        )
    related = {"top": [], "rising": []}
    if len(request.keywords) == 1:
        for i, suffix in enumerate(
            ["教程", "使用方法", "最新消息", "价格", "替代方案"]
        ):
            related["rising"].append(
                {
                    "query": f"{request.keywords[0]} {suffix}",
                    "value": 500 - i * 75,
                    "formatted_value": f"+{500 - i * 75}%",
                }
            )
            related["top"].append(
                {
                    "query": f"{request.keywords[0]} {suffix}",
                    "value": 100 - i * 14,
                    "formatted_value": str(100 - i * 14),
                }
            )
    return {
        "request": request.model_dump(),
        "source": "synthetic-demo",
        "fetched_at": now_iso(),
        "cached": False,
        "series": series,
        "regions": regions,
        "related": related,
        "related_available": len(request.keywords) == 1,
    }


def trending_demo(geo):
    words = [
        "Gemini",
        "Nintendo Switch 2",
        "iPhone",
        "Champions League",
        "OpenAI",
        "Taylor Swift",
        "Formula 1",
        "Minecraft",
    ]
    return {
        "mode": "demo",
        "geo": geo,
        "source": "synthetic-demo",
        "fetched_at": now_iso(),
        "cached": False,
        "trends": [
            {
                "keyword": w,
                "rank": i + 1,
                "volume_text": f"{100 - i * 10}K+",
                "volume_min": (100 - i * 10) * 1000,
                "started_at": now_iso(),
                "news": [],
            }
            for i, w in enumerate(words)
        ],
    }
