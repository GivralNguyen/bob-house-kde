#!/usr/bin/env python3
"""Check source placements and load all rooms without launching applications."""
import json
import os
from pathlib import Path
import sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from action_handler import parse_request
source = json.loads((ROOT / "assets/rooms/source/data.json").read_text())
rooms = json.loads((ROOT / "assets/rooms/rooms.json").read_text())["rooms"]
app = QGuiApplication([])
view = QQuickView()
view.setSource(QUrl.fromLocalFile(str(ROOT / "plasma/org.bobhouse.desktop/contents/ui/RoomScene.qml")))
assert view.status() == QQuickView.Ready, [e.toString() for e in view.errors()]
scene = view.rootObject()
scene.setProperty("assetRoot", (ROOT / "assets").as_uri() + "/")
scene.setProperty("launchEnabled", False)
view.resize(1200, 900)
view.show()
for room in rooms:
    for hotspot in room['hotspots']:
        if 'action' in hotspot:
            for operation in ('open', 'configure'):
                parse_request(f"bobhouse://{operation}/{hotspot['action']}?room={room['id']}&object={hotspot['id']}")
    original = source["rooms"][room["sourceId"]]["objects"]
    assert [obj["source"] for obj in room["objects"]] == original, room["id"]
    scene.setProperty("roomId", room["id"])
    app.processEvents()
    assert scene.property("roomId") == room["id"]
assert len(rooms) == 10
print("PASS: source object records and drawing order in all 10 rooms; QML loads without launching apps.")
view.close()
