"""Rover's native app and folder chooser, opened only on request."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QThread, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialogButtonBox, QFileDialog, QGridLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton,
)

from dialogs import BobDialog
from launcher import Launcher, LaunchError


def launch_choice(launcher: Launcher, kind: str, target: str, label: str) -> str:
    """Use the existing safe launcher without persisting a temporary choice."""
    if kind not in {"app", "folder"}:
        raise LaunchError("Choose an installed program or a folder.")
    key = "__program_picker__"
    previous = deepcopy(launcher.bindings.get(key))
    launcher.bindings[key] = {"kind": kind, "target": target, "label": label}
    try:
        return launcher.launch_binding(key)
    finally:
        if previous is None:
            launcher.bindings.pop(key, None)
        else:
            launcher.bindings[key] = previous


class ChoiceWorker(QThread):
    """Desktop helpers can wait briefly for another process; keep the UI live."""
    def __init__(self, launcher, kind, target, label, parent=None):
        super().__init__(parent)
        self.launcher = launcher
        self.choice = kind, target, label
        self.error = ""

    def run(self):
        try:
            launch_choice(self.launcher, *self.choice)
        except Exception as error:
            self.error = str(error)


class ProgramsDialog(BobDialog):
    def __init__(self, launcher: Launcher, parent=None):
        super().__init__("Open a program or folder", parent, width=600)
        self.launcher = launcher
        self.worker = None
        self.add_description("Choose something to open. Rover will keep your place in the room.")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find a program…")
        self.search.setAccessibleName("Find an installed program")
        self.body.addWidget(self.search)
        self.app_list = QListWidget()
        self.app_list.setAccessibleName("Installed programs")
        self.app_list.setMinimumHeight(250)
        for app in launcher.apps:
            item = QListWidgetItem(app.name)
            item.setData(Qt.ItemDataRole.UserRole, app.id)
            if app.icon:
                icon = QIcon.fromTheme(app.icon)
                if not icon.isNull():
                    item.setIcon(icon)
            self.app_list.addItem(item)
        self.body.addWidget(self.app_list)
        self.body.addWidget(QLabel("Your folders"))
        folders = QGridLayout()
        self.folder_buttons = []
        for index, (title, location) in enumerate((
            ("Home", QStandardPaths.StandardLocation.HomeLocation),
            ("Documents", QStandardPaths.StandardLocation.DocumentsLocation),
            ("Downloads", QStandardPaths.StandardLocation.DownloadLocation),
            ("Pictures", QStandardPaths.StandardLocation.PicturesLocation),
        )):
            target = QStandardPaths.writableLocation(location)
            if not target:
                target = str(Path.home())
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, p=target, name=title: self.begin_launch("folder", p, name))
            self.folder_buttons.append(button)
            folders.addWidget(button, index // 2, index % 2)
        browse = QPushButton("Browse for a folder…")
        browse.clicked.connect(self.browse_folder)
        self.folder_buttons.append(browse)
        folders.addWidget(browse, 2, 0, 1, 2)
        self.body.addLayout(folders)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setAccessibleName("Launch status")
        self.body.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel)
        self.open_button = self.buttons.button(QDialogButtonBox.StandardButton.Open)
        self.open_button.setText("Open program")
        self.open_button.setDefault(True)
        self.buttons.accepted.connect(self.open_selected)
        self.buttons.rejected.connect(self.reject)
        self.body.addWidget(self.buttons)
        self.search.textChanged.connect(self.filter_apps)
        self.search.returnPressed.connect(self.open_selected)
        self.app_list.itemDoubleClicked.connect(lambda item: self.open_selected())
        self.app_list.currentItemChanged.connect(self.update_open_button)
        self.filter_apps("")
        self.search.setFocus()
        self.resize(600, 620)

    def filter_apps(self, text):
        query = text.strip().casefold()
        first = None
        count = 0
        for index in range(self.app_list.count()):
            item = self.app_list.item(index)
            visible = query in item.text().casefold()
            item.setHidden(not visible)
            if visible:
                count += 1
                first = first or item
        self.app_list.setCurrentItem(first)
        self.status.setText(f"{count} program{'s' if count != 1 else ''}" if count else "No matching programs. Try another name or open a folder.")
        self.update_open_button()

    def update_open_button(self, *args):
        item = self.app_list.currentItem()
        self.open_button.setEnabled(self.worker is None and item is not None and not item.isHidden())

    def open_selected(self):
        item = self.app_list.currentItem()
        if item is not None and not item.isHidden():
            self.begin_launch("app", item.data(Qt.ItemDataRole.UserRole), item.text())

    def browse_folder(self):
        target = QFileDialog.getExistingDirectory(self, "Choose a folder", str(Path.home()))
        if target:
            self.begin_launch("folder", target, Path(target).name or target)

    def begin_launch(self, kind, target, label):
        if self.worker is not None:
            return
        self.status.setText(f"Opening {label}…")
        self.search.setEnabled(False)
        self.app_list.setEnabled(False)
        for button in self.folder_buttons:
            button.setEnabled(False)
        self.buttons.setEnabled(False)
        self.worker = ChoiceWorker(self.launcher, kind, target, label, self)
        self.worker.finished.connect(self.finish_launch)
        self.worker.start()

    def finish_launch(self):
        error = self.worker.error
        self.worker.deleteLater()
        self.worker = None
        if not error:
            self.accept()
            return
        self.search.setEnabled(True)
        self.app_list.setEnabled(True)
        for button in self.folder_buttons:
            button.setEnabled(True)
        self.buttons.setEnabled(True)
        self.update_open_button()
        self.status.setText(error.replace("Right-click", "Shift-click").replace("right-click", "shift-click"))

    def reject(self):
        if self.worker is None:
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)
