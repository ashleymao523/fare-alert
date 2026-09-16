# -*- coding: utf-8 -*-
"""v1.13 tests: v2 main entry - agents tab + cabin per-flight timetable."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def _read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


class V2WiringTests(unittest.TestCase):
    def test_agents_view_wired(self):
        app = _read("web", "src", "app.jsx")
        self.assertIn('["agents", "🤖 任务中心"]', app)
        self.assertIn('import AgentsView from "./components/AgentsView.jsx"', app)
        self.assertIn('{tab === "agents" ? <AgentsView /> : null}', app)
        comp = _read("web", "src", "components", "AgentsView.jsx")
        self.assertIn("fetchTasks", comp)
        self.assertIn("runAgentPath", comp)
        api = _read("web", "src", "lib", "api.js")
        self.assertIn("export function fetchTasks()", api)
        self.assertIn("export function runAgentPath(", api)

    def test_cabin_timetable_component(self):
        comp = _read("web", "src", "components", "CabinTimetable.jsx")
        self.assertIn("timetable", comp)
        self.assertIn("g.spark", comp)          # server-side 30-pt projection
        self.assertIn("window.open(row.url", comp)  # Booking deep link
        card = _read("web", "src", "components", "CabinCard.jsx")
        self.assertIn("import CabinTimetable", card)
        self.assertIn("<CabinTimetable timetable={data.timetable} />", card)

    def test_build_fresh(self):
        # dist bundle must exist and reference the new components
        idx = _read("web", "dist", "index.html")
        self.assertIn("/assets/index-", idx)
        assets = os.listdir(os.path.join("web", "dist", "assets"))
        self.assertTrue(any(a.endswith(".js") for a in assets))
        css = [a for a in assets if a.endswith(".css")][0]
        with open(os.path.join("web", "dist", "assets", css),
                  encoding="utf-8") as f:
            self.assertIn(".agents-grid", f.read())


if __name__ == "__main__":
    unittest.main()
