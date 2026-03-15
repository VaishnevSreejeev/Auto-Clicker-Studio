from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QMenu, QWidget


class NodeWidget(QWidget):
    clicked = pyqtSignal(int)
    moved = pyqtSignal(int, int, int)
    deleted = pyqtSignal(int)
    duplicated = pyqtSignal(int)

    def __init__(self, node_id: int, parent=None) -> None:
        super().__init__(parent)
        self.node_id = node_id
        self.badge_text = str(node_id)
        self._selected = False
        self._active = False
        self._dragging = False
        self._drag_offset = QPoint()
        self.setFixedSize(42, 42)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def set_badge_text(self, text: str) -> None:
        if self.badge_text != text:
            self.badge_text = text
            self.update()

    def set_selected(self, value: bool) -> None:
        if self._selected != value:
            self._selected = value
            self.update()

    def set_active(self, value: bool) -> None:
        if self._active != value:
            self._active = value
            self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)
        fill = QColor("#45bdf9")
        outline = QColor("#dff6ff")

        if self._selected:
            fill = QColor("#39d4bc")
            outline = QColor("#f8ffff")
        if self._active:
            fill = QColor("#ffd166")
            outline = QColor("#fff3c5")

        painter.setBrush(fill)
        painter.setPen(QPen(outline, 2))
        painter.drawEllipse(rect)

        painter.setPen(QColor("#071019"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.badge_text)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.clicked.emit(self.node_id)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and self.parentWidget() is not None:
            parent_rect = self.parentWidget().rect()
            new_pos = self.mapToParent(event.pos() - self._drag_offset)
            max_x = max(0, parent_rect.width() - self.width())
            max_y = max(0, parent_rect.height() - self.height())
            new_x = min(max(new_pos.x(), 0), max_x)
            new_y = min(max(new_pos.y(), 0), max_y)
            self.move(new_x, new_y)
            self.moved.emit(
                self.node_id,
                new_x + (self.width() // 2),
                new_y + (self.height() // 2),
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        duplicate_action = menu.addAction("Duplicate Action")
        delete_action = menu.addAction("Delete Action")
        chosen = menu.exec(event.globalPos())
        if chosen == duplicate_action:
            self.duplicated.emit(self.node_id)
        elif chosen == delete_action:
            self.deleted.emit(self.node_id)
