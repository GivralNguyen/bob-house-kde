"""Rover animation interpreter for the Microsoft Bob-inspired KDE desktop.

The artwork, poses and timings come from ROVER.ACT. QSvgRenderer draws the
source component vectors; no Windows executable is loaded or run.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
import random
import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parent / "assets"

# Descriptive launcher aliases, chosen by inspecting the source animations.
# The ACT itself stores numeric groups, not these labels.
ACTION_GROUPS = {
    "greeting": "1",
    "idle": "2",
    "look_left": "3",
    "gesture": "4",
    "acknowledge": "5",
    "walk": "6",
    "clicked": "32",
    "thinking": "7",
    "nod": "8",
    "roll": "9",
    "laugh": "10",
    "working": "11",
    "ready": "12",
    "look_back": "13",
    "mail": "14",
    "look_right": "15",
    "success": "16",
    "smile": "17",
    "error": "18",
    "surprised": "19",
    "play": "20",
    "writing": "21",
    "cancel": "22",
    "computer": "23",
    "pant": "24",
    "ask": "25",
    "stretch": "26",
    "fetch": "31",
}


class RoverAnimation:
    """Play ACT command sequences; render each required pose once on demand."""

    def __init__(self, assets: Path = ASSETS, width: int = 384, seed=None):
        self.assets = Path(assets)
        self.data = json.loads((self.assets / "rover-timeline.json").read_text())
        self.width = width
        self.height = round(width * self.data["height"] / self.data["width"])
        self.rng = random.Random(seed)
        self.clips = {name: self.data["animations"][group]
                      for name, group in ACTION_GROUPS.items()
                      if group in self.data["animations"]}
        self._vectors = {}
        self._poses = OrderedDict()
        self.pose = 201
        self.name = "greeting"
        self._commands = []
        self._position = 0
        self._deadline = 0.0
        self._running = False
        self.start = 0.0
        self.next_idle = 0.0
        self.play("greeting")

    def play(self, name, now=None):
        """Start a named action, retaining the actor's source variant choice."""
        if name not in self.clips:
            name = "clicked"
        self.name = name
        self.start = time.monotonic() if now is None else now
        self.next_idle = self.start + self.rng.uniform(14, 24)
        self._commands = self.rng.choice(self.clips[name])
        self._position = 0
        self._deadline = self.start
        self._running = True
        self.pose = 201

    def frame(self, now, animate=True):
        if not animate:
            # Keep disabled animation from accumulating a backlog to replay.
            self._running = False
            self.next_idle = now + 14
            self.pose = 201
            return self.rest_frame()
        if not self._running and now >= self.next_idle:
            self.play("idle", now=now)
        steps = 0
        while self._running and now >= self._deadline:
            steps += 1
            if self._position >= len(self._commands) or steps > 1000 or now-self.start > 90:
                self._running = False
                self.pose = 201
                self.next_idle = now + self.rng.uniform(10, 18)
                break
            command, arg, value = self._commands[self._position]
            self._position += 1
            if command == 0:
                self.pose = arg
                self._deadline += value / 1000
            elif command == 1:
                if self.rng.randrange(32768) < value:
                    self._position = arg
            # Command 2 contains an source sound cue; the room stays quiet.
        return self.render_pose(self.pose)

    def rest_frame(self):
        return self.render_pose(201)

    def render_pose(self, pose_id):
        """Render a complete pose into a fixed, transparent actor canvas."""
        if pose_id in self._poses:
            self._poses.move_to_end(pose_id)
            return self._poses[pose_id]
        pixmap = QPixmap(self.width, self.height)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        sx = self.width / self.data["width"]
        sy = self.height / self.data["height"]
        for index, left, top, right, bottom in self.data["poses"].get(str(pose_id), []):
            if index not in self._vectors:
                renderer = QSvgRenderer(str(self.assets / "rover-parts" / f"part_{index:03d}.svg"))
                renderer.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
                if not renderer.isValid():
                    painter.end()
                    raise ValueError(f"Invalid Rover vector {index}")
                self._vectors[index] = renderer
            width, height = (right-left)*sx, (bottom-top)*sy
            if not width or not height:
                continue
            painter.save()
            painter.translate(left*sx, top*sy)
            painter.scale(1 if width > 0 else -1, 1 if height > 0 else -1)
            self._vectors[index].render(painter, QRectF(0, 0, abs(width), abs(height)))
            painter.restore()
        painter.end()
        self._poses[pose_id] = pixmap
        if len(self._poses) > 128:
            self._poses.popitem(last=False)
        return pixmap
