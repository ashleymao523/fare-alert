# -*- coding: utf-8 -*-
"""M1 handshake self-test: initialize / tools/list / tools/call round-trip.

安全设计:watch_add 只加测试线路(杭州-宁波)并立即 watch_del 清理,
结束后校验 config.json 线路数与开始时一致。Run: python tools/mcp_selftest.py
"""
import json
import atexit
import os
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Client:
    def __init__(self, home):
        self.p = subprocess.Popen(
            [sys.executable, os.path.join(BASE, "mcp_server.py")],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=BASE,
            env={**os.environ, "FAREALERT_HOME": home})
        self.i = 0

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def req(self, method, params=None):
        self.i += 1
        m = {"jsonrpc": "2.0", "id": self.i, "method": method}
        if params is not None:
            m["params"] = params
        self.send(m)
        return json.loads(self.p.stdout.readline())

    def notify(self, method, params=None):
        m = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            m["params"] = params
        self.send(m)

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


def result_text(resp):
    return "".join(c.get("text", "") for c in resp["result"]["content"])


def main():
    from core.config import load_config
    # v0.21: run against a throwaway FAREALERT_HOME copy so concurrent
    # runs (e.g. acceptance + selftest) never touch the real config.json.
    home = tempfile.mkdtemp(prefix="farealert-selftest-")
    ctx = {"dir": home, "proc": None}  # atexit-serviced: orphan-process + tmpdir

    def _cleanup():
        p = ctx["proc"]
        if p and p.poll() is None:
            try:
                p.stdin.close()
                p.wait(timeout=5)
            except Exception:
                p.kill()
        shutil.rmtree(ctx["dir"], ignore_errors=True)

    atexit.register(_cleanup)
    real_cfg = os.path.join(BASE, "config.json")
    real_bytes = open(real_cfg, "rb").read() if os.path.exists(real_cfg) else b""
    if real_bytes:
        with open(os.path.join(home, "config.json"), "wb") as f:
            f.write(real_bytes)
    cfg_path = os.path.join(home, "config.json")
    n_before = len(load_config(cfg_path)["routes"])
    fails = []

    c = Client(home)
    ctx["proc"] = c.p
    r = c.req("initialize", {"protocolVersion": "2024-11-05",
                             "clientInfo": {"name": "selftest", "version": "0"}})
    ok = r["result"]["serverInfo"]["name"] == "fare-alert"
    print(("PASS" if ok else "FAIL") + " initialize serverInfo")
    if not ok:
        fails.append("initialize")

    c.notify("notifications/initialized")

    r = c.req("tools/list")
    names = sorted(t["name"] for t in r["result"]["tools"])
    expect = sorted(["fare_search", "train_search", "watch_add", "watch_del",
                     "snapshot_get", "reverse_search", "verify_release",
                     "patrol_run"])
    ok = names == expect and all(t.get("inputSchema") for t in r["result"]["tools"])
    print(("PASS" if ok else "FAIL") + " tools/list = %s" % names)
    if not ok:
        fails.append("tools/list")

    c.send([1, 2])  # JSON batch array: must yield -32600, not crash
    line = json.loads(c.p.stdout.readline())
    ok = line["error"]["code"] == -32600
    print(("PASS" if ok else "FAIL") + " batch array -> -32600, no crash")
    if not ok:
        fails.append("batch")

    c.notify("ping")  # notification: must NOT be replied
    rid = c.i + 1
    r = c.req("ping")
    ok = r["id"] == rid and "result" in r  # first reply after notify is ours
    print(("PASS" if ok else "FAIL") + " notification ping silent")
    if not ok:
        fails.append("notification")

    r = c.req("tools/call", {"name": "snapshot_get", "arguments": {}})
    ok = not r["result"].get("isError")
    print(("PASS" if ok else "FAIL") + " tools/call snapshot_get")
    if not ok:
        fails.append("snapshot_get")

    r = c.req("tools/call", {"name": "watch_add",
                             "arguments": {"text": "杭州飞宁波400以内"}})
    ok = "已添加监控" in result_text(r) and not r["result"].get("isError")
    print(("PASS" if ok else "FAIL") + " watch_add hangzhou-ningbo")
    if not ok:
        fails.append("watch_add")

    in_cfg = any(x["id"] == "hangzhou-ningbo"
                 for x in load_config(cfg_path)["routes"])
    print(("PASS" if in_cfg else "FAIL") + " config contains new route")
    if not in_cfg:
        fails.append("config-route")

    r = c.req("tools/call", {"name": "watch_del",
                             "arguments": {"route_id": "hangzhou-ningbo"}})
    ok = "已删除" in result_text(r) and not r["result"].get("isError")
    print(("PASS" if ok else "FAIL") + " watch_del cleanup")
    if not ok:
        fails.append("watch_del")

    n_after = len(load_config(cfg_path)["routes"])
    ok = n_after == n_before
    print(("PASS" if ok else "FAIL") + " config route count restored %d->%d"
          % (n_before, n_after))
    if not ok:
        fails.append("restore")

    r = c.req("tools/call", {"name": "verify_release",
                             "arguments": {"steps": ["ui_check"]}})
    ok = "all_ok" in result_text(r) and not r["result"].get("isError")
    print(("PASS" if ok else "FAIL") + " tools/call verify_release(ui_check)")
    if not ok:
        fails.append("verify_release")

    c.close()
    untouched = (open(real_cfg, "rb").read() == real_bytes) if real_bytes else True
    print(("PASS" if untouched else "FAIL") + " real config.json untouched")
    if not untouched:
        fails.append("real-config-touched")
    shutil.rmtree(home, ignore_errors=True)
    print("selftest: %s (%d checks)" % ("ALL PASS" if not fails else "FAIL " + str(fails),
                                        11 - len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
