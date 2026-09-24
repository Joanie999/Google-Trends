"""One bounded upstream call; stdout is reserved for the JSON protocol."""

import contextlib
import json
import sys


def main():
    message = json.load(sys.stdin)
    try:
        with contextlib.redirect_stdout(sys.stderr):
            import trendspyg

            payload = message["payload"]
            if message["kind"] == "rss":
                data = trendspyg.download_google_trends_rss(
                    geo=payload["geo"],
                    normalize=True,
                    cache=False,
                    include_images=False,
                    max_articles_per_trend=2,
                )
            else:
                options = {
                    "geo": payload["geo"],
                    "timeframe": payload["timeframe"],
                    "gprop": payload["gprop"],
                    "max_retries": 2,
                    "retry_wait": 3,
                    "cache": False,
                    "headless": True,
                }
                if len(payload["keywords"]) == 1:
                    data = trendspyg.download_google_trends_explore(
                        payload["keywords"][0], **options
                    )
                else:
                    data = trendspyg.download_google_trends_comparison(
                        payload["keywords"], **options
                    )
        result = {"data": data}
    except Exception as exc:
        text = f"{type(exc).__name__}: {exc}".lower()
        if "429" in text or "ratelimit" in text or "rate limit" in text:
            code, message, status = (
                "rate_limited",
                "Google 暂时限制了当前网络的查询。已暂停新趋势请求 5 分钟；上游限制可能持续更久，可稍后重试或打开官网。",
                429,
            )
        elif any(k in text for k in ["chrome", "driver", "sessionnotcreated"]):
            code, message, status = (
                "browser_unavailable",
                "无法启动 Chrome。请安装或更新 Google Chrome，并确保浏览器驱动可下载。",
                503,
            )
        else:
            code, message, status = (
                "upstream_unavailable",
                "暂时无法获取 Google 数据。请检查网络是否能访问 Google Trends，或稍后重试。",
                502,
            )
        result = {"error": {"code": code, "message": message, "status": status}}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
