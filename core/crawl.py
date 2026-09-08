# -*- coding: utf-8 -*-
"""Crawl run telemetry: per-source steps written to data/crawl_status.json.

每次 run_once 记录: 每个数据源(去哪儿日历/12306/推送)的 开始时间/耗时/状态/
结果条数/错误信息, 供 Web UI 爬虫监控面板实时展示。写入全部异常安全,
遥测失败绝不影响主流程。
"""
import datetime as dt
import json
import os
import threading
import uuid

_lock = threading.RLock()
MAX_HISTORY = 20


class CrawlRecorder:
    """Records one crawl run step by step (atomic file writes, cross-process safe)."""

    def __init__(self, data_dir):
        self.path = os.path.join(data_dir, "crawl_status.json")
        self.run = None

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"running": False, "current": None, "history": []}

    def _write(self, doc):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def begin(self, trigger="cli"):
        with _lock:
            self.run = {
                "run_id": dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6],
                "trigger": trigger,
                "started_at": dt.datetime.now().isoformat(timespec="seconds"),
                "steps": [],
            }
            doc = self._read()
            doc["running"] = True
            doc["current"] = self.run
            doc["updated_at"] = self.run["started_at"]
            self._write(doc)

    def step(self, source, label, action, status, ms, count=0, error="", cached=False):
        """status: ok | error | disabled"""
        with _lock:
            if not self.run:
                return
            step = {
                "source": source, "label": label, "action": action,
                "status": status, "ms": int(ms), "count": int(count or 0),
                "error": str(error)[:200], "cached": bool(cached),
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
            }
            self.run["steps"].append(step)
            doc = self._read()
            doc["current"] = self.run
            doc["updated_at"] = step["ts"]
            self._write(doc)

    def finish(self, summary=None):
        with _lock:
            if not self.run:
                return
            now = dt.datetime.now()
            self.run["finished_at"] = now.isoformat(timespec="seconds")
            try:
                t0 = dt.datetime.fromisoformat(self.run["started_at"])
                self.run["duration_ms"] = int((now - t0).total_seconds() * 1000)
            except Exception:
                self.run["duration_ms"] = 0
            self.run["summary"] = summary or {}
            self.run["ok"] = all(s["status"] != "error" for s in self.run["steps"])
            doc = self._read()
            doc["history"] = ([self.run] + doc.get("history", []))[:MAX_HISTORY]
            doc["running"] = False
            doc["current"] = None
            doc["updated_at"] = self.run["finished_at"]
            self._write(doc)
            self.run = None
