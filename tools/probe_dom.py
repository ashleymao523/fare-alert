# -*- coding: utf-8 -*-
"""Open qunar candidate URLs in real headless Edge, wait, then dump the
final URL + key DOM markers to decide if the flight-list page really loads.
"""
import argparse
import subprocess
import time
import re
import os
import sys
import urllib.parse

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

MARKERS = [
    "flightList", "flightlist", "航班", "起飞", "到达", "预订", "折扣",
    "低价", "筛选", "排序", "价格",
]

def dump(url, tag, budget):
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    udd = os.path.join(cwd, "data", "edge_prof_qunar_" + tag)
    out = os.path.join(cwd, "data", "qunar_" + tag + ".txt")
    if os.path.exists(out):
        os.remove(out)
    cmd = [
        EDGE, "--headless", "--disable-gpu", "--no-first-run",
        "--user-data-dir=" + udd,
        "--virtual-time-budget=" + str(budget),
        "--run-all-compositor-stages-before-draw",
        "--dump-dom", url,
    ]
    with open(out, "wb") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, timeout=90)
    data = open(out, "rb").read().decode("utf-8", "replace")
    print("== " + tag)
    # final url is not directly available from dump-dom; infer from content
    for m in MARKERS:
        cnt = data.count(m)
        if cnt:
            print("   marker %-6s x%d" % (m, cnt))
    t = re.search(r"<title>([^<]*)</title>", data)
    print("   title:", t.group(1) if t else "?", "len:", len(data))
    return data

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="t1")
    ap.add_argument("--budget", type=int, default=15000)
    ap.add_argument("url")
    a = ap.parse_args()
    dump(a.url, a.tag, a.budget)

