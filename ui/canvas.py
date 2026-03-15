from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QFrame

import config
from models import ActionNode, Profile
from ui.node_widget import NodeWidget


class Canvas(QFrame):
    node_selected = pyqtSignal(object)
    selection_cleared = pyqtSignal()
    profile_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Canvas")
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.desktop_bounds = config.DESKTOP_BOUNDS
        self.profile = Profile()
        self.node_widgets: dict[int, NodeWidget] = {}
        self.selected_node_id: int | None = None
        self.active_node_id: int | None = None
        self.resize(self.desktop_bounds.width, self.desktop_bounds.height)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        grid_pen = QPen(QColor(160, 210, 220, 26))
        grid_pen.setWidth(1)
        painter.setPen(grid_pen)

        spacing = 120
        for x in range(0, self.width(), spacing):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), spacing):
            painter.drawLine(0, y, self.width(), y)

        line_pen = QPen(QColor("#ffd166"))
        line_pen.setWidth(2)
        line_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(line_pen)

        for node in self.profile.nodes:
            if node.action_type != "Drag" or node.target_x is None or node.target_y is None:
                continue
            start = self.desktop_to_canvas(node.x, node.y)
            end = self.desktop_to_canvas(node.target_x, node.target_y)
            painter.drawLine(start, end)
            painter.setBrush(QColor("#ffd166"))
            painter.drawEllipse(end, 5, 5)

        hint_pen = QPen(QColor("#9ac7d2"))
        painter.setPen(hint_pen)
        painter.drawText(
            self.rect().adjusted(14, 14, -14, -14),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            "Overlay editing: drag markers to place actions. Right-click a marker to duplicate or delete it.",
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.childAt(event.position().toPoint()) is None:
            self.clear_selection()
        super().mousePressEvent(event)

    def desktop_to_canvas(self, x: int, y: int) -> QPoint:
        return QPoint(x - self.desktop_bounds.left, y - self.desktop_bounds.top)

    def canvas_to_desktop(self, x: int, y: int) -> tuple[int, int]:
        return x + self.desktop_bounds.left, y + self.desktop_bounds.top

    def add_node(self, x: int | None = None, y: int | None = None) -> ActionNode:
        if x is None or y is None:
            cursor = QCursor.pos()
            if self.desktop_bounds.contains(cursor.x(), cursor.y()):
                x, y = cursor.x(), cursor.y()
            else:
                x, y = self.desktop_bounds.center

        x, y = self.desktop_bounds.clamp(x, y, border=config.SAFETY_BORDER)
        node = ActionNode(id=self.profile.next_node_id(), x=x, y=y)
        self.profile.nodes.append(node)
        self._add_node_widget(node)
        self._refresh_step_badges()
        self.select_node(node.id)
        self.profile_changed.emit()
        self.update()
        return node

    def update_node(self, node: ActionNode) -> None:
        stored = self.profile.get_node(node.id)
        if stored is None:
            return

        stored.x, stored.y = self.desktop_bounds.clamp(node.x, node.y, border=config.SAFETY_BORDER)
        stored.click_type = node.click_type
        stored.action_type = node.action_type
        stored.pre_delay = node.pre_delay
        stored.post_delay = node.post_delay
        stored.hold_ms = node.hold_ms
        stored.drag_duration_ms = node.drag_duration_ms
        stored.target_x = node.target_x
        stored.target_y = node.target_y
        if stored.action_type == "Drag":
            stored.ensure_drag_target()
            stored.target_x, stored.target_y = self.desktop_bounds.clamp(
                stored.target_x,
                stored.target_y,
                border=config.SAFETY_BORDER,
            )

        self._position_widget(stored.id)
        self._update_widget_appearance(stored.id)
        if self.selected_node_id == stored.id:
            self.node_selected.emit(stored)
        self.update()

    def duplicate_node(self, node_id: int) -> ActionNode | None:
        duplicate = self.profile.duplicate_node(node_id)
        if duplicate is None:
            return None

        duplicate.x, duplicate.y = self.desktop_bounds.clamp(duplicate.x, duplicate.y, border=config.SAFETY_BORDER)
        if duplicate.target_x is not None and duplicate.target_y is not None:
            duplicate.target_x, duplicate.target_y = self.desktop_bounds.clamp(
                duplicate.target_x,
                duplicate.target_y,
                border=config.SAFETY_BORDER,
            )

        self._add_node_widget(duplicate)
        self._refresh_step_badges()
        self.select_node(duplicate.id)
        self.profile_changed.emit()
        self.update()
        return duplicate

    def delete_node(self, node_id: int) -> bool:
        if not self.profile.remove_node(node_id):
            return False

        widget = self.node_widgets.pop(node_id, None)
        if widget is not None:
            widget.deleteLater()

        if self.selected_node_id == node_id:
            self.selected_node_id = None
            if self.profile.nodes:
                self.select_node(self.profile.nodes[0].id)
            else:
                self.selection_cleared.emit()

        self._refresh_step_badges()
        self.profile_changed.emit()
        self.update()
        return True

    def move_node(self, node_id: int, direction: int) -> bool:
        moved = self.profile.move_node(node_id, direction)
        if moved:
            self._refresh_step_badges()
            self.profile_changed.emit()
            self.update()
        return moved

    def select_node(self, node_id: int, emit_signal: bool = True) -> None:
        node = self.profile.get_node(node_id)
        if node is None:
            return

        self.selected_node_id = node_id
        for current_id, widget in self.node_widgets.items():
            widget.set_selected(current_id == node_id)
        if emit_signal:
            self.node_selected.emit(node)

    def clear_selection(self) -> None:
        self.selected_node_id = None
        for widget in self.node_widgets.values():
            widget.set_selected(False)
        self.selection_cleared.emit()

    def set_active_node(self, node_id: int | None) -> None:
        self.active_node_id = node_id
        self._update_widget_appearance()

    def load_profile(self, profile: Profile) -> None:
        for widget in self.node_widgets.values():
            widget.deleteLater()
        self.node_widgets.clear()

        self.profile = profile
        self.selected_node_id = None
        self.active_node_id = None

        for node in self.profile.nodes:
            node.x, node.y = self.desktop_bounds.clamp(node.x, node.y, border=config.SAFETY_BORDER)
            if node.action_type == "Drag":
                node.ensure_drag_target()
                node.target_x, node.target_y = self.desktop_bounds.clamp(
                    node.target_x,
                    node.target_y,
                    border=config.SAFETY_BORDER,
                )
            self._add_node_widget(node)

        self._refresh_step_badges()
        self.profile_changed.emit()
        self.update()

    def _add_node_widget(self, node: ActionNode) -> None:
        widget = NodeWidget(node.id, self)
        widget.clicked.connect(self.select_node)
        widget.moved.connect(self._on_widget_moved)
        widget.deleted.connect(self.delete_node)
        widget.duplicated.connect(self.duplicate_node)
        widget.show()
        self.node_widgets[node.id] = widget
        self._position_widget(node.id)
        self._update_widget_appearance(node.id)

    def _position_widget(self, node_id: int) -> None:
        node = self.profile.get_node(node_id)
        widget = self.node_widgets.get(node_id)
        if node is None or widget is None:
            return

        canvas_point = self.desktop_to_canvas(node.x, node.y)
        widget.move(canvas_point.x() - widget.width() // 2, canvas_point.y() - widget.height() // 2)
        widget.setToolTip(node.summary)

    def _refresh_step_badges(self) -> None:
        for index, node in enumerate(self.profile.nodes, start=1):
            widget = self.node_widgets.get(node.id)
            if widget is not None:
                widget.set_badge_text(str(index))
                widget.setToolTip(f"Step {index}\nID {node.id}\n{node.summary}")
        self._update_widget_appearance()

    def _update_widget_appearance(self, node_id: int | None = None) -> None:
        target_ids = [node_id] if node_id is not None else list(self.node_widgets.keys())
        for current_id in target_ids:
            widget = self.node_widgets.get(current_id)
            if widget is None:
                continue
            widget.set_selected(current_id == self.selected_node_id)
            widget.set_active(current_id == self.active_node_id)

    def _on_widget_moved(self, node_id: int, canvas_x: int, canvas_y: int) -> None:
        node = self.profile.get_node(node_id)
        if node is None:
            return

        node.x, node.y = self.canvas_to_desktop(canvas_x, canvas_y)
        node.x, node.y = self.desktop_bounds.clamp(node.x, node.y, border=config.SAFETY_BORDER)
        self._position_widget(node_id)
        if self.selected_node_id == node_id:
            self.node_selected.emit(node)
        self.update()
