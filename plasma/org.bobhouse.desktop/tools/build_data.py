#!/usr/bin/env python3
"""Bundle local JSON as a QML JS module; Plasma needs no file-XHR permission."""
import argparse
import json
from pathlib import Path


def rover_hit_masks(assets):
    """Compact alpha runs let clicks pass through each pose's transparent margin."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    masks = {}
    for path in sorted((assets / "rover-poses").glob("pose_*.png")):
        image = QImage(str(path)).scaled(96, 72, Qt.AspectRatioMode.IgnoreAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        if image.isNull():
            raise ValueError(f"Unreadable Rover pose: {path}")
        alpha = bytes(image.constBits())[3::4]
        rows = []
        for y in range(72):
            spans, start = [], None
            for x in range(97):
                opaque = x < 96 and alpha[y * 96 + x] > 16
                if opaque and start is None:
                    start = x
                elif not opaque and start is not None:
                    spans.extend((start, x))
                    start = None
            rows.append(spans)
        masks[path.stem.split('_')[1]] = rows
    return masks

PACKAGE = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = PACKAGE.parents[1] / "assets"


def build(assets=DEFAULT_ASSETS):
    assets = Path(assets)
    rooms = json.loads((assets / "rooms/rooms.json").read_text())
    timeline = json.loads((assets / "rover-timeline.json").read_text())
    entries = rooms.get("rooms", [])
    if not entries:
        raise ValueError("At least one room is required")
    ids = {str(room["id"]) for room in entries}
    if len(ids) != len(entries):
        raise ValueError("Room IDs must be unique")
    for room in entries:
        if room["width"] <= 0 or room["height"] <= 0:
            raise ValueError("Room dimensions must be positive")
        picture = (assets / room["image"]).resolve()
        if not picture.is_relative_to(assets.resolve()) or not picture.is_file():
            raise ValueError(f"Missing or invalid room picture: {room['image']}")
        for hotspot in room.get("hotspots", []):
            if len(hotspot["rect"]) != 4:
                raise ValueError(f"Invalid hotspot: {hotspot['id']}")
            if "room" in hotspot and str(hotspot["room"]) not in ids:
                raise ValueError(f"Missing door destination: {hotspot['room']}")
    if "animations" not in timeline or not (assets / "rover-poses/pose_201.png").is_file():
        raise ValueError("Rover timeline and exported poses are required")
    target = PACKAGE / "contents/ui/Data.js"
    target.write_text(".pragma library\n// Generated from source local room and animation metadata.\n"
                      + "var rooms = " + json.dumps(rooms, ensure_ascii=False, separators=(",", ":")) + ";\n"
                      + "var timeline = " + json.dumps(timeline, separators=(",", ":")) + ";\n"
                      + "var roverHitMasks = " + json.dumps(rover_hit_masks(assets), separators=(",", ":")) + ";\n")
    print(f"Bundled {len(entries)} rooms and {len(timeline['animations'])} Rover animation groups into {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    build(parser.parse_args().assets)
