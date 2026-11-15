"""Small, keyboard-friendly dialogs for the Bob desktop room.

These dialogs deliberately use real Qt controls and an era-appropriate palette.
The launcher owns persistence; editing a dialog does not change it until Save.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCalendarWidget, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QRadioButton, QStackedWidget,
    QTextEdit, QVBoxLayout, QWidget,
)


RETRO_STYLE = """
QDialog {
    background: #c0c0c0;
    color: #000000;
    font-family: "W95FA", "MS Sans Serif", sans-serif;
    font-size: 16px;
}
QDialog QWidget {
    color: #000000;
    font-family: "W95FA", "MS Sans Serif", sans-serif;
    font-size: 16px;
}
QLabel#bobDialogHeading {
    background: #000080;
    color: #ffffff;
    padding: 5px 8px;
    font-weight: bold;
}
QDialog QPushButton, QDialog QComboBox {
    background: #c0c0c0;
    color: #000000;
    border-top: 2px solid #ffffff;
    border-left: 2px solid #ffffff;
    border-bottom: 2px solid #404040;
    border-right: 2px solid #404040;
    border-radius: 0;
    padding: 5px 12px;
    min-height: 22px;
}
QDialog QPushButton:pressed {
    border-top-color: #404040;
    border-left-color: #404040;
    border-bottom-color: #ffffff;
    border-right-color: #ffffff;
    padding: 6px 11px 4px 13px;
}
QDialog QPushButton:focus {
    outline: 1px dotted #000000;
}
QDialog QPushButton:disabled {
    color: #777777;
}
QDialog QLineEdit, QDialog QTextEdit, QDialog QAbstractItemView {
    background: #ffffff;
    color: #000000;
    border-top: 2px solid #404040;
    border-left: 2px solid #404040;
    border-bottom: 2px solid #ffffff;
    border-right: 2px solid #ffffff;
    border-radius: 0;
    padding: 4px;
    selection-background-color: #000080;
    selection-color: #ffffff;
}
QDialog QCheckBox, QDialog QRadioButton {
    spacing: 8px;
    padding: 4px 0;
}
QDialog QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #000080;
}
QCalendarWidget QToolButton {
    color: #ffffff;
    background: #000080;
    padding: 6px;
}
QCalendarWidget QSpinBox {
    background: #ffffff;
    color: #000000;
}
"""


class BobDialog(QDialog):
    """Shared heading and button row; the operating system supplies window chrome."""

    def __init__(self, title: str, parent=None, width=500):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(360)
        self.resize(width, 320)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(12, 12, 12, 12)
        self.body.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("bobDialogHeading")
        self.body.addWidget(heading)

    def add_description(self, text):
        label = QLabel(text)
        label.setWordWrap(True)
        self.body.addWidget(label)
        return label

    def add_buttons(self, save_label="&Save"):
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText(save_label)
        save.setDefault(True)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        self.body.addWidget(buttons)
        return buttons

    def show_error(self, exc):
        QMessageBox.warning(self, "Couldn't save", str(exc))


class NotesDialog(BobDialog):
    def __init__(self, launcher, parent=None):
        super().__init__("Bob's Notepad", parent, width=600)
        self.launcher = launcher
        self.add_description("A little space for your ideas, lists, and reminders.")
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setAccessibleName("Your notes")
        self.editor.setPlainText(str(launcher.store.data.get("notes", "")))
        self.editor.setMinimumHeight(250)
        self.body.addWidget(self.editor)
        self.add_buttons()
        self.resize(600, 440)
        self.editor.setFocus()

    def save(self):
        old = self.launcher.store.data.get("notes", "")
        try:
            self.launcher.save_notes(self.editor.toPlainText())
        except (OSError, ValueError, RuntimeError) as exc:
            self.launcher.store.data["notes"] = old
            self.show_error(exc)
            return
        self.accept()


class BindingDialog(BobDialog):
    def __init__(self, launcher, object_id, parent=None, *, initial_binding=None, object_label=None):
        super().__init__("Choose what this object opens", parent, width=560)
        self.launcher = launcher
        self.object_id = object_id
        self.add_description(f"Choose what {object_label or 'this object'} opens. This change applies only to this object.")
        binding = deepcopy(initial_binding if initial_binding is not None
                           else launcher.store.data.get("bindings", {}).get(object_id, {}))
        self.kind_group = QButtonGroup(self)
        kind_row = QHBoxLayout()
        for index, (kind, title) in enumerate((
            ("app", "&Application"), ("folder", "&Folder"), ("url", "&Web or email link")
        )):
            button = QRadioButton(title)
            button.setProperty("binding_kind", kind)
            self.kind_group.addButton(button, index)
            kind_row.addWidget(button)
        self.body.addLayout(kind_row)

        self.pages = QStackedWidget()
        self.body.addWidget(self.pages)

        app_page = QWidget()
        app_form = QFormLayout(app_page)
        app_form.setContentsMargins(0, 6, 0, 6)
        self.apps_combo = QComboBox()
        self.apps_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.apps_combo.setMinimumContentsLength(20)
        self.apps_combo.setMaxVisibleItems(14)
        for app in launcher.apps:
            self.apps_combo.addItem(app.name, app.id)
        app_form.addRow("&Open:", self.apps_combo)
        if not launcher.apps:
            label = QLabel("No installed applications were found. Choose a folder or link instead.")
            label.setWordWrap(True)
            app_form.addRow(label)
        self.pages.addWidget(app_page)

        folder_page = QWidget()
        folder_form = QFormLayout(folder_page)
        folder_form.setContentsMargins(0, 6, 0, 6)
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(str(Path.home()))
        self.folder_edit.setAccessibleName("Folder path")
        browse = QPushButton("&Browse…")
        browse.clicked.connect(self.browse_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        folder_form.addRow("Folder:", folder_row)
        self.pages.addWidget(folder_page)

        url_page = QWidget()
        url_form = QFormLayout(url_page)
        url_form.setContentsMargins(0, 6, 0, 6)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com or mailto:")
        url_form.addRow("&Address:", self.url_edit)
        self.pages.addWidget(url_page)

        label_form = QFormLayout()
        self.label_edit = QLineEdit(binding.get("label", ""))
        self.label_edit.setPlaceholderText("Optional friendly name")
        label_form.addRow("&Name:", self.label_edit)
        self.body.addLayout(label_form)
        self.body.addStretch()
        self.add_buttons("&OK")
        self.kind_group.idClicked.connect(self.pages.setCurrentIndex)

        kind = binding.get("kind", "app")
        target = binding.get("target", "")
        selected = {"app": 0, "folder": 1, "url": 2}.get(kind, 0)
        self.kind_group.button(selected).setChecked(True)
        self.pages.setCurrentIndex(selected)
        if kind == "app":
            index = self.apps_combo.findData(target)
            if index >= 0:
                self.apps_combo.setCurrentIndex(index)
        elif kind == "folder":
            self.folder_edit.setText(target)
        elif kind == "url":
            self.url_edit.setText(target)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Choose a folder", self.folder_edit.text() or str(Path.home())
        )
        if folder:
            self.folder_edit.setText(folder)

    def save(self):
        kind = self.kind_group.checkedButton().property("binding_kind")
        target = {
            "app": self.apps_combo.currentData(),
            "folder": self.folder_edit.text().strip(),
            "url": self.url_edit.text().strip(),
        }[kind]
        if not target:
            self.show_error(ValueError("Choose an application, folder, or address first."))
            return
        old = deepcopy(self.launcher.store.data.get("bindings", {}))
        try:
            self.launcher.set_binding(self.object_id, kind, target, self.label_edit.text().strip())
        except (OSError, ValueError, RuntimeError) as exc:
            self.launcher.store.data["bindings"] = old
            self.show_error(exc)
            return
        self.accept()


class CalendarDialog(BobDialog):
    def __init__(self, launcher, parent=None):
        super().__init__("Bob's Calendar", parent, width=560)
        self.launcher = launcher
        raw_notes = launcher.store.data.get("calendar_notes", {})
        self.notes = deepcopy(raw_notes) if isinstance(raw_notes, dict) else {}
        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(False)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setAccessibleName("Choose a date")
        self.calendar.setMinimumHeight(250)
        self.body.addWidget(self.calendar)
        self.date_label = QLabel()
        self.body.addWidget(self.date_label)
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setAccessibleName("Notes for the selected date")
        self.editor.setPlaceholderText("Write something to remember for this day…")
        self.editor.setMinimumHeight(100)
        self.body.addWidget(self.editor)
        self.selected_key = self.calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        self.load_day()
        self.calendar.selectionChanged.connect(self.select_day)
        self.add_buttons()
        self.resize(560, 590)

    def stash_day(self):
        text = self.editor.toPlainText()
        if text.strip():
            self.notes[self.selected_key] = text
        else:
            self.notes.pop(self.selected_key, None)

    def load_day(self):
        date = QDate.fromString(self.selected_key, Qt.DateFormat.ISODate)
        self.date_label.setText(date.toString("dddd, MMMM d, yyyy"))
        self.editor.setPlainText(str(self.notes.get(self.selected_key, "")))

    def select_day(self):
        self.stash_day()
        self.selected_key = self.calendar.selectedDate().toString(Qt.DateFormat.ISODate)
        self.load_day()

    def save(self):
        self.stash_day()
        had_key = "calendar_notes" in self.launcher.store.data
        old = self.launcher.store.data.get("calendar_notes")
        self.launcher.store.data["calendar_notes"] = deepcopy(self.notes)
        try:
            self.launcher.store.save()
        except (OSError, ValueError, RuntimeError) as exc:
            if had_key:
                self.launcher.store.data["calendar_notes"] = old
            else:
                self.launcher.store.data.pop("calendar_notes", None)
            self.show_error(exc)
            return
        self.accept()


class SettingsDialog(BobDialog):
    def __init__(self, launcher, parent=None):
        super().__init__("Room Options", parent)
        self.launcher = launcher
        settings = launcher.store.data.get("settings", {})
        self.checks = {}
        for key, text, default in (
            ("animations", "&Animate Rover and the room", True),
            ("sound", "Play &sounds", False),
            ("minimize_after_launch", "&Minimize the room after opening an app or folder", True),
        ):
            box = QCheckBox(text)
            box.setChecked(bool(settings.get(key, default)))
            self.checks[key] = box
            self.body.addWidget(box)
        self.add_description("You can also right-click a room object to change what it opens.")
        self.body.addStretch()
        self.add_buttons("&OK")

    def save(self):
        old = deepcopy(self.launcher.store.data.get("settings", {}))
        updated = dict(old)
        updated.update({key: box.isChecked() for key, box in self.checks.items()})
        self.launcher.store.data["settings"] = updated
        try:
            self.launcher.store.save()
        except (OSError, ValueError, RuntimeError) as exc:
            self.launcher.store.data["settings"] = old
            self.show_error(exc)
            return
        self.accept()


class HelpDialog(BobDialog):
    def __init__(self, parent=None):
        super().__init__("Welcome to Bob's Room", parent, width=550)
        self.add_description("Click an object in the room to use it. Rover is here to help!")
        form = QFormLayout()
        form.setHorizontalSpacing(22)
        form.setVerticalSpacing(10)
        for shortcut, description in (
            ("F1", "Show the names of the things you can click."),
            ("F11", "Switch between full screen and a window."),
            ("Esc", "Leave full screen; in a window, close the room."),
            ("Tab / Shift+Tab", "Move between room objects."),
            ("Enter / Space", "Use the selected object."),
            ("Right-click", "Choose the app, folder, or link an object opens."),
        ):
            label = QLabel(description)
            label.setWordWrap(True)
            form.addRow(QLabel(shortcut), label)
        self.body.addLayout(form)
        self.add_description("Your notes, calendar notes, and room options are kept on this computer.")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        self.body.addWidget(buttons)
        self.resize(550, 430)
