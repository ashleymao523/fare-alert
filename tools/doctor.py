# -*- coding: utf-8 -*-
"""v0.76 deployment doctor - one-shot health report for any deployed box.

Local box (file + live API checks):
    python tools/doctor.py
Remote box over LAN (API checks only):
    python tools/doctor.py --url http://192.168.1.5:8765

Rows are PASS / WARN / FAIL. Exit 0 when nothing FAILs (WARN alone is fine),
exit 1 otherwise - safe to wire into any uptime wrapper or upgrade script.
"""
import argparse
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _load_json(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def fetch_health(base):
    """GET {base}/api/health; None when the webui is down."""
    try:
        import urllib.request
        with urllib.request.urlopen(base.rstrip("/") + "/api/health",
                                    timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def fetch_text(base, path):
    try:
        import urllib.request
        with urllib.request.urlopen(base.rstrip("/") + path, timeout=8) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def check_webui(h):
    if not h:
        return FAIL, "webui 不可达 (/api/health 无响应)"
    return PASS, "webui 在线"


def check_snapshot(h):
    age = ((h or {}).get("snapshot") or {}).get("age_min")
    if age is None:
        return FAIL, "快照缺失或无 updated_at"
    if age > 24 * 60:
        return FAIL, "快照已 %.1f 小时未刷新" % (age / 60.0)
    if age > 6 * 60:
        return WARN, "快照 %.1f 小时未刷新(桌面可能刚开机, catch-up 会补)" % (age / 60.0)
    return PASS, "快照 %.0f 分钟前刷新" % age


def check_worker(h):
    w = (h or {}).get("worker")
    if not w:
        return WARN, "worker 未运行 - 跑 tools/autostart_worker.ps1 拉起"
    if not w.get("ok"):
        return FAIL, "worker 最近一轮失败(心跳 ok=false)"
    age = w.get("age_min") or 0
    if age > 120:
        return FAIL, "worker 心跳 %.0f 分钟无更新" % age
    return PASS, "worker 运行中, 心跳 %.0f 分钟前" % age


def check_code_sync(h):
    w = (h or {}).get("worker") or {}
    if not w:
        return WARN, "worker 未运行, 无法比对代码版本"
    if not w.get("code_synced"):
        return FAIL, "worker 代码落后(%s != webui) - 跑 tools/restart_all.ps1" % (
            w.get("code_ver"),)
    return PASS, "worker 与 webui 代码同版本 (%s)" % w.get("code_ver")


def check_board(h):
    b = (h or {}).get("board") or {}
    flights = b.get("flights") or 0
    dows = b.get("dows") or {}
    covered = sum(1 for v in dows.values() if v)
    if flights == 0:
        return WARN, "班期库为空 - worker 每日运行自然沉淀"
    if covered < 5:
        return WARN, "班期库 %d 班, 星期覆盖 %d/7(沉淀中)" % (flights, covered)
    # v0.83: name the missing dows + the two heal paths so the gap
    # reads actionable instead of mystical: the board API only returns
    # today+tomorrow rows, so a dow fills either on its own weekday
    # (worker runs) or instantly via a point-fill bookmark capture.
    if covered < 7:
        names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        missing = [names[int(k)] for k, v in sorted(
            (dows or {}).items(), key=lambda kv: int(kv[0])) if not v]
        return PASS, ("班期库 %d 班, 星期覆盖 %d/7 (缺%s: 该星期几运行日自动补;"
                      " 精查书签回填任意该日航班立即补)" % (
                          flights, covered, "、".join(missing)))
    return PASS, "班期库 %d 班, 星期覆盖 %d/7" % (flights, covered)


def check_backup(h):
    b = (h or {}).get("backup")
    if not b:
        return WARN, "备份状态未知(v0.75 前的 webui?)"
    if not b.get("count"):
        return WARN, "尚无自动备份 - 首轮调度会自动创建"
    return PASS, "自动备份 %d 份, 最近 %s" % (b.get("count"), b.get("last"))


def check_push(cfg):
    p = (cfg or {}).get("push") or {}
    if (p.get("bark_key") or "").strip() or (p.get("serverchan_sendkey") or "").strip():
        return PASS, "推送渠道已配置"
    return WARN, "未配置推送渠道 - iPhone 提醒不会触发"


def check_interval(cfg):
    iv = ((cfg or {}).get("schedule") or {}).get("interval_minutes")
    if not iv:
        return WARN, "schedule.interval_minutes 未设置"
    if iv < 30:
        return FAIL, "查询间隔 %s 分钟 < 30(合规红线)" % iv
    return PASS, "查询间隔 %s 分钟" % iv


def check_deploy():
    """v0.77: where are we running? Container deployments only sediment
    the sched-board dow library when FA_ROLE includes the worker."""
    if os.path.exists("/.dockerenv"):
        role = os.environ.get("FA_ROLE", "all")
        if role in ("all", "worker"):
            return PASS, "容器部署 (FA_ROLE=%s, 含爬虫循环)" % role
        return WARN, "容器 FA_ROLE=%s 不含爬虫 - 班期库不会沉淀" % role
    return PASS, "本机部署 (worker 由 restart_all/计划任务拉起)"


def check_autostart():
    """v0.79: reboot survivability - if neither the HKCU Run entries nor
    the scheduled tasks exist, a reboot silently kills both the panel
    and the board sedimentation loop.
    v0.82: also probe the user Startup folder (shell:startup) - the
    veil-proof mechanism on MSIX-python hosts where HKCU Run reads come
    back virtualized (see tools/install_autostart.py field notes)."""
    if os.name != "nt":
        return PASS, "非 Windows (见部署指南对应形态)"
    found = []
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run")
        names = set()
        i = 0
        while True:
            try:
                names.add(winreg.EnumValue(k, i)[0])
                i += 1
            except OSError:
                break
        for n in ("FareAlertWebUI", "FareAlertWorker"):
            if n in names:
                found.append(n)
    except OSError:
        pass
    msix = "WindowsApps" in sys.executable
    startup_cmd = os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming"),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
        "FareAlertStartup.cmd")
    if len(found) == 2:
        return PASS, ("开机自启已装 (webui+worker, HKCU Run"
                      + ("; 启动文件夹另有一层" if os.path.exists(startup_cmd)
                         else "") + ")")
    if not found:
        # task-mode installs (install_autostart.ps1 -Mode task) land in
        # the scheduler instead of the registry - probe it once.
        try:
            out = subprocess.run(
                ["schtasks", "/query", "/fo", "csv", "/nh"],
                capture_output=True, text=True, timeout=8).stdout or ""
            if "FareAlertWebUI" in out and "FareAlertWorker" in out:
                return PASS, "开机自启已装 (webui+worker, 计划任务)"
            if "FareAlert" in out:
                found = [x for x in ("FareAlertWebUI", "FareAlertWorker")
                         if x in out]
        except Exception:
            pass
    if os.path.exists(startup_cmd):
        return PASS, ("开机自启已装 (启动文件夹 FareAlertStartup.cmd"
                      + (", MSIX python 注册表探测被遮蔽 - Run 项以此为准"
                         if msix else "") + ")")
    if not found:
        return WARN, "未装开机自启 - 重启后面板与班期沉淀停摆; 运行 tools/install_autostart.ps1"
    return WARN, ("自启不完整(%s) - 再跑一次 tools/install_autostart.ps1 补齐"
                  % ",".join(found))


def check_pwa(base):
    html = fetch_text(base, "/v2/")
    if html is None:
        return FAIL, "/v2/ 页面不可达"
    missing = [t for t in ("manifest.webmanifest", "apple-touch-icon")
               if t not in html]
    man = fetch_text(base, "/static/manifest.webmanifest")
    if missing:
        return FAIL, "v2 页面缺 PWA 标签: %s" % ",".join(missing)
    if man is None:
        return FAIL, "/static/manifest.webmanifest 不可达"
    return PASS, "v2 PWA 就绪(主屏图标+全屏)"


def check_dist():
    p = os.path.join(ROOT, "web", "dist", "index.html")
    if not os.path.exists(p):
        return FAIL, "web/dist 缺失 - 先在 web/ 跑 npm run build"
    html = io.open(p, encoding="utf-8").read()
    if "manifest.webmanifest" not in html:
        return FAIL, "dist/index.html 缺 manifest 标签(需重新 build)"
    return PASS, "dist 构建产物含 PWA 标签"


def run_all(base, local=True):
    h = fetch_health(base)
    cfg = _load_json(os.path.join(ROOT, "config.json")) if local else None
    rows = [
        ("deploy", check_deploy()),
        ("autostart", check_autostart()),
        ("webui", check_webui(h)),
        ("snapshot", check_snapshot(h)),
        ("worker", check_worker(h)),
        ("code-sync", check_code_sync(h)),
        ("board", check_board(h)),
        ("backup", check_backup(h)),
    ]
    if local:
        rows += [
            ("push", check_push(cfg)),
            ("interval", check_interval(cfg)),
            ("dist", check_dist()),
        ]
    rows.append(("pwa", check_pwa(base)))
    return rows


def main():
    ap = argparse.ArgumentParser(description="fare-alert deployment doctor")
    ap.add_argument("--url", default="http://127.0.0.1:8765")
    args = ap.parse_args()
    base = args.url if "://" in args.url else "http://" + args.url
    rows = run_all(base, local=("127.0.0.1" in base or "localhost" in base))
    bad = 0
    print("fare-alert deployment doctor -> " + base)
    for name, (level, detail) in rows:
        mark = {"PASS": "OK ", "WARN": "!! ", "FAIL": "XX "}[level]
        print("  %s %-10s %s" % (mark, name, detail))
        bad += 1 if level == FAIL else 0
    print("verdict: %d FAIL / %d checks" % (bad, len(rows)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
