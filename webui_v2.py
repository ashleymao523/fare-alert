# -*- coding: utf-8 -*-
"""v2 frontend hosting: serves web/dist at /v2 (same-origin, no CORS needed).

The build output is committed to the repo, so deployment still needs
zero Node tooling; rebuild only when web/src changes (cd web && npm run build).
"""
import os

from flask import send_from_directory


def register_v2(app):
    dist = os.path.join(app.root_path, "web", "dist")

    def _index():
        path = os.path.join(dist, "index.html")
        if not os.path.exists(path):
            return ("v2 frontend not built: run cd web && npm install && npm run build", 503)
        resp = send_from_directory(dist, "index.html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    app.add_url_rule("/v2", "v2_index", _index)
    app.add_url_rule("/v2/", "v2_index_slash", _index)

    def _asset(subpath):
        if not os.path.exists(os.path.join(dist, "index.html")):
            return ("v2 frontend not built: run cd web && npm install && npm run build", 503)
        resp = send_from_directory(dist, subpath)
        if subpath.startswith("assets/"):  # vite hash filenames are immutable
            resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return resp

    app.add_url_rule("/v2/<path:subpath>", "v2_asset", _asset)
