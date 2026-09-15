# -*- coding: utf-8 -*-
# v0.82: autostart installer that survives the MSIX-python registry
# veil. Field finding (2026-09-15, this host): the daily-driver python
# is the Microsoft Store MSIX build (WindowsApps\PythonSoftwareFoundation).
# MSIX packages get registry virtualization: HKCU\...\CurrentVersion\Run
# reads come back VEILED and writes are denied - while real Win32
# processes (PowerShell, reg.exe) see and write the true hive. So the
# install_autostart.ps1 HKCU Run entries installed fine, but python-based
# probes (doctor) false-negatived them. This installer adds a second,
# veil-proof mechanism: a plain .cmd in the user Startup folder
# (shell:startup). Filesystem access is NOT virtualized for MSIX python,
# both wrappers self-guard against double launch, explorer honors the
# folder at every logon.
from __future__ import annotations

import os
import sys


def startup_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
    return os.path.join(base, "Microsoft", "Windows", "Start Menu",
                        "Programs", "Startup")


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = startup_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "FareAlertStartup.cmd")
    body = "\r\n".join([
        "@echo off",
        "rem FareAlert logon launcher (v0.82). Both wrappers self-guard:",
        "rem they no-op when the webui port / worker loop is already up.",
        'start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass'
        ' -WindowStyle Hidden -File "%s"'
        % os.path.join(repo, "tools", "autostart_webui.ps1"),
        'start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass'
        ' -WindowStyle Hidden -File "%s"'
        % os.path.join(repo, "tools", "autostart_worker.ps1"),
        "exit /b 0",
        "",
    ])
    # mbcs == system ANSI (GBK here): cmd.exe parses batch files in the
    # OEM/ANSI codepage, and the repo path carries CJK chars.
    with open(path, "w", encoding="mbcs", newline="") as f:
        f.write(body)
    print("Startup folder : %s" % path)
    msix = "WindowsApps" in sys.executable
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            winreg.KEY_SET_VALUE)
        for name, wrapper in (("FareAlertWebUI", "autostart_webui.ps1"),
                              ("FareAlertWorker", "autostart_worker.ps1")):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ,
                              'powershell.exe -NoProfile -ExecutionPolicy '
                              'Bypass -WindowStyle Hidden -File "%s"'
                              % os.path.join(repo, "tools", wrapper))
        print("HKCU Run entries written (real hive on stock python hosts)")
    except OSError as e:
        if msix:
            print("HKCU Run write skipped: MSIX python registry veil (%s)"
                  % str(e).strip())
        else:
            print("WARN: HKCU Run write failed: %s" % e)
    print("doctor checks  : startup-folder file + HKCU Run best-effort")


if __name__ == "__main__":
    main()
