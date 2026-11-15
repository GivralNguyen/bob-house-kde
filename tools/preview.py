#!/usr/bin/env python3
"""Render release previews without launching applications or touching Plasma."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from pathlib import Path
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest

ROOT = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.setSource(QUrl.fromLocalFile(str(ROOT / 'plasma/org.bobhouse.desktop/contents/ui/RoomScene.qml')))
if view.status() != QQuickView.Ready:
    raise RuntimeError([e.toString() for e in view.errors()])
scene = view.rootObject()
scene.setProperty('assetRoot', (ROOT / 'assets').as_uri() + '/')
scene.setProperty('launchEnabled', False)
scene.setProperty('animations', False)
view.resize(1200, 900)
view.show()
output = ROOT / 'previews'; output.mkdir(exist_ok=True)
for room in ('study', 'family'):
    scene.setProperty('roomId', room)
    QTest.qWait(200)
    if not scene.property('pictureReady'):
        raise RuntimeError(f'Background did not load: {room}')
    if not view.grabWindow().save(str(output / f'{room}.png')):
        raise RuntimeError(f'Could not save preview: {room}')
view.close()
print(output)
