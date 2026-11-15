#!/usr/bin/env python3
"""Render source vector poses once for the native Plasma wallpaper player.

Uses the existing Qt renderer, preserving the ACT component arrangements and
transparency. This is a deterministic vector export, not generated artwork.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from rover import RoverAnimation


def export(destination: Path | None = None) -> dict:
    application = QApplication.instance() or QApplication([])
    destination = destination or ROOT / "assets/rover-poses"
    destination.mkdir(parents=True, exist_ok=True)
    actor = RoverAnimation(width=384, seed=0)
    identifiers = sorted(map(int, actor.data["poses"])) + [65535]
    for pose_id in identifiers:
        path = destination / f"pose_{pose_id}.png"
        if not actor.render_pose(pose_id).save(str(path), "PNG"):
            raise RuntimeError(f"Unable to export Rover pose {pose_id}")
    manifest = {
        "width": actor.width,
        "height": actor.height,
        "rest_pose": 201,
        "empty_pose": 65535,
        "filename": "pose_<id>.png",
        "pose_ids": identifiers,
        "source": "Source ROVER.ACT poses; deterministic Qt vector export",
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    result = export()
    print(f"Exported {len(result['pose_ids'])} transparent poses at {result['width']}x{result['height']}")
