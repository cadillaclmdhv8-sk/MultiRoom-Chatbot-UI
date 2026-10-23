from __future__ import annotations

import os

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QPushButton, QSpinBox, QVBoxLayout)

from .. import storage
from ..kobold import SAMPLER_PRESETS, KoboldClient, describe_error, run_background
from ..prompt import INSTRUCT_PRESETS
from .avatar import avatar, rounded
from .crop_dialog import CropDialog

class ClearDataDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clear all data")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Choose what to delete:"))
        self.bots = QCheckBox("Bots and their images")
        self.chats = QCheckBox("Saved chats")
        self.settings = QCheckBox("Settings (your name, image, theme, connection)")
        for c in (self.bots, self.chats, self.settings):
            c.setChecked(True)
            c.toggled.connect(self._update)
            lay.addWidget(c)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        self.go = QPushButton("Delete")
        self.go.setObjectName("danger")
        self.go.clicked.connect(self._confirm)
        btns.addWidget(cancel)
        btns.addWidget(self.go)
        lay.addLayout(btns)

    def _update(self, *_):
        self.go.setEnabled(any(self.choice()))

    def choice(self) -> tuple[bool, bool, bool]:
        return (self.bots.isChecked(), self.chats.isChecked(), self.settings.isChecked())

    def _confirm(self):
        if QMessageBox.warning(self, "Are you sure?", "This can't be undone. Delete now?",
                               QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.accept()


USER_IMAGE_ID = "user"   # saved as data/avatars/user.png (+ user_original.<ext>)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(480, 0)
        s = settings

        lay = QVBoxLayout(self)
        form = QFormLayout()

        url_row = QHBoxLayout()
        self.url = QLineEdit(s["kobold_url"])
        test = QPushButton("Test connection")
        test.setObjectName("secondary")
        test.clicked.connect(self._test)
        url_row.addWidget(self.url, 1)
        url_row.addWidget(test)
        form.addRow("KoboldAI URL", url_row)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.status.setWordWrap(True)
        form.addRow("", self.status)

        self.user = QLineEdit(s["user_name"])
        form.addRow("Your name", self.user)

        # Optional avatar for your own messages
        self._user_image = s.get("user_image", "")
        self._pending_user_crop = None   # (QImage, original path) until Save
        self._clear_user_image = False
        img_row = QHBoxLayout()
        self.user_preview = QLabel()
        self.user_preview.setFixedSize(40, 40)
        pick = QPushButton("Browse…")
        pick.setObjectName("secondary")
        pick.clicked.connect(self._pick_user_image)
        clear = QPushButton("Clear")
        clear.setObjectName("secondary")
        clear.clicked.connect(self._clear_user)
        img_row.addWidget(self.user_preview)
        img_row.addWidget(pick)
        img_row.addWidget(clear)
        img_row.addStretch(1)
        form.addRow("Your image", img_row)
        self._update_user_preview()

        self.max_len = QSpinBox()
        self.max_len.setRange(16, 2048)
        self.max_len.setValue(int(s["max_length"]))
        form.addRow("Max output tokens", self.max_len)

        self.avatar_size = QSpinBox()
        self.avatar_size.setRange(32, 128)
        self.avatar_size.setSingleStep(4)
        self.avatar_size.setSuffix(" px")
        self.avatar_size.setValue(int(s.get("avatar_size", 56)))
        form.addRow("Chat image size", self.avatar_size)

        self.sampler = QComboBox()
        self.sampler.addItems(SAMPLER_PRESETS)
        self.sampler.setCurrentText(s["sampler_preset"])
        self.temp = QDoubleSpinBox()
        self.temp.setRange(0.05, 3.0)
        self.temp.setSingleStep(0.05)
        self.temp.setValue(float(s["temperature"]))
        form.addRow("Sampler preset", self.sampler)
        form.addRow("Temperature (Custom)", self.temp)

        self.instruct = QComboBox()
        self.instruct.addItems(list(INSTRUCT_PRESETS) + ["Custom"])
        self.instruct.setCurrentText(s["instruct_preset"])
        self.start_tag = QLineEdit(s["instruct_start"].replace("\n", "\\n"))
        self.end_tag = QLineEdit(s["instruct_end"].replace("\n", "\\n"))
        self.start_tag.setPlaceholderText(r"e.g. [INST]  (use \n for new lines)")
        self.end_tag.setPlaceholderText(r"e.g.  [/INST]\n")
        form.addRow("Instruct format", self.instruct)
        form.addRow("Start tag (Custom)", self.start_tag)
        form.addRow("End tag (Custom)", self.end_tag)
        lay.addLayout(form)

        # Danger zone
        danger = QHBoxLayout()
        dl = QLabel("Danger zone")
        dl.setObjectName("dangerLabel")
        clear_all = QPushButton("Clear all data…")
        clear_all.setObjectName("danger")
        clear_all.clicked.connect(self._clear_all)
        danger.addWidget(dl)
        danger.addStretch(1)
        danger.addWidget(clear_all)
        lay.addSpacing(8)
        lay.addLayout(danger)
        # Set when the user confirms clearing: (bots, chats, settings). The main window does it.
        self.clear_requested: tuple[bool, bool, bool] | None = None

        self.sampler.currentTextChanged.connect(self._toggle)
        self.instruct.currentTextChanged.connect(self._toggle)
        self._toggle()

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def _pick_user_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose your image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if not path:
            return
        img = CropDialog.load(path)
        if img is None:
            QMessageBox.warning(self, "Can't open image", "That file isn't an image.")
            return
        dlg = CropDialog(img, self)
        if dlg.exec() == CropDialog.Accepted:
            self._pending_user_crop = (dlg.result_image(), os.path.normpath(path))
            self._clear_user_image = False
            self._update_user_preview()

    def _clear_user(self):
        self._pending_user_crop = None
        self._clear_user_image = True
        self._update_user_preview()

    def _update_user_preview(self):
        if self._pending_user_crop is not None:
            self.user_preview.setPixmap(rounded(self._pending_user_crop[0], 40))
        elif self._user_image and not self._clear_user_image and os.path.isfile(self._user_image):
            self.user_preview.setPixmap(avatar(self._user_image, "?", 40))
        else:
            self.user_preview.clear()
            self.user_preview.setText("None")

    def _clear_all(self):
        dlg = ClearDataDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.clear_requested = dlg.choice()
            self.reject()   # other edits in this dialog are dropped

    def accept(self):
        # Write image changes only when Save is pressed
        try:
            if self._pending_user_crop is not None:
                image, original = self._pending_user_crop
                storage.import_image(original, USER_IMAGE_ID, "_original")
                storage.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
                out = storage.AVATAR_DIR / f"{USER_IMAGE_ID}.png"
                if not image.save(str(out), "PNG"):
                    raise OSError(f"Couldn't write {out}")
                storage.clear_variants(USER_IMAGE_ID, ".png")
                self._user_image = str(out)
            elif self._clear_user_image:
                storage.delete_bot_images(USER_IMAGE_ID)
                self._user_image = ""
        except OSError as e:
            QMessageBox.warning(self, "Save failed", f"Couldn't save your image:\n{e}")
            return
        super().accept()

    def _toggle(self, *_):
        self.temp.setEnabled(self.sampler.currentText() == "Custom")
        custom = self.instruct.currentText() == "Custom"
        self.start_tag.setEnabled(custom)
        self.end_tag.setEnabled(custom)

    def _test(self):
        url = self.url.text().strip()
        self.status.setText("Connecting…")
        client = KoboldClient(url)
        run_background(lambda: (client.model_name(), client.max_context()),
                       on_done=lambda r: self._show(f"✔ Connected: {r[0]}  (context {r[1]})"),
                       on_error=lambda e: self._show("✖ " + describe_error(e, url)))

    def _show(self, text: str) -> None:
        try:
            self.status.setText(text)
        except RuntimeError:
            pass  # dialog already closed

    def values(self) -> dict:
        def unescape(t: str) -> str:
            return t.replace("\\n", "\n")
        return {
            "kobold_url": self.url.text().strip() or "http://localhost:5001",
            "user_name": self.user.text().strip().replace("[", "").replace("]", "") or "You",
            "max_length": self.max_len.value(),
            "avatar_size": self.avatar_size.value(),
            "user_image": self._user_image,
            "sampler_preset": self.sampler.currentText(),
            "temperature": round(self.temp.value(), 2),
            "instruct_preset": self.instruct.currentText(),
            "instruct_start": unescape(self.start_tag.text()),
            "instruct_end": unescape(self.end_tag.text()),
        }
