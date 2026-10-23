"""Square crop dialog for bot images."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

MAX_OUTPUT = 512
HANDLE = 12      # corner handle size (screen px)
MIN_BOX = 24     # smallest crop box (screen px)


class CropArea(QWidget):
    """Shows the image with a draggable/resizable square box over it."""
    changed = Signal()

    def __init__(self, image: QImage, view_size: int = 520):
        super().__init__()
        self.image = image
        # Scale to fit view_size x view_size
        s = min(view_size / image.width(), view_size / image.height(), 1.0)
        self.scale = s
        self.view_w = max(1, round(image.width() * s))
        self.view_h = max(1, round(image.height() * s))
        self.preview = image.scaled(self.view_w, self.view_h, Qt.IgnoreAspectRatio,
                                    Qt.SmoothTransformation)
        self.setFixedSize(self.view_w, self.view_h)
        self.setMouseTracking(True)
        # Start with the biggest centered square
        side = min(self.view_w, self.view_h)
        self.box = QRectF((self.view_w - side) / 2, (self.view_h - side) / 2, side, side)
        self._drag = None          # "move" or a corner name
        self._start = QPointF()
        self._start_box = QRectF()

    # ---- geometry helpers -----------------------------------------------------
    def _corners(self) -> dict[str, QPointF]:
        b = self.box
        return {"tl": b.topLeft(), "tr": b.topRight(), "bl": b.bottomLeft(), "br": b.bottomRight()}

    def _hit(self, p: QPointF):
        for name, c in self._corners().items():
            if abs(p.x() - c.x()) <= HANDLE and abs(p.y() - c.y()) <= HANDLE:
                return name
        return "move" if self.box.contains(p) else None

    def _clamp_move(self, box: QRectF) -> QRectF:
        x = min(max(box.x(), 0), self.view_w - box.width())
        y = min(max(box.y(), 0), self.view_h - box.height())
        return QRectF(x, y, box.width(), box.height())

    def _resize_from(self, corner: str, p: QPointF) -> QRectF:
        b = self._start_box
        # The opposite corner stays fixed
        anchor = {"tl": b.bottomRight(), "tr": b.bottomLeft(),
                  "bl": b.topRight(), "br": b.topLeft()}[corner]
        dx = p.x() - anchor.x()
        dy = p.y() - anchor.y()
        sx = -1 if corner in ("tl", "bl") else 1
        sy = -1 if corner in ("tl", "tr") else 1
        side = max(MIN_BOX, min(dx * sx, dy * sy))
        # Room available from the anchor towards the corner direction
        room_x = anchor.x() if sx < 0 else self.view_w - anchor.x()
        room_y = anchor.y() if sy < 0 else self.view_h - anchor.y()
        side = min(side, room_x, room_y)
        x = anchor.x() - side if sx < 0 else anchor.x()
        y = anchor.y() - side if sy < 0 else anchor.y()
        return QRectF(x, y, side, side)

    # ---- events -----------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        p = e.position()
        self._drag = self._hit(p)
        if self._drag is None:
            # Click outside the box: center the box on the click
            self._drag = "move"
            self.box = self._clamp_move(QRectF(p.x() - self.box.width() / 2,
                                               p.y() - self.box.height() / 2,
                                               self.box.width(), self.box.height()))
            self.update()
            self.changed.emit()
        self._start = p
        self._start_box = QRectF(self.box)

    def mouseMoveEvent(self, e):
        p = e.position()
        if self._drag is None:
            hit = self._hit(p)
            cursors = {"tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor,
                       "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
                       "move": Qt.SizeAllCursor}
            self.setCursor(cursors.get(hit, Qt.CrossCursor))
            return
        if self._drag == "move":
            d = p - self._start
            self.box = self._clamp_move(self._start_box.translated(d))
        else:
            self.box = self._resize_from(self._drag, p)
        self.update()
        self.changed.emit()

    def mouseReleaseEvent(self, e):
        self._drag = None

    def wheelEvent(self, e):
        step = 1.06 if e.angleDelta().y() > 0 else 1 / 1.06
        c = self.box.center()
        side = self.box.width() * step
        side = max(MIN_BOX, min(side, self.view_w, self.view_h))
        self.box = self._clamp_move(QRectF(c.x() - side / 2, c.y() - side / 2, side, side))
        self.update()
        self.changed.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawImage(0, 0, self.preview)
        # Dim everything outside the box
        outside = QPainterPath()
        outside.addRect(QRectF(0, 0, self.view_w, self.view_h))
        inner = QPainterPath()
        inner.addRect(self.box)
        p.fillPath(outside.subtracted(inner), QColor(0, 0, 0, 140))
        # Box outline, rule-of-thirds lines, corner handles
        p.setPen(QPen(QColor(255, 255, 255), 2))
        p.drawRect(self.box)
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        b = self.box
        for i in (1, 2):
            x = b.x() + b.width() * i / 3
            y = b.y() + b.height() * i / 3
            p.drawLine(QPointF(x, b.top()), QPointF(x, b.bottom()))
            p.drawLine(QPointF(b.left(), y), QPointF(b.right(), y))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255))
        for c in self._corners().values():
            p.drawRect(QRectF(c.x() - HANDLE / 2, c.y() - HANDLE / 2, HANDLE, HANDLE))
        p.end()

    def cropped(self) -> QImage:
        """The box cut from the full-resolution image, at most MAX_OUTPUT square."""
        b = self.box
        x = round(b.x() / self.scale)
        y = round(b.y() / self.scale)
        side = round(b.width() / self.scale)
        side = max(1, min(side, self.image.width() - x, self.image.height() - y))
        out = self.image.copy(x, y, side, side)
        if side > MAX_OUTPUT:
            out = out.scaled(MAX_OUTPUT, MAX_OUTPUT, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return out


class CropDialog(QDialog):
    """Usage: dlg = CropDialog(path); if dlg.exec(): dlg.result_image()"""

    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop image")
        lay = QVBoxLayout(self)

        self.area = CropArea(image)
        holder = QHBoxLayout()
        holder.addStretch(1)
        holder.addWidget(self.area)
        holder.addStretch(1)
        lay.addLayout(holder)

        hint = QLabel("Drag the box to move it, drag a corner or scroll to resize.")
        hint.setObjectName("cropHint")
        lay.addWidget(hint)

        row = QHBoxLayout()
        self.preview = QLabel()
        self.preview.setFixedSize(72, 72)
        self.preview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(self.preview)
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Use crop")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

        self.area.changed.connect(self._update_preview)
        self._update_preview()

    def _update_preview(self):
        from .avatar import rounded
        self.preview.setPixmap(rounded(self.area.cropped(), 72))

    def result_image(self) -> QImage:
        return self.area.cropped()

    @staticmethod
    def load(path: str) -> QImage | None:
        img = QImage(path)
        return None if img.isNull() else img
