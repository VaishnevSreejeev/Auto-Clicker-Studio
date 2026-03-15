from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import config
from models import ACTION_TYPES, CLICK_TYPES, ActionNode


class Sidebar(QWidget):
    node_updated = pyqtSignal(object)
    duplicate_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.current_node: ActionNode | None = None
        self._updating = False
        self._init_ui()
        self.clear()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.overview_group = QGroupBox("Selected Action")
        overview_form = QFormLayout(self.overview_group)
        self.lbl_id = QLabel("None")
        self.summary_label = QLabel("Select an action from the sequence list or overlay.")
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("MetaText")
        self.source_label = QLabel("Manual")
        self.source_label.setObjectName("MetaText")
        overview_form.addRow("ID", self.lbl_id)
        overview_form.addRow("Summary", self.summary_label)
        overview_form.addRow("Source", self.source_label)

        self.placement_group = QGroupBox("Placement")
        placement_form = QFormLayout(self.placement_group)
        self.spin_x = QSpinBox()
        self.spin_y = QSpinBox()
        self.spin_target_x = QSpinBox()
        self.spin_target_y = QSpinBox()

        for spin in (self.spin_x, self.spin_target_x):
            spin.setRange(config.DESKTOP_BOUNDS.left, config.DESKTOP_BOUNDS.right)
        for spin in (self.spin_y, self.spin_target_y):
            spin.setRange(config.DESKTOP_BOUNDS.top, config.DESKTOP_BOUNDS.bottom)

        placement_form.addRow("X", self.spin_x)
        placement_form.addRow("Y", self.spin_y)
        placement_form.addRow("Target X", self.spin_target_x)
        placement_form.addRow("Target Y", self.spin_target_y)

        self.action_group = QGroupBox("Action")
        action_form = QFormLayout(self.action_group)
        self.combo_click = QComboBox()
        self.combo_action = QComboBox()
        self.spin_hold = QSpinBox()
        self.spin_drag_duration = QSpinBox()
        self.spin_move_duration = QSpinBox()

        self.combo_click.addItems(CLICK_TYPES)
        self.combo_action.addItems(ACTION_TYPES)

        self.spin_hold.setRange(50, 60_000)
        self.spin_hold.setSuffix(" ms")
        self.spin_drag_duration.setRange(50, 60_000)
        self.spin_drag_duration.setSuffix(" ms")
        self.spin_move_duration.setRange(0, 60_000)
        self.spin_move_duration.setSuffix(" ms")

        action_form.addRow("Action", self.combo_action)
        action_form.addRow("Click type", self.combo_click)
        action_form.addRow("Hold", self.spin_hold)
        action_form.addRow("Drag duration", self.spin_drag_duration)
        action_form.addRow("Move duration", self.spin_move_duration)

        self.timing_group = QGroupBox("Timing")
        timing_form = QFormLayout(self.timing_group)
        self.spin_pre = QSpinBox()
        self.spin_post = QSpinBox()
        self.spin_pre.setRange(0, 60_000)
        self.spin_pre.setSuffix(" ms")
        self.spin_post.setRange(0, 60_000)
        self.spin_post.setSuffix(" ms")
        timing_form.addRow("Pre-delay", self.spin_pre)
        timing_form.addRow("Post-delay", self.spin_post)

        action_row = QHBoxLayout()
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("DangerButton")
        action_row.addWidget(self.btn_duplicate)
        action_row.addWidget(self.btn_delete)

        layout.addWidget(self.overview_group)
        layout.addWidget(self.placement_group)
        layout.addWidget(self.action_group)
        layout.addWidget(self.timing_group)
        layout.addLayout(action_row)
        layout.addStretch(1)

        self.combo_click.currentIndexChanged.connect(self._on_changed)
        self.combo_action.currentIndexChanged.connect(self._on_changed)
        self.spin_x.valueChanged.connect(self._on_changed)
        self.spin_y.valueChanged.connect(self._on_changed)
        self.spin_target_x.valueChanged.connect(self._on_changed)
        self.spin_target_y.valueChanged.connect(self._on_changed)
        self.spin_hold.valueChanged.connect(self._on_changed)
        self.spin_drag_duration.valueChanged.connect(self._on_changed)
        self.spin_move_duration.valueChanged.connect(self._on_changed)
        self.spin_pre.valueChanged.connect(self._on_changed)
        self.spin_post.valueChanged.connect(self._on_changed)
        self.btn_duplicate.clicked.connect(self._duplicate_current)
        self.btn_delete.clicked.connect(self._delete_current)

    def load_node(self, node: ActionNode) -> None:
        self.current_node = node
        self._set_editor_enabled(True)

        self._updating = True
        self.lbl_id.setText(str(node.id))
        self.summary_label.setText(node.summary)
        self.source_label.setText(node.source.title())
        self.spin_x.setValue(node.x)
        self.spin_y.setValue(node.y)
        self.combo_action.setCurrentText(node.action_type)
        self.combo_click.setCurrentText(node.click_type)
        self.spin_target_x.setValue(node.target_x if node.target_x is not None else node.x + 120)
        self.spin_target_y.setValue(node.target_y if node.target_y is not None else node.y)
        self.spin_hold.setValue(node.hold_ms)
        self.spin_drag_duration.setValue(node.drag_duration_ms)
        self.spin_move_duration.setValue(node.move_duration_ms)
        self.spin_pre.setValue(node.pre_delay)
        self.spin_post.setValue(node.post_delay)
        self._toggle_action_fields(node.action_type)
        self._updating = False

    def clear(self) -> None:
        self.current_node = None
        self._updating = True
        self.lbl_id.setText("None")
        self.summary_label.setText("Select an action from the sequence list or overlay.")
        self.source_label.setText("Manual")
        self.spin_x.setValue(0)
        self.spin_y.setValue(0)
        self.spin_target_x.setValue(0)
        self.spin_target_y.setValue(0)
        self.spin_hold.setValue(config.DEFAULT_HOLD_MS)
        self.spin_drag_duration.setValue(config.DEFAULT_DRAG_DURATION_MS)
        self.spin_move_duration.setValue(config.DEFAULT_MOVE_DURATION_MS)
        self.spin_pre.setValue(config.DEFAULT_PRE_DELAY)
        self.spin_post.setValue(config.DEFAULT_POST_DELAY)
        self._toggle_action_fields("Click")
        self._set_editor_enabled(False)
        self._updating = False

    def _on_changed(self) -> None:
        if self.current_node is None or self._updating:
            return

        self.current_node.x = self.spin_x.value()
        self.current_node.y = self.spin_y.value()
        self.current_node.action_type = self.combo_action.currentText()
        self.current_node.click_type = self.combo_click.currentText()
        self.current_node.target_x = self.spin_target_x.value()
        self.current_node.target_y = self.spin_target_y.value()
        self.current_node.hold_ms = self.spin_hold.value()
        self.current_node.drag_duration_ms = self.spin_drag_duration.value()
        self.current_node.move_duration_ms = self.spin_move_duration.value()
        self.current_node.pre_delay = self.spin_pre.value()
        self.current_node.post_delay = self.spin_post.value()
        if self.current_node.action_type == "Drag":
            self.current_node.ensure_drag_target()
        self._toggle_action_fields(self.current_node.action_type)
        self.summary_label.setText(self.current_node.summary)
        self.node_updated.emit(self.current_node)

    def _toggle_action_fields(self, action_type: str) -> None:
        is_drag = action_type == "Drag"
        is_long_press = action_type == "Long Press"
        is_move = action_type == "Move"
        has_click_type = action_type in {"Click", "Long Press", "Drag"}

        self.spin_target_x.setEnabled(is_drag)
        self.spin_target_y.setEnabled(is_drag)
        self.spin_drag_duration.setEnabled(is_drag)
        self.spin_hold.setEnabled(is_long_press)
        self.spin_move_duration.setEnabled(is_move)
        self.combo_click.setEnabled(has_click_type)

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self.placement_group,
            self.action_group,
            self.timing_group,
            self.btn_duplicate,
            self.btn_delete,
        ):
            widget.setEnabled(enabled)
        self.overview_group.setEnabled(True)

    def _duplicate_current(self) -> None:
        if self.current_node is not None:
            self.duplicate_requested.emit(self.current_node.id)

    def _delete_current(self) -> None:
        if self.current_node is not None:
            self.delete_requested.emit(self.current_node.id)
