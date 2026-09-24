"""Stable data adapter, bounded cache, and isolated upstream execution."""

import copy
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from .demo import explore_demo, now_iso, trending_demo
from .models import ExploreRequest

ROOT = Path(__file__).resolve().parent.parent


class ProviderError(Exception):
    def __init__(self, code, message, status=502):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class TTLCache:
    def __init__(self, ttl=900, maxsize=64, clock=time.monotonic):
        self.ttl, self.maxsize, self.clock = ttl, maxsize, clock
        self.items = OrderedDict()
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            entry = self.items.get(key)
            if not entry:
                return None
            expires, value = entry
            if self.clock() >= expires:
                del self.items[key]
                return None
            self.items.move_to_end(key)
            result = copy.deepcopy(value)
            result["cached"] = True
            return result

    def put(self, key, value):
        with self.lock:
            self.items[key] = (self.clock() + self.ttl, copy.deepcopy(value))
            self.items.move_to_end(key)
            while len(self.items) > self.maxsize:
                self.items.popitem(last=False)


def index_value(value):
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0 <= value <= 100
    ):
        raise ProviderError(
            "invalid_upstream", "Google 返回了无法识别的数据，请稍后重试。"
        )
    return value


def normalize_explore(raw, request):
    try:
        if not isinstance(raw, dict) or not isinstance(
            raw.get("interest_over_time"), list
        ):
            raise ValueError("missing series")
        single = len(request.keywords) == 1
        series = []
        for row in raw["interest_over_time"]:
            values = (
                {request.keywords[0]: index_value(row["value"])}
                if single
                else {k: index_value(row["values"][k]) for k in request.keywords}
            )
            if not isinstance(row["date"], str):
                raise ValueError("invalid date")
            datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
            series.append(
                {
                    "date": row["date"],
                    "values": values,
                    "is_partial": bool(row.get("is_partial", False)),
                }
            )
        if (
            not series
            or raw.get("is_empty")
            or not any(any(p["values"].values()) for p in series)
        ):
            raise ProviderError(
                "no_data",
                "当前关键词和筛选范围没有足够数据。请扩大时间或地区范围。",
                404,
            )
        regions = []
        region_rows = raw.get("interest_by_region", [])
        if not isinstance(region_rows, list):
            raise ValueError("invalid regions")
        for row in region_rows:
            values = (
                {request.keywords[0]: index_value(row["value"])}
                if single
                else {k: index_value(row["values"][k]) for k in request.keywords}
            )
            regions.append(
                {
                    "name": str(row["geo_name"]),
                    "code": str(row.get("geo_code", "")),
                    "values": values,
                }
            )
        related = raw.get("related_queries") or {"top": [], "rising": []}
        if not isinstance(related, dict):
            raise ValueError("invalid related queries")
        normalized_related = {}
        for group in ("top", "rising"):
            rows = related.get(group, [])
            if not isinstance(rows, list):
                raise ValueError("invalid related group")
            normalized_related[group] = []
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("query"), str):
                    raise ValueError("invalid related item")
                normalized_related[group].append(
                    {
                        "query": row["query"],
                        "value": row.get("value", ""),
                        "formatted_value": str(
                            row.get("formatted_value", row.get("value", ""))
                        ),
                    }
                )
        return {
            "request": request.model_dump(),
            "source": "google-trends",
            "fetched_at": raw.get("fetched_at") or now_iso(),
            "cached": False,
            "series": series,
            "regions": regions,
            "related": normalized_related,
            "related_available": single,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError(
            "invalid_upstream",
            "数据源格式发生变化，请稍后重试或在 Google Trends 中查看。",
        ) from exc


def kill_worker(process):
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)


def run_worker(kind, payload, timeout):
    process = subprocess.Popen(
        [sys.executable, "-m", "app.worker"],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        start_new_session=os.name != "nt",
    )
    try:
        stdout, _ = process.communicate(
            json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        try:
            kill_worker(process)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
        raise ProviderError(
            "timeout", "Google 查询超时。请稍后再试，或直接打开 Google Trends。", 504
        )
    try:
        result = json.loads(stdout)
        if "error" in result:
            error = result["error"]
            raise ProviderError(error["code"], error["message"], error["status"])
        return result["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ProviderError(
            "worker_failed", "数据服务未正常完成，请检查本机 Chrome 和网络连接。"
        ) from exc


class TrendsService:
    def __init__(self, runner=run_worker, clock=time.monotonic):
        self.runner, self.clock = runner, clock
        self.explore_cache = TTLCache(clock=clock)
        self.rss_cache = TTLCache(ttl=300, maxsize=20, clock=clock)
        self.explore_lock = threading.Lock()
        self.rss_lock = threading.Lock()
        self.next_explore = 0
        self.next_rss = 0

    def explore(self, request: ExploreRequest):
        if request.mode == "demo":
            return explore_demo(request)
        key = request.model_dump_json()
        cached = self.explore_cache.get(key)
        if cached:
            return cached
        if not self.explore_lock.acquire(blocking=False):
            raise ProviderError(
                "busy", "已有真实趋势查询正在进行，请等待完成后再试。", 429
            )
        try:
            if self.clock() < self.next_explore:
                raise ProviderError(
                    "cooldown",
                    f"为减少 Google 限流，请 {math.ceil(self.next_explore - self.clock())} 秒后再查询。",
                    429,
                )
            self.next_explore = self.clock() + 30
            try:
                result = normalize_explore(
                    self.runner("explore", request.model_dump(), 150), request
                )
            except ProviderError as exc:
                if exc.code == "rate_limited":
                    self.next_explore = self.clock() + 300
                raise
            self.explore_cache.put(key, result)
            return result
        finally:
            self.explore_lock.release()

    def trending(self, geo, mode):
        if mode == "demo":
            return trending_demo(geo)
        cached = self.rss_cache.get(geo)
        if cached:
            return cached
        if not self.rss_lock.acquire(blocking=False):
            raise ProviderError("busy", "热搜正在加载，请稍后重试。", 429)
        try:
            if self.clock() < self.next_rss:
                raise ProviderError("cooldown", "热搜请求过于频繁，请几秒后重试。", 429)
            self.next_rss = self.clock() + 5
            raw = self.runner("rss", {"geo": geo}, 35)
            if not isinstance(raw, dict) or not isinstance(raw.get("trends"), list):
                raise ProviderError(
                    "invalid_upstream", "热搜数据格式发生变化，请稍后重试。"
                )
            result = {
                "mode": mode,
                "geo": geo,
                "source": "google-trends-rss",
                "fetched_at": raw.get("fetched_at") or now_iso(),
                "cached": False,
                "trends": raw["trends"],
            }
            self.rss_cache.put(geo, result)
            return result
        finally:
            self.rss_lock.release()
