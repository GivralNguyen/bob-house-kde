"""Local application discovery, launch bindings and durable Bob preferences.

The UI should run ``Launcher.launch_binding`` in a worker: desktop openers can
take a few seconds to hand a request to another process. Commands are always
argument lists; user-supplied paths and desktop Exec lines never reach a shell.
"""
from __future__ import annotations

import configparser
import copy
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Callable
from urllib.parse import urlsplit


class LaunchError(RuntimeError):
    """A useful error to show in Rover's speech bubble or a dialog."""


@dataclass(frozen=True)
class DesktopApp:
    id: str
    name: str
    path: Path
    icon: str = ""
    terminal: bool = False


def _xdg_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name, "")
    return Path(value) if value and Path(value).is_absolute() else fallback


def config_directory() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config") / "bob-house-kde"


def application_directories() -> list[Path]:
    """XDG user files take precedence over system files of the same desktop ID."""
    user = _xdg_path("XDG_DATA_HOME", Path.home() / ".local/share")
    system = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    roots = [user] + [Path(item) for item in system.split(":") if item and Path(item).is_absolute()]
    return list(dict.fromkeys(root / "applications" for root in roots))


def discover_applications(directories: list[Path] | None = None) -> list[DesktopApp]:
    """Read launchable desktop entries without executing their Exec fields."""
    apps: list[DesktopApp] = []
    seen: set[str] = set()
    desktops = set(filter(None, os.environ.get("XDG_CURRENT_DESKTOP", "").split(":")))
    for directory in application_directories() if directories is None else directories:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.desktop")):
            desktop_id = str(path.relative_to(directory)).replace(os.sep, "-")
            if desktop_id in seen:
                continue
            # Even a Hidden user entry masks the corresponding system entry.
            seen.add(desktop_id)
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read_string(path.read_text(encoding="utf-8"))
                entry = parser["Desktop Entry"]
                if entry.get("Type") != "Application":
                    continue
                if any(entry.get(key, "").lower() == "true" for key in ("Hidden", "NoDisplay")):
                    continue
                only = set(filter(None, entry.get("OnlyShowIn", "").split(";")))
                never = set(filter(None, entry.get("NotShowIn", "").split(";")))
                if (only and not only.intersection(desktops)) or never.intersection(desktops):
                    continue
                try_exec = entry.get("TryExec", "")
                if try_exec and not shutil.which(try_exec):
                    continue
                if not entry.get("Exec") and entry.get("DBusActivatable", "").lower() != "true":
                    continue
                name = entry.get("Name", "").strip()
                if name:
                    apps.append(DesktopApp(desktop_id, name, path.resolve(), entry.get("Icon", ""),
                                           entry.get("Terminal", "").lower() == "true"))
            except (OSError, UnicodeError, configparser.Error, KeyError):
                continue
    return sorted(apps, key=lambda app: (app.name.casefold(), app.id))


def user_folder(name: str) -> Path:
    """Resolve an XDG user directory without sourcing shell configuration."""
    home = Path.home()
    if name.lower() in ("home", "cabinet"):
        return home
    key = "XDG_" + name.upper() + "_DIR"
    config = _xdg_path("XDG_CONFIG_HOME", home / ".config") / "user-dirs.dirs"
    try:
        for line in config.read_text(encoding="utf-8").splitlines():
            variable, separator, value = line.strip().partition("=")
            if separator and variable == key:
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] == '"':
                    value = value[1:-1].replace('\\"', '"').replace('\\\\', '\\')
                if value == "$HOME":
                    candidate = home
                elif value.startswith("$HOME/"):
                    candidate = home / value[6:]
                else:
                    candidate = Path(value)
                if candidate.is_absolute() and candidate.is_dir():
                    return candidate
                break
    except (OSError, UnicodeError):
        pass
    conventional = home / name
    return conventional if conventional.is_dir() else home


def default_bindings(apps: list[DesktopApp] | None = None) -> dict[str, dict[str, str]]:
    available = {app.id: app for app in (apps or [])}

    def app_or(ids: tuple[str, ...], fallback: dict[str, str]) -> dict[str, str]:
        for desktop_id in ids:
            if desktop_id in available:
                app = available[desktop_id]
                return {"kind": "app", "target": app.id, "label": app.name}
        return fallback

    return {
        "bookshelf": {"kind": "folder", "target": str(user_folder("Documents")), "label": "Documents"},
        "album": {"kind": "folder", "target": str(user_folder("Pictures")), "label": "Pictures"},
        "window": app_or(("firefox.desktop", "org.mozilla.firefox.desktop", "firefox-esr.desktop"),
                         {"kind": "url", "target": "https://www.google.com/", "label": "Web browser"}),
        "letter": {"kind": "url", "target": "mailto:", "label": "Email"},
        "desk": {"kind": "folder", "target": str(user_folder("Documents")), "label": "Documents"},
        "cabinet": {"kind": "folder", "target": str(Path.home()), "label": "Home folder"},
    }


def _valid_binding(binding: Any) -> bool:
    return (isinstance(binding, dict)
            and binding.get("kind") in {"app", "folder", "url"}
            and isinstance(binding.get("target"), str)
            and bool(binding["target"])
            and isinstance(binding.get("label", ""), str))


def _merge_changes(before: Any, edited: Any, current: Any) -> Any:
    """Apply this editor's changes without discarding another helper's changes."""
    if before == edited:
        return copy.deepcopy(current)
    if not all(isinstance(value, dict) for value in (before, edited, current)):
        return copy.deepcopy(edited)
    if {"kind", "target"}.issubset(edited):
        # A launch binding is one indivisible choice, not three independent fields.
        return copy.deepcopy(edited)
    result = copy.deepcopy(current)
    for key in before.keys() - edited.keys():
        result.pop(key, None)
    for key, value in edited.items():
        if key not in before:
            result[key] = copy.deepcopy(value)
        elif key not in current and value == before[key]:
            continue
        else:
            result[key] = _merge_changes(before[key], value, current.get(key, before[key]))
    return result


class Store:
    """One atomic JSON file; malformed input is preserved before replacement.

    ``warning`` is nonempty when preferences could not be read completely.
    A caller may edit ``data`` and call ``save()``, or use Launcher helpers.
    """
    def __init__(self, directory: Path | None = None, apps: list[DesktopApp] | None = None):
        self._apps = apps
        self.directory = Path(directory) if directory is not None else config_directory()
        self.path = self.directory / "settings.json"
        self.warning = ""
        self._invalid_original = False
        self.data: dict[str, Any] = {
            "version": 1,
            "bindings": default_bindings(apps),
            "settings": {"animations": True, "sound": False, "minimize_after_launch": True},
            "notes": "",
            "calendar_notes": {},
        }
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings must be a JSON object")
            if raw.get("version", 1) != 1:
                raise ValueError("unsupported preferences version")
            bindings = raw.get("bindings", {})
            settings = raw.get("settings", {})
            notes = raw.get("notes", "")
            calendar_notes = raw.get("calendar_notes", {})
            if not isinstance(bindings, dict) or not isinstance(settings, dict) or not isinstance(notes, str):
                raise ValueError("invalid preferences fields")
            if not isinstance(calendar_notes, dict) or not all(
                    isinstance(day, str) and isinstance(note, str)
                    for day, note in calendar_notes.items()):
                raise ValueError("calendar notes must map date strings to note strings")
            for key, binding in bindings.items():
                if not isinstance(key, str) or not _valid_binding(binding):
                    raise ValueError("invalid object binding")
            for key in self.data["settings"]:
                if key in settings and not isinstance(settings[key], bool):
                    raise ValueError(f"{key} must be true or false")
            self.data["bindings"].update(bindings)
            self.data["settings"].update(settings)
            self.data["notes"] = notes
            self.data["calendar_notes"] = calendar_notes
        except FileNotFoundError:
            pass
        except (OSError, UnicodeError, ValueError) as error:
            self.warning = f"I couldn't read the saved preferences: {error}. Default settings are in use."
            self._invalid_original = True
        self._snapshot = copy.deepcopy(self.data)

    def save(self, transform: Callable[[dict[str, Any]], None] | None = None) -> None:
        """Merge and save under a file lock; optionally transform the latest data.

        ``transform`` mutates the merged dictionary in place while the lock is
        held. Neither this Store nor its on-disk file changes unless save succeeds.
        """
        temporary: str | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / ".settings.lock").open("a") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                latest = Store(self.directory, self._apps)
                merged = _merge_changes(self._snapshot, self.data, latest.data)
                if transform is not None:
                    transform(merged)
                payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
                with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                                 prefix=".settings-", suffix=".tmp", delete=False) as stream:
                    temporary = stream.name
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                if latest._invalid_original and self.path.exists():
                    backup = self.path.with_suffix(".json.invalid")
                    count = 1
                    while backup.exists():
                        backup = self.path.with_suffix(f".json.invalid-{count}")
                        count += 1
                    shutil.copy2(self.path, backup)
                os.replace(temporary, self.path)
                temporary = None
                self.data = merged
                self._snapshot = copy.deepcopy(merged)
                self._invalid_original = False
        except (OSError, TypeError, ValueError) as error:
            raise LaunchError(f"I couldn't save your preferences: {error}") from error
        finally:
            if temporary is not None:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass


def _run_opener(arguments: list[str]) -> None:
    try:
        result = subprocess.run(arguments, shell=False, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                text=True, errors="replace", timeout=15, check=False)
    except FileNotFoundError as error:
        raise LaunchError(f"The desktop helper '{arguments[0]}' is not installed.") from error
    except subprocess.TimeoutExpired as error:
        raise LaunchError("The desktop took too long to confirm opening that item. Check whether it opened, then try again.") from error
    except OSError as error:
        raise LaunchError(f"I couldn't open that item: {error}") from error
    if result.returncode:
        detail = (result.stderr or "").strip().splitlines()
        message = detail[-1][:300] if detail else f"desktop helper exited with status {result.returncode}"
        raise LaunchError(f"I couldn't open that item: {message}")


class Launcher:
    def __init__(self, store: Store | None = None, apps: list[DesktopApp] | None = None):
        self.apps = discover_applications() if apps is None else apps
        self.store = Store(apps=self.apps) if store is None else store

    @property
    def bindings(self) -> dict[str, dict[str, str]]:
        return self.store.data["bindings"]

    def set_binding(self, object_id: str, kind: str, target: str, label: str = "") -> None:
        binding = {"kind": kind, "target": target, "label": label or target}
        self._validate_binding(binding)
        previous = copy.deepcopy(self.bindings)
        self.bindings[object_id] = binding
        try:
            self.store.save()
        except LaunchError:
            self.store.data["bindings"] = previous
            raise

    def save_notes(self, text: str) -> None:
        previous = self.store.data["notes"]
        self.store.data["notes"] = text
        try:
            self.store.save()
        except LaunchError:
            self.store.data["notes"] = previous
            raise

    def _validate_binding(self, binding: dict[str, str]) -> None:
        if not _valid_binding(binding):
            raise LaunchError("Choose an application, folder, or web address first.")
        target, kind = binding["target"], binding["kind"]
        if "\x00" in target:
            raise LaunchError("That destination contains an invalid character.")
        if kind == "app":
            match = next((app for app in self.apps if app.id == target), None)
            if match is None or not match.path.is_file():
                raise LaunchError("That application is no longer available. Right-click the object to choose another one.")
        elif kind == "folder":
            if not Path(target).expanduser().is_dir():
                raise LaunchError("That folder no longer exists. Right-click the object to choose another one.")
        else:
            try:
                address = urlsplit(target)
                valid = address.scheme in {"http", "https", "mailto"}
                valid = valid and (address.scheme == "mailto" or bool(address.hostname))
            except ValueError:
                valid = False
            if not valid:
                raise LaunchError("Use a complete http://, https://, or mailto: address.")

    def launch_binding(self, object_id: str) -> str:
        """Launch one configured item and return its label after opener success."""
        binding = self.bindings.get(object_id)
        if binding is None:
            raise LaunchError("This object has no destination yet. Right-click it to choose one.")
        self._validate_binding(binding)
        kind, target = binding["kind"], binding["target"]
        if kind == "app":
            app = next(app for app in self.apps if app.id == target)
            kde_client = (shutil.which("kioclient") or shutil.which("kioclient6")) if app.terminal else None
            if kde_client:
                # KDE reads Terminal=true and chooses the user's terminal. Pass
                # the desktop entry itself; never parse its Exec line in a shell.
                command = [kde_client, "exec", app.path.as_uri()]
            elif shutil.which("gio"):
                command = ["gio", "launch", str(app.path)]
            elif shutil.which("gtk-launch"):
                command = ["gtk-launch", app.id]
            else:
                raise LaunchError("Install gio or gtk-launch to open applications from this room.")
        elif kind == "folder":
            command = ["xdg-open", str(Path(target).expanduser().resolve())]
        else:
            command = ["xdg-open", target]
        _run_opener(command)
        return binding.get("label") or target
