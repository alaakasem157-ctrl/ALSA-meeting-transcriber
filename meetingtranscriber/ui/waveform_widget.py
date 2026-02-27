from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._data: Optional[np.ndarray] = None
        self.setMinimumHeight(90)

    def set_data(self, data: np.ndarray) -> None:
        if data is None:
            self._data = None
        else:
            d = np.asarray(data, dtype=np.float32).flatten()
            self._data = d[-4096:]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        p.fillRect(rect, self.palette().window())

        if self._data is None or self._data.size < 4:
            return

        w = rect.width()
        h = rect.height()
        mid = rect.top() + h / 2.0

        d = self._data
        peak = float(np.max(np.abs(d)) + 1e-9)
        d = d / peak

        step = max(1, int(len(d) / max(1, w)))
        pts = []
        x = rect.left()
        for i in range(0, len(d), step):
            y = mid - float(d[i]) * (h * 0.40)
            pts.append((x, y))
            x += 1
            if x > rect.right():
                break

        pen = QPen(self.palette().text().color(), 2)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)

        for i in range(1, len(pts)):
            p.drawLine(int(pts[i - 1][0]), int(pts[i - 1][1]), int(pts[i][0]), int(pts[i][1]))