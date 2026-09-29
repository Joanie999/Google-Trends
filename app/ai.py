"""可选的 OpenAI 兼容 AI 适配器；未配置时使用本地规则结果。"""

from __future__ import annotations

import json
import os
import urllib.request

from .analytics import analyze_regions, analyze_series


def rule_analysis(result: dict, opportunities: list[dict] | None = None) -> dict:
    keywords = result.get("request", {}).get("keywords", [])
    trends = [analyze_series(result.get("series", []), keyword) for keyword in keywords]
    regions = [
        analyze_regions(result.get("regions", []), keyword) for keyword in keywords
    ]
    return {
        "provider": "rules",
        "summary": "规则分析已完成。结合持续性、波动率和地区分布判断，建议优先复核持续趋势且跨地区的关键词。",
        "trends": trends,
        "regions": regions,
        "opportunities": opportunities or [],
        "confidence": round(sum(item["confidence"] for item in trends) / len(trends), 2)
        if trends
        else 0.0,
    }


def ai_analysis(result: dict, opportunities: list[dict] | None = None) -> dict:
    fallback = rule_analysis(result, opportunities)
    base_url, api_key, model = (
        os.getenv("TRENDSCOPE_AI_BASE_URL"),
        os.getenv("TRENDSCOPE_AI_API_KEY"),
        os.getenv("TRENDSCOPE_AI_MODEL", "gpt-4o-mini"),
    )
    if not base_url or not api_key:
        return fallback
    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": "你是电商趋势分析助手。只返回 JSON，字段为 conclusion、evidence、risks、confidence。不要把 Google Trends 0-100 当成绝对搜索量。",
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"rules": fallback, "opportunities": opportunities or []},
                    ensure_ascii=False,
                ),
            },
        ],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode())
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return {
            **fallback,
            "provider": "ai",
            "ai": {
                "conclusion": str(parsed.get("conclusion", "")),
                "evidence": parsed.get("evidence", []),
                "risks": parsed.get("risks", []),
                "confidence": parsed.get("confidence", fallback["confidence"]),
            },
        }
    except Exception as exc:
        return {**fallback, "ai_error": f"AI 服务暂不可用：{type(exc).__name__}"}
