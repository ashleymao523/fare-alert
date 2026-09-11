# -*- coding: utf-8 -*-
"""v0.29 v2 frontend hosting: /v2 serves the committed web/dist build
same-origin (no CORS), classic page keeps a visible entry link."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webui


class V2HostingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = webui.app.test_client()
        cls.dist = os.path.join(os.path.dirname(os.path.abspath(webui.__file__)),
                                "web", "dist")

    def test_v2_index_served_no_cache(self):
        if not os.path.exists(os.path.join(self.dist, "index.html")):
            self.skipTest("web/dist not built")
        r = self.client.get("/v2")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn('id="app"', body)
        self.assertIn("/v2/assets/", body)
        self.assertIn("no-cache", r.headers.get("Cache-Control", ""))

    def test_v2_asset_served(self):
        assets = os.path.join(self.dist, "assets")
        if not os.path.isdir(assets):
            self.skipTest("web/dist not built")
        js = [f for f in os.listdir(assets) if f.endswith(".js")]
        self.assertTrue(js, "no js bundle in dist")
        r = self.client.get("/v2/assets/" + js[0])
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r.headers.get("Content-Type", ""))

    def test_v2_no_path_traversal(self):
        """Security regression lock: /v2 must never serve files outside dist."""
        for p in ("/v2/../webui.py", "/v2/..%2F..%2Fwebui.py",
                  "/v2/assets/../../config.json", "/v2/..%5C..%5Cconfig.json"):
            r = self.client.get(p)
            self.assertNotEqual(r.status_code, 200,
                                "traversal leaked via %s -> %s" % (p, r.status_code))

    def test_v2_asset_immutable_cache(self):
        assets = os.path.join(self.dist, "assets")
        if not os.path.isdir(assets):
            self.skipTest("web/dist not built")
        js = [f for f in os.listdir(assets) if f.endswith(".js")]
        r = self.client.get("/v2/assets/" + js[0])
        self.assertEqual(r.status_code, 200)
        cc = r.headers.get("Cache-Control", "")
        self.assertIn("immutable", cc)
        self.assertIn("max-age=31536000", cc)

    def test_classic_links_to_v2(self):
        r = self.client.get("/classic")
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/v2"', r.get_data(as_text=True))

    def test_root_redirects_to_v2(self):
        """v0.32: v2 (8/8 tabs) is the default entry."""
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers.get("Location"), "/v2/")

    def test_v2_route_registered(self):
        rules = {r.rule for r in webui.app.url_map.iter_rules()}
        self.assertIn("/v2", rules)
        self.assertIn("/v2/<path:subpath>", rules)


if __name__ == "__main__":
    unittest.main()
