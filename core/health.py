# -*- coding: utf-8 -*-
"""Source health tracking: score, degrade flag, diagnose report (M2).

每轮 run_once 后由 update_from_crawl() 从 crawl_status.json 聚合各源成败:
- 检出: 任一步 error 即记一次失败, 诊断立即可用
- 降级: 单轮内同源 >=2 步失败(端点级故障)立即降级; 或累计连续 3 轮失败
- 恢复: 一轮全部成功即解除降级
状态原子写入 data/health.json, 供 Web UI 徽标与 MCP 输出。
"""
import datetime as dt
import json
import os
import re

WINDOW = 12          # rolling window of run results per source
DEGRADE_RUN_FAILS = 2   # >=2 failed steps in ONE run -> instant degrade
DEGRADE_CONSEC = 3      # 3 consecutive failing runs -> degrade

# (regex on error text, candidate cause, suggested action)
_CLASSIFY = [
    ("timeout|timed? ?out", "网络超时", "检查本机网络/代理; 若持续可在网页设置里拉长超时"),
    ("connection|reset|refused|dns|name resolution", "连接失败", "确认能否正常访问去哪儿/12306; 检查防火墙与 DNS"),
    ("403|429|too many|rate", "疑似反爬限频", "把轮询间隔拉长(interval_minutes>=30), 稍后观察是否恢复"),
    (r"5\d\d", "对方服务异常", "数据源服务端问题, 通常等待即可恢复"),
    ("json|keyerror|attributeerror|parse", "响应结构变化", "页面/接口可能改版, 到 GitHub 提 issue 附 run_id"),
    ("empty|无结果|0 条", "空结果", "确认城市名/日期窗口是否有效; 该线路可能暂无航班"),
]


def _now_iso(now=None):
    return (now or dt.datetime.now()).isoformat(timespec="seconds")


class SourceHealth:
    def __init__(self, path):
        self.path = path
        self.doc = self._read()

    def _read(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d.get("sources"), dict):
                return d
        except Exception:
            pass
        return {"sources": {}, "updated_at": None}

    def _save(self, now=None):
        self.doc["updated_at"] = _now_iso(now)
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.doc, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass

    def report(self, source, ok, fails_in_run=0, error="", now=None):
        """One run-level report for a source. ok=False means the run failed."""
        s = self.doc["sources"].setdefault(
            source, {"window": [], "consecutive_fails": 0, "degraded": False,
                     "last_error": "", "last_error_at": None, "last_ok_at": None})
        win = s["window"]
        win.append(1 if ok else 0)
        del win[:-WINDOW]
        if ok:
            s["consecutive_fails"] = 0
            s["degraded"] = False
            s["last_ok_at"] = _now_iso(now)
        else:
            s["consecutive_fails"] += 1
            if fails_in_run >= DEGRADE_RUN_FAILS or s["consecutive_fails"] >= DEGRADE_CONSEC:
                s["degraded"] = True
            s["last_error"] = str(error)[:200]
            s["last_error_at"] = _now_iso(now)

    def score(self, source):
        win = self.doc["sources"].get(source, {}).get("window") or []
        return round(100.0 * sum(win) / len(win)) if win else None

    def snapshot(self):
        """Summarized state for UI/MCP."""
        out = []
        for name, s in sorted(self.doc["sources"].items()):
            out.append({"source": name, "score": self.score(name),
                        "degraded": bool(s.get("degraded")),
                        "consecutive_fails": s.get("consecutive_fails", 0),
                        "last_error": s.get("last_error", ""),
                        "last_error_at": s.get("last_error_at"),
                        "last_ok_at": s.get("last_ok_at")})
        return {"updated_at": self.doc.get("updated_at"), "sources": out}

    def diagnose(self, source):
        """Diagnosis report: status + candidate causes with actions."""
        s = self.doc["sources"].get(source) or {}
        err = (s.get("last_error") or "").lower()
        cands = []
        for pat, cause, action in _CLASSIFY:
            if re.search(pat, err) and not any(c["cause"] == cause for c in cands):
                cands.append({"cause": cause, "action": action})
        if not cands and err:
            cands.append({"cause": "未分类错误",
                          "action": "复制错误信息到 GitHub issue, 附 run_id 与时间"})
        return {"source": source,
                "status": "degraded" if s.get("degraded") else
                          ("failing" if s.get("consecutive_fails") else "ok"),
                "score": self.score(source),
                "consecutive_fails": s.get("consecutive_fails", 0),
                "last_error": s.get("last_error", ""),
                "last_error_at": s.get("last_error_at"),
                "candidates": cands}


def update_from_crawl(data_dir, now=None):
    """Aggregate the newest finished run in crawl_status.json into health."""
    h = SourceHealth(os.path.join(data_dir, "health.json"))
    try:
        with open(os.path.join(data_dir, "crawl_status.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return h
    run = (doc.get("history") or [None])[0] if not doc.get("running") \
        else doc.get("current")
    if not run:
        return h
    per_src = {}
    for st in run.get("steps", []):
        if st.get("status") == "disabled":
            continue
        name = st.get("source", "?")
        d = per_src.setdefault(name, {"fails": 0, "err": "", "any": False})
        d["any"] = True
        if st.get("status") == "error":
            d["fails"] += 1
            d["err"] = d["err"] or st.get("error", "")
    for name, d in per_src.items():
        h.report(name, ok=(d["fails"] == 0), fails_in_run=d["fails"],
                 error=d["err"], now=now)
    h._save(now)
    return h
