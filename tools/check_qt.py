#!/usr/bin/env python3
"""Check native Python bindings and QML modules without loading any Bob assets."""
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
if sys.version_info < (3, 10):
    sys.exit('Python 3.10 or newer is required.')
try:
    from PySide6 import QtCore, QtGui, QtNetwork, QtQuick, QtSvg, QtTest, QtWidgets
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    app = QtGui.QGuiApplication([])
    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b'''import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item { width: 200; height: 100; RowLayout { Button { text: "Check" } } }
''', QtCore.QUrl())
    item = component.create()
    if item is None:
        sys.exit('\n'.join(error.toString() for error in component.errors()))
except ImportError as error:
    sys.exit(str(error))
print('Python, PySide6, and QML modules available.')
