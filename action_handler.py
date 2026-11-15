#!/usr/bin/env python3
"""Strict local action bridge for the native KDE Plasma Bob wallpaper.

The wallpaper sends an action, room ID, and optional exact object ID. Applications, folders,
and URLs are resolved from local settings; the protocol cannot supply a command,
file path, or destination URL. The helper opens no room-sized window.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import datetime as dt
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import parse_qs, unquote, urlsplit

from launcher import Launcher, LaunchError

ROOT = Path(__file__).resolve().parent
ROOMS_PATH = ROOT / "assets/rooms/rooms.json"
GLOBAL_ACTIONS = frozenset({"settings", "help", "rover", "programs"})
GLOBAL_OPEN_TOOLS = frozenset({"notes", "calendar", "clock"})
BUILTIN_ACTIONS = frozenset({"notes", "paper", "calendar", "clock", "calculator"})
KNOWN_ACTIONS = GLOBAL_ACTIONS | BUILTIN_ACTIONS | frozenset({
    "bookshelf", "album", "window", "letter", "desk", "cabinet",
})
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ActionRequest:
    operation: str
    room: str
    action: str
    object_id: str | None = None

    @property
    def binding_key(self) -> str:
        if self.object_id is not None:
            return f"{self.room}:object:{self.object_id}"
        return f"{self.room}:{self.action}"


def load_rooms(path: Path = ROOMS_PATH) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("rooms"), list):
            raise ValueError("unsupported room metadata")
        rooms = {}
        for room in data["rooms"]:
            if (not isinstance(room, dict) or not isinstance(room.get("id"), str)
                    or not IDENTIFIER.fullmatch(room["id"])):
                raise ValueError("invalid room ID")
            if not isinstance(room.get("hotspots"), list) or not all(isinstance(h, dict) for h in room["hotspots"]):
                raise ValueError("invalid room objects")
            if room["id"] in rooms:
                raise ValueError("duplicate room ID")
            rooms[room["id"]] = room
        if not rooms:
            raise ValueError("no rooms were found")
        return rooms
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        raise ProtocolError(f"The Bob room data could not be read: {error}") from error


def parse_request(uri: str, rooms: dict | None = None) -> ActionRequest:
    """Accept bobhouse://open|configure/action?room=known-room[&object=id]."""
    if not isinstance(uri, str) or not uri or len(uri) > 2048 or any(ord(c) <= 32 for c in uri):
        raise ProtocolError("Invalid Bob desktop link.")
    try:
        parsed = urlsplit(uri)
        if parsed.scheme != "bobhouse" or parsed.netloc not in {"open", "configure"} or parsed.fragment:
            raise ValueError("unexpected protocol or operation")
        action = unquote(parsed.path, encoding="utf-8", errors="strict")
        if not action.startswith("/") or not IDENTIFIER.fullmatch(action[1:]):
            raise ValueError("invalid action")
        action = action[1:]
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True,
                         encoding="utf-8", errors="strict")
        if (set(query) not in ({"room"}, {"room", "object"}) or len(query["room"]) != 1
                or not IDENTIFIER.fullmatch(query["room"][0])):
            raise ValueError("supply exactly one room ID")
        room_id = query["room"][0]
        object_id = None
        if "object" in query:
            if len(query["object"]) != 1 or not IDENTIFIER.fullmatch(query["object"][0]):
                raise ValueError("supply exactly one valid object ID")
            object_id = query["object"][0]
    except (ValueError, UnicodeError) as error:
        raise ProtocolError(f"Invalid Bob desktop link: {error}") from error
    available = load_rooms() if rooms is None else rooms
    if room_id not in available:
        raise ProtocolError("That room is not installed.")
    if action not in KNOWN_ACTIONS:
        raise ProtocolError("That object action is not supported.")
    hotspots = available[room_id]["hotspots"]
    normalized = "notes" if action == "paper" else action
    if object_id is not None:
        matches = [hotspot for hotspot in hotspots if hotspot.get("id") == object_id]
        if len(matches) != 1 or matches[0].get("action") not in {action, normalized}:
            raise ProtocolError("That exact object and action were not found in this room.")
    elif parsed.netloc == "open" and (action in GLOBAL_ACTIONS or normalized in GLOBAL_OPEN_TOOLS):
        return ActionRequest(parsed.netloc, room_id, normalized)
    else:
        matches = [hotspot for hotspot in hotspots if hotspot.get("action") in {action, normalized}]
        if len(matches) > 1:
            raise ProtocolError("Several objects use that tool. Choose the exact object in the room.")
        if not matches:
            raise ProtocolError("That object is not in this room.")
        object_id = matches[0].get("id")
        if not isinstance(object_id, str) or not IDENTIFIER.fullmatch(object_id):
            raise ProtocolError("That room object has no valid identity.")
        if sum(hotspot.get("id") == object_id for hotspot in hotspots) != 1:
            raise ProtocolError("That room contains a duplicate object identity.")
    if action in GLOBAL_ACTIONS:
        raise ProtocolError("Companion commands cannot be assigned to a room object.")
    return ActionRequest(parsed.netloc, room_id, normalized, object_id)


def migrate_legacy_bindings(launcher: Launcher, rooms: dict | None = None) -> dict[str, int]:
    """Split old room/action choices into independent object choices atomically.

    This transformation runs on the latest saved data under Store's lock. An
    existing individual choice always wins, including one saved by another helper
    after this Launcher was constructed. Unknown legacy keys are retained.
    """
    available = load_rooms() if rooms is None else rooms
    targets: dict[str, list[str]] = {}
    for room_id, room in available.items():
        identifiers = [hotspot.get("id") for hotspot in room["hotspots"]]
        for hotspot in room["hotspots"]:
            object_id, action = hotspot.get("id"), hotspot.get("action")
            if (action not in KNOWN_ACTIONS or action in GLOBAL_ACTIONS
                    or not isinstance(object_id, str) or not IDENTIFIER.fullmatch(object_id)
                    or identifiers.count(object_id) != 1):
                continue
            targets.setdefault(f"{room_id}:{action}", []).append(f"{room_id}:object:{object_id}")
    result = {"copied": 0, "removed": 0}
    if not any(key in launcher.bindings for key in targets):
        return result

    def migrate(data):
        bindings = data["bindings"]
        recorded = data["settings"].get("object_binding_migrations", [])
        migrated = set(recorded) if isinstance(recorded, list) and all(isinstance(k, str) for k in recorded) else set()
        for legacy_key, object_keys in targets.items():
            if legacy_key not in bindings:
                continue
            old_choice = bindings[legacy_key]
            if legacy_key not in migrated:
                for object_key in object_keys:
                    if object_key not in bindings:
                        bindings[object_key] = deepcopy(old_choice)
                        result["copied"] += 1
            del bindings[legacy_key]
            migrated.add(legacy_key)
            result["removed"] += 1
        # An already-open old helper can save its shared key after migration.
        # Remember migrated keys so this cannot resurrect a later object reset.
        if migrated:
            data["settings"]["object_binding_migrations"] = sorted(migrated)

    launcher.store.save(transform=migrate)
    return result


def object_label(request: ActionRequest, rooms: dict | None = None) -> str | None:
    if request.object_id is None:
        return None
    available = load_rooms() if rooms is None else rooms
    for hotspot in available.get(request.room, {}).get("hotspots", []):
        if hotspot.get("id") == request.object_id:
            return hotspot.get("label") or request.action.replace("_", " ")
    return None


def require_object(request: ActionRequest) -> None:
    if request.object_id is None:
        raise ProtocolError("Choose the exact object in the room before changing its destination.")


def binding_for(request: ActionRequest, launcher: Launcher) -> str | None:
    """Resolve one exact object, then global defaults; never a shared legacy key."""
    if request.object_id is not None and request.binding_key in launcher.bindings:
        return request.binding_key
    if request.action in launcher.bindings:
        return request.action
    return None


def reset_room_binding(request: ActionRequest, launcher: Launcher) -> None:
    require_object(request)
    # Reset is an explicit deletion of the latest object assignment, including
    # one another helper saved after this dialog was opened.
    launcher.store.save(transform=lambda current: current["bindings"].pop(request.binding_key, None))


def _calculator_binding(launcher: Launcher) -> dict[str, str]:
    for desktop_id in ("org.kde.kcalc.desktop", "org.gnome.Calculator.desktop", "galculator.desktop"):
        match = next((app for app in launcher.apps if app.id == desktop_id), None)
        if match:
            return {"kind": "app", "target": match.id, "label": match.name}
    raise LaunchError("No calculator is installed. Shift-click the calculator object to choose an application.")


def launch_external(request: ActionRequest, launcher: Launcher) -> str | None:
    """Dispatch a configured launch, or return None for a native dialog action."""
    if request.action in {"programs"}:
        return None
    binding = binding_for(request, launcher)
    if binding is not None:
        return launcher.launch_binding(binding)
    if request.action == "calculator":
        # This derived default is not persisted; a user override is saved only
        # through the configuration dialog.
        launcher.bindings[request.binding_key] = _calculator_binding(launcher)
        return launcher.launch_binding(request.binding_key)
    if request.action in BUILTIN_ACTIONS | GLOBAL_ACTIONS:
        return None
    raise LaunchError("This object has no destination. Shift-click it to choose an application or folder.")


def _application():
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication
    from dialogs import RETRO_STYLE

    app = QApplication.instance() or QApplication(["Bob House KDE"])
    app.setApplicationName("Bob House KDE")
    app.setDesktopFileName("bob-house-kde-action")
    app.setWindowIcon(QIcon.fromTheme("user-home"))
    app.setStyle("Fusion")
    app.setStyleSheet(RETRO_STYLE)
    return app


def clock_dialog(launcher: Launcher):
    """An on-demand countdown helper that survives closing its visible clock."""
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSpinBox
    from dialogs import BobDialog

    class ClockDialog(BobDialog):
        def __init__(self):
            super().__init__("Grandfather Clock", width=430)
            self.deadline = None
            self.time_label = QLabel()
            self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.body.addWidget(self.time_label)
            self.status = self.add_description("Choose a duration to begin.")
            row = QHBoxLayout()
            row.addWidget(QLabel("Minutes:"))
            self.minutes = QSpinBox()
            self.minutes.setRange(1, 240)
            self.minutes.setValue(25)
            row.addWidget(self.minutes)
            start = QPushButton("Start timer")
            start.clicked.connect(self.start_timer)
            row.addWidget(start)
            self.body.addLayout(row)
            self.add_description("You can close this clock while its timer runs. I'll remind you when it's finished.")
            controls = QHBoxLayout()
            cancel = QPushButton("Cancel timer")
            cancel.clicked.connect(self.cancel_timer)
            controls.addWidget(cancel)
            close = QPushButton("Close")
            close.clicked.connect(self.close)
            controls.addWidget(close)
            self.body.addLayout(controls)
            self.tick = QTimer(self)
            self.tick.timeout.connect(self.refresh)
            self.tick.start(250)
            self.refresh()

        def start_timer(self):
            self.deadline = time.monotonic() + self.minutes.value() * 60
            QApplication.instance().setQuitOnLastWindowClosed(False)
            self.refresh()

        def cancel_timer(self):
            self.deadline = None
            QApplication.instance().setQuitOnLastWindowClosed(True)
            self.status.setText("Timer cancelled. Choose a duration to begin again.")

        def refresh(self):
            self.time_label.setText(dt.datetime.now().strftime("%A, %B %d\n%I:%M:%S %p"))
            if self.deadline is None:
                return
            remaining = max(0, math.ceil(self.deadline - time.monotonic()))
            self.status.setText(f"Time left: {remaining // 60:02d}:{remaining % 60:02d}")
            if remaining == 0:
                self.deadline = None
                self.status.setText("Time's up!")
                if launcher.store.data["settings"].get("sound"):
                    QApplication.beep()
                self.showNormal()
                self.raise_()
                QApplication.instance().setQuitOnLastWindowClosed(True)
                QMessageBox.information(self, "Time's up!", "Your timer has finished. Time for a little break!")

    return ClockDialog()


def show_clock(launcher: Launcher, app) -> int:
    """Reuse an already-running clock helper; no permanent background service."""
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    name = f"bob-house-kde-clock-{os.getuid()}"
    existing = QLocalSocket()
    existing.connectToServer(name)
    if existing.waitForConnected(250):
        existing.write(b"show\n")
        existing.flush()
        existing.waitForBytesWritten(250)
        existing.disconnectFromServer()
        return 0
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(name):
        QLocalServer.removeServer(name)
        if not server.listen(name):
            raise LaunchError("The clock is already starting. Click it again in a moment.")
    dialog = clock_dialog(launcher)

    def reveal():
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            connection.disconnectFromServer()
            connection.deleteLater()
        dialog.showNormal()
        dialog.raise_()
        dialog.activateWindow()

    server.newConnection.connect(reveal)
    dialog.show()
    try:
        return app.exec()
    finally:
        server.close()


def show_dialog(request: ActionRequest, launcher: Launcher) -> int:
    from PySide6.QtWidgets import QDialogButtonBox, QLabel, QPushButton
    from dialogs import BindingDialog, BobDialog, CalendarDialog, NotesDialog, SettingsDialog

    app = _application()
    if request.operation == "configure":
        require_object(request)
        inherited = binding_for(request, launcher)
        initial_binding = deepcopy(launcher.bindings[inherited]) if inherited is not None else None
        if inherited is None and request.action == "calculator":
            try:
                initial_binding = _calculator_binding(launcher)
            except LaunchError:
                pass
        dialog = BindingDialog(launcher, request.binding_key, initial_binding=initial_binding,
                               object_label=object_label(request))
        reset = QPushButton("Use this object's default choice")

        def restore():
            try:
                reset_room_binding(request, launcher)
            except LaunchError as error:
                dialog.show_error(error)
                return
            dialog.accept()

        reset.clicked.connect(restore)
        dialog.body.insertWidget(dialog.body.count() - 1, reset)
    elif request.action == "programs":
        from companion_dialogs import ProgramsDialog
        dialog = ProgramsDialog(launcher)
    elif request.action == "notes":
        dialog = NotesDialog(launcher)
    elif request.action == "calendar":
        dialog = CalendarDialog(launcher)
    elif request.action == "clock":
        return show_clock(launcher, app)
    elif request.action == "settings":
        dialog = SettingsDialog(launcher)
        dialog.setWindowTitle("Timer options")
        dialog.findChild(QLabel, "bobDialogHeading").setText("Timer options")
        dialog.checks["animations"].hide()
        dialog.checks["minimize_after_launch"].hide()
        dialog.checks["sound"].setText("Play timer notification sounds")
        for label in dialog.findChildren(QLabel):
            if "right-click" in label.text():
                label.setText("Use the wallpaper's Options menu to change room animation and object labels.")
    elif request.action in {"help", "rover"}:
        dialog = BobDialog("Welcome to Bob's Home", width=520)
        dialog.add_description("Click a door to visit another room. Click an object to open its application or folder.")
        dialog.add_description("Click Rover, or press F2 while the room has focus, to open his command menu. He can find apps and folders, open your tools, change rooms, or do a trick.")
        dialog.add_description("Shift-click an object to choose what it opens. Every object remembers its own choice.")
        dialog.add_description("The paper keeps your notes, the calendar keeps date reminders, and the clock can time a break.")
        dialog.add_description("This room is your desktop wallpaper. Use the normal desktop menu or taskbar to switch applications.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        dialog.body.addWidget(buttons)
    else:
        raise LaunchError("This object has no native tool. Shift-click it to choose an application.")
    dialog.exec()
    return 0


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    try:
        if len(args) != 1:
            raise ProtocolError("Expected one Bob desktop action link.")
        rooms = load_rooms()
        request = parse_request(args[0], rooms)
        launcher = Launcher()
        migrate_legacy_bindings(launcher, rooms)
        if request.operation == "configure":
            return show_dialog(request, launcher)
        if launch_external(request, launcher) is None:
            return show_dialog(request, launcher)
        return 0
    except (ProtocolError, LaunchError, OSError, ValueError) as error:
        message = str(error).replace("Right-click", "Shift-click").replace("right-click", "shift-click")
        print(f"Bob House KDE: {message}", file=sys.stderr)
        from PySide6.QtWidgets import QMessageBox
        app = _application()
        QMessageBox.warning(None, "Bob couldn't open that", message)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
