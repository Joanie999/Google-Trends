"""轻量级本地计划器。默认不自动启动，可通过 TRENDSCOPE_SCHEDULER=1 开启。"""

from __future__ import annotations

import os
import threading

from .models import ExploreRequest


class LocalScheduler:
    def __init__(self, storage, service, interval=60):
        self.storage, self.service, self.interval = storage, service, interval
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(
            target=self._loop, name="trendscope-scheduler", daemon=True
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _loop(self):
        while not self.stop_event.wait(self.interval):
            self.run_due()

    def run_due(self):
        completed = []
        for item in self.storage.due_schedules():
            try:
                result = self.service.explore(
                    ExploreRequest(
                        keywords=item["keywords"],
                        geo=item["geo"],
                        timeframe=item["timeframe"],
                        gprop=item["gprop"],
                        mode="live",
                    )
                )
                self.storage.save_snapshot(result["request"], result)
                self.storage.mark_schedule(item["id"], "success", item["interval_days"])
                completed.append({"id": item["id"], "status": "success"})
            except (
                Exception
            ) as exc:  # upstream failures are recorded and do not create snapshots
                self.storage.mark_schedule(
                    item["id"], f"failed:{type(exc).__name__}", item["interval_days"]
                )
                completed.append({"id": item["id"], "status": "failed"})
        return completed


def enabled() -> bool:
    return os.getenv("TRENDSCOPE_SCHEDULER", "").casefold() in {"1", "true", "yes"}
