# -*- coding: utf-8 -*-
"""Probe cached OTA responses for embedded dep/arr times (read-only)."""
import io
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def keys_with(path, pattern):
    try:
        s = io.open(path, encoding="utf-8", errors="replace").read()
    except OSError as e:
        print(path, "unreadable:", e)
        return
    ks = sorted(set(re.findall(pattern, s)))
    print(path, len(s), "bytes; time-ish keys:", ks[:25])
    # show one sample context around the first hit
    m = re.search(pattern, s)
    if m:
        print("  sample:", s[max(0, m.start() - 40):m.end() + 120].replace("\n", " ")[:220])


for f in ("data/qnsearch.json", "data/qh5.html", "data/qlist.html"):
    keys_with(f, r'"([a-zA-Z]*(?:[Tt]ime|[Dd]epTime|[Aa]rrTime|depTime|arrTime)[a-zA-Z]*)"')

# JSON structure walk for qnsearch.json
try:
    d = json.load(io.open("data/qnsearch.json", encoding="utf-8"))
    def walk(o, depth=0, path=""):
        if depth > 4:
            return
        if isinstance(o, dict):
            for k, v in list(o.items())[:8]:
                walk(v, depth + 1, path + "." + str(k))
        elif isinstance(o, list) and o:
            walk(o[0], depth + 1, path + "[0]")
        else:
            if depth <= 3:
                print("leaf", path, repr(o)[:80])
    walk(d)
except Exception as e:
    print("qnsearch walk failed:", e)
