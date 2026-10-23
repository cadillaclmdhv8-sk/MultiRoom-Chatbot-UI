"""Rounded-square avatar pixmaps, with a colored initials tile as fallback."""
from __future__ import annotations

import hashlib
import os

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath,
                           QPixmap)

from . import theme

_cache: dict[tuple, QPixmap] = {}


def color_for(name: str) -> str:
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    colors = theme.name_colors()
    return colors[h % len(colors)]


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _dpr() -> float:
    app = QGuiApplication.instance()
    return app.devicePixelRatio() if app else 1.0


def _paint(src: QPixmap | None, name: str, size: int, radius_ratio: float) -> QPixmap:
    dpr = _dpr()
    px = int(size * dpr)
    out = QPixmap(px, px)
    out.fill(Qt.transparent)

    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), px * radius_ratio, px * radius_ratio)
    p.setClipPath(path)

    if src is not None and not src.isNull():
        scaled = src.scaled(px, px, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (scaled.width() - px) // 2
        y = (scaled.height() - px) // 2
        p.drawPixmap(0, 0, scaled, x, y, px, px)
    else:
        p.fillRect(0, 0, px, px, QColor(color_for(name)))
        p.setPen(QColor("white"))
        f = QFont()
        f.setBold(True)
        f.setPixelSize(max(8, int(px * 0.38)))
        p.setFont(f)
        p.drawText(QRectF(0, 0, px, px), Qt.AlignCenter, _initials(name))
    p.end()

    out.setDevicePixelRatio(dpr)
    return out


def rounded(image: QImage, size: int, radius_ratio: float = 0.22) -> QPixmap:
    """Rounded-square pixmap from an in-memory image (not cached)."""
    return _paint(QPixmap.fromImage(image), "?", size, radius_ratio)


def avatar(image_path: str, name: str, size: int, radius_ratio: float = 0.22) -> QPixmap:
    """Cached rounded-square avatar; colored initials if the file is missing."""
    mtime = 0.0
    if image_path and os.path.isfile(image_path):
        try:
            mtime = os.path.getmtime(image_path)
        except OSError:
            pass
    key = (image_path, mtime, name, size, radius_ratio, _dpr(), theme.current())
    if key not in _cache:
        src = QPixmap(image_path) if mtime else None
        _cache[key] = _paint(src, name, size, radius_ratio)
    return _cache[key]
