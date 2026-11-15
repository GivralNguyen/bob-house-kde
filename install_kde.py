#!/usr/bin/env python3
"""Install, activate, inspect, or restore Bob's native Plasma wallpaper."""
from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
PLUGIN = "org.bobhouse.desktop"
HANDLER = "bob-house-kde-action.desktop"


def xdg(name, fallback):
    value = os.environ.get(name, "")
    return Path(value) if value and Path(value).is_absolute() else Path.home() / fallback


DATA = xdg("XDG_DATA_HOME", ".local/share")
CONFIG = xdg("XDG_CONFIG_HOME", ".config")
STATE = xdg("XDG_STATE_HOME", ".local/state") / "bob-house-kde"
BACKUP = STATE / "wallpaper-before-bob.json"
APPLETS = CONFIG / "plasma-org.kde.plasma.desktop-appletsrc"


def run(args, timeout=30, check=True):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def qdbus_command():
    for candidate in ("qdbus6", "qdbus-qt6", "/usr/lib/qt6/bin/qdbus", "/usr/lib64/qt6/bin/qdbus"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("Qt 6 qdbus is missing; run ./install.sh to install dependencies")


def script(source):
    return run([qdbus_command(), "org.kde.plasmashell", "/PlasmaShell",
                "org.kde.PlasmaShell.evaluateScript", source])


def snapshot():
    return json.loads(script("""
var out=[];
desktops().forEach(function(d) {
    d.currentConfigGroup=["Wallpaper",d.wallpaperPlugin,"General"];
    var c={}; d.configKeys.forEach(function(k){ c[k]=d.readConfig(k); });
    out.push({id:d.id,screen:d.screen,type:d.type,wallpaper:d.wallpaperPlugin,config:c});
});
print(JSON.stringify(out));
"""))


def save_backup():
    if BACKUP.exists():
        return json.loads(BACKUP.read_text())
    current = snapshot()
    if any(d["wallpaper"] == PLUGIN for d in current):
        raise RuntimeError("Bob is already active, but its previous wallpaper backup is missing.")
    STATE.mkdir(parents=True, exist_ok=True)
    handler = run(["xdg-mime", "query", "default", "x-scheme-handler/bobhouse"], check=False)
    data = {"version": 1, "created": datetime.datetime.now().astimezone().isoformat(),
            "desktops": current, "previous_uri_handler": handler}
    temporary = BACKUP.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(BACKUP)
    if APPLETS.exists():
        shutil.copy2(APPLETS, STATE / "desktop-appletsrc.before-bob")
    return data


def desktop_quote(path):
    # Desktop Entry Exec quoting, rather than shell quoting.
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'


def install_files():
    package = ROOT / "plasma" / PLUGIN
    manifest = json.loads((package / "metadata.json").read_text())
    if manifest.get("KPlugin", {}).get("Id") != PLUGIN:
        raise RuntimeError("Unexpected wallpaper package ID")
    if not (package / "contents/ui/Data.js").is_file():
        raise RuntimeError("Build the wallpaper's Data.js before installing")
    if not (ROOT / "assets/rooms/rooms.json").is_file():
        raise RuntimeError("The room collection has not been built")
    destination = DATA / "plasma/wallpapers" / PLUGIN
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, destination, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    applications = DATA / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    entry = applications / HANDLER
    entry.write_text("\n".join([
        "[Desktop Entry]", "Type=Application", "Name=Bob House KDE Actions",
        "Comment=Open an object in the Bob desktop wallpaper",
        "Exec=/usr/bin/python3 " + desktop_quote(ROOT / "action_handler.py") + " %u",
        "Icon=user-home", "Terminal=false", "NoDisplay=true",
        "MimeType=x-scheme-handler/bobhouse;", "StartupNotify=false", "",
    ]))
    run(["desktop-file-validate", str(entry)])
    run(["xdg-mime", "default", HANDLER, "x-scheme-handler/bobhouse"])
    if shutil.which("update-desktop-database"):
        run(["update-desktop-database", str(applications)], check=False)
    print(f"Installed native wallpaper: {destination}")


def wait_for_plasma():
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        try:
            current = snapshot()
            if current:
                return current
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
        time.sleep(.4)
    raise RuntimeError("Plasma did not become ready; the previous configuration backup is " + str(BACKUP))


def change_layouts(targets):
    """Use Plasma's standard Desktop layout so Folder View cannot eat clicks.

    Only the selected desktop containment's plugin entry changes. Files on the
    Desktop and panels remain untouched. Plasma's service is briefly restarted
    to load its new containment type; existing application windows keep running.
    """
    current = snapshot()
    changes = [(d, targets[d["screen"]]) for d in current
               if d["screen"] in targets and d["type"] != targets[d["screen"]]]
    if not changes:
        return
    try:
        run(["systemctl", "--user", "stop", "plasma-plasmashell.service"])
        for desktop, target in changes:
            run(["kwriteconfig6", "--file", str(APPLETS), "--group", "Containments",
                 "--group", str(desktop["id"]), "--key", "plugin", target])
    finally:
        run(["systemctl", "--user", "start", "plasma-plasmashell.service"])
    wait_for_plasma()


def restore_offline(backup):
    """Recover wallpaper/layout even when Plasma's D-Bus interface is down."""
    try:
        run(["systemctl", "--user", "stop", "plasma-plasmashell.service"], check=False)
        for desktop in backup["desktops"]:
            prefix = ["kwriteconfig6", "--file", str(APPLETS), "--group", "Containments",
                      "--group", str(desktop["id"])]
            run(prefix + ["--key", "plugin", desktop["type"]])
            run(prefix + ["--key", "wallpaperplugin", desktop["wallpaper"]])
            for key, value in desktop["config"].items():
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, list):
                    value = ",".join(str(item) for item in value)
                run(prefix + ["--group", "Wallpaper", "--group", desktop["wallpaper"],
                              "--group", "General", "--key", key, str(value)])
    finally:
        run(["systemctl", "--user", "start", "plasma-plasmashell.service"])
    wait_for_plasma()


def activate():
    backup = save_backup()
    install_files()
    try:
        current = snapshot()
        change_layouts({d["screen"]: "org.kde.desktopcontainment" for d in current if d["screen"] >= 0})
        uri = (ROOT / "assets").as_uri() + "/"
        script("""
desktops().forEach(function(d) {
    if (d.screen < 0) return;
    d.wallpaperPlugin=%s;
    d.currentConfigGroup=["Wallpaper",%s,"General"];
    d.writeConfig("AssetRoot",%s);
    d.writeConfig("RoomId","study");
    d.writeConfig("Animations",true);
    d.reloadConfig();
});
""" % (json.dumps(PLUGIN), json.dumps(PLUGIN), json.dumps(uri)))
        current = snapshot()
        if not current or any(d["wallpaper"] != PLUGIN for d in current if d["screen"] >= 0):
            raise RuntimeError("KDE did not select the Bob wallpaper")
        print(json.dumps(current, indent=2))
        print("Restore command:", sys.executable, str(Path(__file__).resolve()), "restore")
    except Exception:
        # A broken desktop integration must return to the prior wallpaper.
        try:
            restore(backup)
        except Exception as error:
            print("Automatic restore also failed:", error, file=sys.stderr)
        raise


def restore(backup=None):
    backup = backup or json.loads(BACKUP.read_text())
    records = backup["desktops"]
    try:
        snapshot()
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
        restore_offline(backup)
        print("Restored the previous desktop layout and wallpaper using the saved configuration.")
        return
    change_layouts({d["screen"]: d["type"] for d in records})
    script("""
var saved=%s;
desktops().forEach(function(d) {
    var previous=saved.find(function(p){return p.screen===d.screen;});
    if (!previous) return;
    d.wallpaperPlugin=previous.wallpaper;
    d.currentConfigGroup=["Wallpaper",previous.wallpaper,"General"];
    Object.keys(previous.config).forEach(function(k){d.writeConfig(k,previous.config[k]);});
    d.reloadConfig();
});
""" % json.dumps(records))
    print("Restored the previous desktop layout and wallpaper.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["activate", "install", "restore", "status"])
    args = parser.parse_args()
    if args.command == "activate":
        activate()
    elif args.command == "install":
        save_backup()
        install_files()
    elif args.command == "restore":
        restore()
    else:
        print(json.dumps(snapshot(), indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
