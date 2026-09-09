# -*- coding: utf-8 -*-
import urllib.request
for u in ["https://zh.wikipedia.org/api/rest_v1/page/summary/%E6%9D%AD%E5%B7%9E",
          "https://en.wikipedia.org/api/rest_v1/page/summary/Hangzhou",
          "https://commons.wikimedia.org/"]:
    try:
        r = urllib.request.urlopen(u, timeout=8)
        print("OK", r.status, u[:60])
    except Exception as e:
        print("ERR", str(e)[:80], u[:60])

