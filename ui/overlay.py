from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

import config
from ui.canvas import Canvas


class OverlayWindow(QWidget):
    def __init__(self, canvas: Canvas) -> None:
        super().__init__(None)
        self.canvas = canvas
        self.hint_label = QLabel(
            "Overlay mode\nDrag markers to the exact screen coordinates.\nRight-click a marker to duplicate or delete it."
        )
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(
            config.DESKTOP_BOUNDS.left,
            config.DESKTOP_BOUNDS.top,
            config.DESKTOP_BOUNDS.width,
            config.DESKTOP_BOUNDS.height,
        )
        self.setStyleSheet("background-color: rgba(4, 10, 18, 72);")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.hint_label.setObjectName("OverlayHint")
        self.hint_label.setParent(self)
        self.hint_label.adjustSize()
        self.hint_label.raise_()
        self.hide()

    def resizeEvent(self, event) -> None:
        self.hint_label.move(18, 18)
        super().resizeEvent(event)

    def set_input_transparent(self, transparent: bool) -> None:
        flags = self.windowFlags()
        if transparent:
            flags |= Qt.WindowType.WindowTransparentForInput
        else:
            flags &= ~Qt.WindowType.WindowTransparentForInput

        self.setWindowFlags(flags)
        if self.isVisible():
            self.show()
            self.raise_()

    def toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
            return
        self.show()
        self.raise_()
