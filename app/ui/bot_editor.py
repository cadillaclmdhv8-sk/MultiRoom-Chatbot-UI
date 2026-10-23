from __future__ import annotations

import os

from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from .. import storage
from ..models import Bot, new_id
from .avatar import avatar, rounded
from .crop_dialog import CropDialog


class BotEditor(QDialog):
    """Add or edit a bot. After exec(): .deleted is True if Delete was pressed."""

    def __init__(self, bot: Bot | None, taken_names: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit bot" if bot else "New bot")
        self.resize(520, 560)
        self.bot = bot
        self.deleted = False
        self._taken = {n.lower() for n in taken_names}
        self._bot_id = bot.id if bot else new_id()
        self._pending_crop = None   # QImage cropped but not saved yet
        # An existing crop stays valid until the source path is changed
        self._crop_path = bot.image_path if bot and bot.source_image else ""

        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(96, 96)
        top.addWidget(self.preview)

        form = QFormLayout()
        self.name = QLineEdit(bot.name if bot else "")
        self.name.setPlaceholderText("e.g. Ashley")
        self.name.textChanged.connect(self._update_preview)
        self.desc = QLineEdit(bot.description if bot else "")
        self.desc.setPlaceholderText("Short line shown under the card")
        img_row = QHBoxLayout()
        start_path = (bot.source_image or bot.image_path) if bot else ""
        self.image = QLineEdit(start_path)
        self.image.setPlaceholderText("Path to an image on your PC")
        self.image.textEdited.connect(self._path_typed)
        browse = QPushButton("Browse…")
        browse.setObjectName("secondary")
        browse.clicked.connect(self._browse)
        self.crop_btn = QPushButton("Crop…")
        self.crop_btn.setObjectName("secondary")
        self.crop_btn.clicked.connect(self._crop)
        img_row.addWidget(self.image, 1)
        img_row.addWidget(browse)
        img_row.addWidget(self.crop_btn)
        form.addRow("Name", self.name)
        form.addRow("Description", self.desc)
        form.addRow("Image", img_row)
        top.addLayout(form, 1)
        lay.addLayout(top)

        lay.addWidget(QLabel("Context: personality, background and speech quirks sent to the AI"))
        self.context = QPlainTextEdit(bot.context if bot else "")
        self.context.setPlaceholderText(
            "Bubbly 22-year-old art student. Says 'literally' a lot, uses lots of "
            "exclamation marks, teases Victor constantly…")
        lay.addWidget(self.context, 1)

        btns = QHBoxLayout()
        if bot:
            delete = QPushButton("Delete")
            delete.setObjectName("danger")
            delete.clicked.connect(self._delete)
            btns.addWidget(delete)
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)
        self._update_preview()

    def _browse(self):
        start = os.path.dirname(self.image.text()) if self.image.text() else ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose image", start, "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if path:
            self.image.setText(os.path.normpath(path))
            self._path_typed()
            self._crop()

    def _src_path(self) -> str:
        return self.image.text().strip().strip('"')

    def _path_typed(self, *_):
        # A new source image: any earlier crop no longer applies
        self._pending_crop = None
        self._crop_path = ""
        self._update_preview()

    def _crop(self):
        img = CropDialog.load(self._src_path())
        if img is None:
            QMessageBox.warning(self, "Can't open image", "Choose an image file first.")
            return
        dlg = CropDialog(img, self)
        if dlg.exec() == CropDialog.Accepted:
            self._pending_crop = dlg.result_image()
            self._update_preview()

    def _update_preview(self):
        if not hasattr(self, "crop_btn"):
            return  # still building the dialog
        name = self.name.text().strip() or "?"
        if self._pending_crop is not None:
            pm = rounded(self._pending_crop, 96)
        elif self._crop_path:
            pm = avatar(self._crop_path, name, 96)
        else:
            pm = avatar(self._src_path(), name, 96)
        self.preview.setPixmap(pm)
        self.crop_btn.setEnabled(os.path.isfile(self._src_path()))

    def _delete(self):
        if QMessageBox.question(self, "Delete bot",
                                f"Delete {self.bot.name}? This can't be undone.") == QMessageBox.Yes:
            self.deleted = True
            self.accept()

    def _save(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Give the bot a name.")
            return
        if any(c in name for c in "[]:"):
            QMessageBox.warning(self, "Bad name", "Names can't contain [ ] or :")
            return
        if name.lower() in self._taken:
            QMessageBox.warning(self, "Name taken", f"There's already a bot called {name}.")
            return
        img = self._src_path()
        if img and not os.path.isfile(img) and not self._crop_path:
            if QMessageBox.question(self, "Image not found",
                                    "That image path doesn't exist. Save anyway?") != QMessageBox.Yes:
                return
        # Keep copies of the images in data/avatars so they survive the originals moving
        bid = self._bot_id
        try:
            if self._pending_crop is not None:
                source = storage.import_image(img, bid, "_original")
                storage.AVATAR_DIR.mkdir(parents=True, exist_ok=True)
                out = storage.AVATAR_DIR / f"{bid}.png"
                if not self._pending_crop.save(str(out), "PNG"):
                    raise OSError(f"Couldn't write {out}")
                storage.clear_variants(bid, ".png")
                image_path = str(out)
            elif self._crop_path:
                image_path, source = self._crop_path, storage.import_image(img, bid, "_original")
            else:
                image_path, source = storage.import_image(img, bid), ""
                storage.clear_variants(f"{bid}_original")
        except OSError as e:
            QMessageBox.warning(self, "Save failed", f"Couldn't copy the image:\n{e}")
            return
        if self.bot is None:
            self.bot = Bot(name=name, id=self._bot_id)
        self.bot.name = name
        self.bot.description = self.desc.text().strip()
        self.bot.context = self.context.toPlainText().strip()
        self.bot.image_path = image_path
        self.bot.source_image = source
        self.accept()
