# -*- coding: utf-8 -*-
"""v0.51: single source of truth for the deployed code version.

The worker stamps it into its heartbeat; the webui compares the stamp
against its own import, and the revive supervisor hot-swaps a worker
that runs older code. Root cause this closes: a pre-v0.48 worker
process (started at logon, never restarted by autostart - which only
launches when NOTHING is running) kept re-writing snapshot.json
without the alt-ref promotion for hours while the freshly rebuilt
webui showed the new UI, so departure times kept "coming back
missing" no matter how many fixes shipped."""

CODE_VERSION = "0.86"
