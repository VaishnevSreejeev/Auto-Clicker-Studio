"""Primary application window and workflow coordinator."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import config
from engine import ExecutionEngine
from hotkeys import HotkeyListener
from models import Profile
from recorder import MouseRecorder, RecordingOptions, RecordingResult
from ui.canvas import Canvas
from ui.overlay import OverlayWindow
from ui.sidebar import Sidebar


class MainWindow(QMainWindow):
    """Owns the UI, execution engine, recorder, and profile interactions."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(1040, 720)
        self.setMinimumSize(config.FULL_MIN_WIDTH, config.FULL_MIN_HEIGHT)
        self.setStyleSheet(config.STYLESHEET)

        self.canvas = Canvas()
        self.overlay = OverlayWindow(self.canvas)
        self.sidebar = Sidebar()
        self.engine = ExecutionEngine()
        self.recorder = MouseRecorder()
        self.hotkeys = HotkeyListener()

        self._selected_node_id: int | None = None
        self._syncing_profile = False
        self._run_had_error = False
        self._compact_mode = False
        self._expanded_geometry = None

        self._build_ui()
        self._connect_signals()
        self._refresh_profile_form()
        self._refresh_nodes()
        self._set_status_chip("Idle", "idle")
        self._sync_overlay_button()
        self._sync_record_button()
        self._refresh_state()
        self.hotkeys.start()
        self._log("Ready.")

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        full = QWidget()
        full_root = QVBoxLayout(full)
        full_root.setContentsMargins(16, 16, 16, 16)
        full_root.setSpacing(12)

        header = QFrame()
        header.setObjectName("HeaderBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)

        title_col = QVBoxLayout()
        title = QLabel(config.APP_NAME)
        title.setObjectName("AppTitle")
        subtitle = QLabel("Record mouse actions, refine them visually, and run them with safety controls.")
        subtitle.setObjectName("AppSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_layout.addLayout(title_col, 1)

        header_actions = QVBoxLayout()
        header_row = QHBoxLayout()
        self.status_chip = QLabel()
        self.btn_compact = QPushButton("Compact Strip")
        self.btn_compact.setObjectName("GhostButton")
        header_row.addWidget(self.status_chip)
        header_row.addWidget(self.btn_compact)
        header_actions.addLayout(header_row)
        self.mode_label = QLabel("Full workspace")
        self.mode_label.setObjectName("MetaText")
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        header_actions.addWidget(self.mode_label)
        header_layout.addLayout(header_actions)
        full_root.addWidget(header)

        bar = QFrame()
        bar.setObjectName("ControlBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(14, 12, 14, 12)
        bar_layout.setSpacing(8)
        self.btn_overlay = QPushButton("Show Overlay")
        self.btn_add = QPushButton("Add Action")
        self.btn_record = QPushButton(f"Record ({config.HOTKEY_RECORD})")
        self.btn_record.setObjectName("RecordButton")
        self.btn_start = QPushButton(f"Start ({config.HOTKEY_START})")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_pause = QPushButton(f"Pause ({config.HOTKEY_PAUSE})")
        self.btn_pause.setObjectName("PauseButton")
        self.btn_stop = QPushButton(f"Stop ({config.HOTKEY_STOP})")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_save = QPushButton("Save")
        self.btn_load = QPushButton("Load")
        for button in (
            self.btn_overlay,
            self.btn_add,
            self.btn_record,
            self.btn_start,
            self.btn_pause,
            self.btn_stop,
            self.btn_save,
            self.btn_load,
        ):
            bar_layout.addWidget(button)
        bar_layout.addStretch(1)
        hotkeys = QLabel(
            f"{config.HOTKEY_RECORD} record  {config.HOTKEY_START} start  "
            f"{config.HOTKEY_PAUSE} pause  {config.HOTKEY_STOP} stop"
        )
        hotkeys.setObjectName("SectionHint")
        bar_layout.addWidget(hotkeys)
        full_root.addWidget(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        full_root.addWidget(split, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        split.addWidget(left)

        automation = QGroupBox("Automation")
        automation_form = QFormLayout(automation)
        self.input_profile_name = QLineEdit()
        self.check_loop_forever = QCheckBox("Loop until stopped")
        self.spin_repeat_count = QSpinBox()
        self.spin_repeat_count.setRange(1, 9999)
        self.spin_cycle_delay = QSpinBox()
        self.spin_cycle_delay.setRange(0, 60_000)
        self.spin_cycle_delay.setSuffix(" ms")
        automation_form.addRow("Profile name", self.input_profile_name)
        automation_form.addRow("", self.check_loop_forever)
        automation_form.addRow("Repeat count", self.spin_repeat_count)
        automation_form.addRow("Cycle delay", self.spin_cycle_delay)
        left_layout.addWidget(automation)

        recording = QGroupBox("Recording")
        recording_layout = QVBoxLayout(recording)
        hint = QLabel("Record live mouse actions into the current profile.")
        hint.setObjectName("SectionHint")
        hint.setWordWrap(True)
        self.check_append_recording = QCheckBox("Append to current sequence")
        self.check_capture_moves = QCheckBox("Capture pointer movements")
        self.check_capture_moves.setChecked(True)
        self.recording_note = QLabel("Recording replaces the current sequence unless append is enabled.")
        self.recording_note.setObjectName("MetaText")
        self.recording_note.setWordWrap(True)
        recording_layout.addWidget(hint)
        recording_layout.addWidget(self.check_append_recording)
        recording_layout.addWidget(self.check_capture_moves)
        recording_layout.addWidget(self.recording_note)
        left_layout.addWidget(recording)

        sequence = QGroupBox("Sequence")
        sequence_layout = QVBoxLayout(sequence)
        self.step_count_label = QLabel("0 actions")
        self.step_count_label.setObjectName("MetaText")
        self.selection_label = QLabel("No action selected.")
        self.selection_label.setObjectName("MetaText")
        self.selection_label.setWordWrap(True)
        self.node_list = QListWidget()
        row = QHBoxLayout()
        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_down = QPushButton("Move Down")
        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("DangerButton")
        for button in (self.btn_move_up, self.btn_move_down, self.btn_duplicate, self.btn_delete):
            row.addWidget(button)
        sequence_layout.addWidget(self.step_count_label)
        sequence_layout.addWidget(self.selection_label)
        sequence_layout.addWidget(self.node_list, 1)
        sequence_layout.addLayout(row)
        left_layout.addWidget(sequence, 1)

        right = QSplitter(Qt.Orientation.Vertical)
        right.setChildrenCollapsible(False)
        right.addWidget(self.sidebar)
        log_group = QGroupBox("Activity")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 18, 12, 12)
        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        log_layout.addWidget(self.log_output)
        right.addWidget(log_group)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 1)
        split.addWidget(right)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 5)

        compact = QFrame()
        compact.setObjectName("CompactStrip")
        compact_layout = QVBoxLayout(compact)
        compact_layout.setContentsMargins(10, 12, 10, 12)
        compact_layout.setSpacing(10)
        self.btn_expand = QPushButton("Expand")
        self.btn_expand.setObjectName("GhostButton")
        compact_layout.addWidget(self.btn_expand)
        c_title = QLabel(config.APP_NAME)
        c_title.setObjectName("CompactTitle")
        c_title.setWordWrap(True)
        compact_layout.addWidget(c_title)
        self.compact_status_chip = QLabel()
        compact_layout.addWidget(self.compact_status_chip)
        self.compact_profile_label = QLabel("Default Profile")
        self.compact_profile_label.setObjectName("CompactMeta")
        self.compact_profile_label.setWordWrap(True)
        compact_layout.addWidget(self.compact_profile_label)
        self.compact_steps_label = QLabel("0 actions")
        self.compact_steps_label.setObjectName("CompactMeta")
        compact_layout.addWidget(self.compact_steps_label)
        self.compact_record = QPushButton("Record")
        self.compact_record.setObjectName("RecordButton")
        self.compact_overlay = QPushButton("Overlay")
        self.compact_add = QPushButton("Add")
        self.compact_start = QPushButton("Start")
        self.compact_start.setObjectName("PrimaryButton")
        self.compact_pause = QPushButton("Pause")
        self.compact_pause.setObjectName("PauseButton")
        self.compact_stop = QPushButton("Stop")
        self.compact_stop.setObjectName("DangerButton")
        for button in (
            self.compact_record,
            self.compact_overlay,
            self.compact_add,
            self.compact_start,
            self.compact_pause,
            self.compact_stop,
        ):
            compact_layout.addWidget(button)
        compact_layout.addStretch(1)
        c_hint = QLabel(
            f"{config.HOTKEY_RECORD} record\n{config.HOTKEY_START} start\n"
            f"{config.HOTKEY_PAUSE} pause\n{config.HOTKEY_STOP} stop"
        )
        c_hint.setObjectName("CompactMeta")
        c_hint.setWordWrap(True)
        compact_layout.addWidget(c_hint)

        self.stack.addWidget(full)
        self.stack.addWidget(compact)

        bounds = QLabel(
            f"Desktop bounds: {config.DESKTOP_BOUNDS.left},{config.DESKTOP_BOUNDS.top} "
            f"to {config.DESKTOP_BOUNDS.right},{config.DESKTOP_BOUNDS.bottom}"
        )
        bounds.setObjectName("MetaText")
        self.statusBar().showMessage("Ready")
        self.statusBar().addPermanentWidget(bounds)

    def _connect_signals(self) -> None:
        self.btn_overlay.clicked.connect(self._toggle_overlay)
        self.compact_overlay.clicked.connect(self._toggle_overlay)
        self.btn_add.clicked.connect(self._add_node)
        self.compact_add.clicked.connect(self._add_node)
        self.btn_record.clicked.connect(self._toggle_recording)
        self.compact_record.clicked.connect(self._toggle_recording)
        self.btn_start.clicked.connect(self._start_execution)
        self.compact_start.clicked.connect(self._start_execution)
        self.btn_pause.clicked.connect(self._toggle_pause)
        self.compact_pause.clicked.connect(self._toggle_pause)
        self.btn_stop.clicked.connect(self._handle_stop)
        self.compact_stop.clicked.connect(self._handle_stop)
        self.btn_save.clicked.connect(self._save_profile)
        self.btn_load.clicked.connect(self._load_profile)
        self.btn_move_up.clicked.connect(lambda: self._move_selected(-1))
        self.btn_move_down.clicked.connect(lambda: self._move_selected(1))
        self.btn_duplicate.clicked.connect(self._duplicate_selected)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_compact.clicked.connect(lambda: self._set_compact_mode(not self._compact_mode))
        self.btn_expand.clicked.connect(lambda: self._set_compact_mode(False))

        self.input_profile_name.textChanged.connect(self._apply_profile_form)
        self.check_loop_forever.toggled.connect(self._apply_profile_form)
        self.spin_repeat_count.valueChanged.connect(self._apply_profile_form)
        self.spin_cycle_delay.valueChanged.connect(self._apply_profile_form)
        self.node_list.currentItemChanged.connect(self._on_list_selection_changed)

        self.canvas.node_selected.connect(self._on_canvas_selected)
        self.canvas.selection_cleared.connect(self._clear_selection)
        self.canvas.profile_changed.connect(self._refresh_nodes)
        self.sidebar.node_updated.connect(self._on_sidebar_updated)
        self.sidebar.duplicate_requested.connect(self._duplicate_node)
        self.sidebar.delete_requested.connect(self._delete_node)

        self.engine.started.connect(self._on_execution_started)
        self.engine.finished.connect(self._on_execution_finished)
        self.engine.paused_changed.connect(self._on_paused_changed)
        self.engine.node_executed.connect(self._on_node_executed)
        self.engine.status_changed.connect(self._on_runtime_status)
        self.engine.error.connect(self._on_engine_error)

        self.recorder.started.connect(self._on_recording_started)
        self.recorder.finished.connect(self._on_recording_finished)
        self.recorder.status_changed.connect(self._on_runtime_status)
        self.recorder.error.connect(self._on_recorder_error)

        self.hotkeys.record_requested.connect(self._toggle_recording)
        self.hotkeys.start_requested.connect(self._start_execution)
        self.hotkeys.pause_requested.connect(self._toggle_pause)
        self.hotkeys.stop_requested.connect(self._handle_stop)
        self.hotkeys.error.connect(self._on_hotkey_error)

    def _toggle_overlay(self) -> None:
        if self.recorder.is_recording:
            return
        self.overlay.toggle_visibility()
        self._sync_overlay_button()

    def _sync_overlay_button(self) -> None:
        showing = self.overlay.isVisible()
        self.btn_overlay.setText("Hide Overlay" if showing else "Show Overlay")
        self.compact_overlay.setText("Hide Overlay" if showing else "Overlay")

    def _toggle_recording(self) -> None:
        if self.engine.is_running:
            return
        if self.recorder.is_recording:
            self.recorder.stop()
            return
        if self.overlay.isVisible():
            self.overlay.hide()
            self._sync_overlay_button()
        options = RecordingOptions(
            append_to_profile=self.check_append_recording.isChecked(),
            capture_moves=self.check_capture_moves.isChecked(),
        )
        if self.recorder.start(options):
            self._refresh_state()

    def _sync_record_button(self) -> None:
        recording = self.recorder.is_recording
        self.btn_record.setText(f"Stop Recording ({config.HOTKEY_RECORD})" if recording else f"Record ({config.HOTKEY_RECORD})")
        self.compact_record.setText("Stop Record" if recording else "Record")
        for button in (self.btn_record, self.compact_record):
            button.setProperty("recording", "true" if recording else "false")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _add_node(self) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        if not self.overlay.isVisible():
            self.overlay.show()
            self._sync_overlay_button()
        node = self.canvas.add_node()
        self._refresh_nodes(node.id)
        self._log(f"Added action at {node.x},{node.y}.")

    def _start_execution(self) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        self._apply_profile_form()
        if not self.canvas.profile.nodes:
            QMessageBox.warning(self, "No Actions", "Add at least one action before starting.")
            return
        self._run_had_error = False
        if self.overlay.isVisible():
            self.overlay.set_input_transparent(True)
        if self.engine.start(self.canvas.profile):
            self._refresh_state()

    def _toggle_pause(self) -> None:
        if self.engine.is_running and not self.recorder.is_recording:
            self.engine.toggle_pause()

    def _handle_stop(self) -> None:
        if self.recorder.is_recording:
            self.recorder.stop()
            return
        self.overlay.set_input_transparent(False)
        if self.engine.stop():
            self._log("Stopping execution.")

    def _save_profile(self) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        self._apply_profile_form()
        config.DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        default_path = config.DEFAULT_PROFILE_DIR / f"{(self.canvas.profile.name or 'profile').replace(' ', '_').lower()}.json"
        path, _ = QFileDialog.getSaveFileName(self, "Save Profile", str(default_path), "JSON Files (*.json)")
        if path:
            self.canvas.profile.save_to_file(path)
            self._log(f"Saved profile to {path}.")

    def _load_profile(self) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        config.DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Load Profile", str(config.DEFAULT_PROFILE_DIR), "JSON Files (*.json)")
        if not path:
            return
        try:
            profile = Profile.load_from_file(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Failed", f"Failed to load profile:\n{exc}")
            return
        self.canvas.load_profile(profile)
        self._refresh_profile_form()
        self._refresh_nodes()
        self._clear_selection()
        self._log(f"Loaded profile from {path}.")

    def _move_selected(self, direction: int) -> None:
        if self._selected_node_id is not None and not (self.engine.is_running or self.recorder.is_recording):
            if self.canvas.move_node(self._selected_node_id, direction):
                self._refresh_nodes(self._selected_node_id)

    def _duplicate_selected(self) -> None:
        if self._selected_node_id is not None:
            self._duplicate_node(self._selected_node_id)

    def _delete_selected(self) -> None:
        if self._selected_node_id is not None:
            self._delete_node(self._selected_node_id)

    def _duplicate_node(self, node_id: int) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        node = self.canvas.duplicate_node(node_id)
        if node is not None:
            self._refresh_nodes(node.id)
            self._log(f"Duplicated action ID {node_id}.")

    def _delete_node(self, node_id: int) -> None:
        if self.engine.is_running or self.recorder.is_recording:
            return
        if self.canvas.delete_node(node_id):
            self._refresh_nodes(self._selected_node_id)
            self._log(f"Deleted action ID {node_id}.")

    def _refresh_nodes(self, preferred_node_id: int | None = None) -> None:
        preferred_node_id = self._selected_node_id if preferred_node_id is None else preferred_node_id
        self.node_list.blockSignals(True)
        self.node_list.clear()
        for index, node in enumerate(self.canvas.profile.nodes, start=1):
            item = QListWidgetItem(f"{index:02d}. {node.summary}")
            item.setData(Qt.ItemDataRole.UserRole, node.id)
            self.node_list.addItem(item)
            if node.id == preferred_node_id:
                self.node_list.setCurrentItem(item)
        self.node_list.blockSignals(False)
        if not self.canvas.profile.nodes:
            self._selected_node_id = None
        self._refresh_labels()
        self._refresh_state()

    def _refresh_profile_form(self) -> None:
        self._syncing_profile = True
        self.input_profile_name.setText(self.canvas.profile.name)
        self.check_loop_forever.setChecked(self.canvas.profile.settings.loop_forever)
        self.spin_repeat_count.setValue(self.canvas.profile.settings.repeat_count)
        self.spin_cycle_delay.setValue(self.canvas.profile.settings.cycle_delay)
        self.spin_repeat_count.setEnabled(not self.canvas.profile.settings.loop_forever)
        self._syncing_profile = False
        self._refresh_labels()

    def _apply_profile_form(self) -> None:
        if self._syncing_profile:
            return
        self.canvas.profile.name = self.input_profile_name.text().strip() or "Default Profile"
        self.canvas.profile.settings.loop_forever = self.check_loop_forever.isChecked()
        self.canvas.profile.settings.repeat_count = self.spin_repeat_count.value()
        self.canvas.profile.settings.cycle_delay = self.spin_cycle_delay.value()
        self.spin_repeat_count.setEnabled(not self.check_loop_forever.isChecked())
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        count = len(self.canvas.profile.nodes)
        text = f"{count} action{'s' if count != 1 else ''}"
        self.step_count_label.setText(text)
        self.compact_steps_label.setText(text)
        self.compact_profile_label.setText(self.canvas.profile.name)
        node = self.canvas.profile.get_node(self._selected_node_id) if self._selected_node_id else None
        self.selection_label.setText(node.summary if node else "No action selected.")

    def _refresh_state(self) -> None:
        running = self.engine.is_running
        recording = self.recorder.is_recording
        editable = not running and not recording
        has_actions = bool(self.canvas.profile.nodes)
        has_selection = self._selected_node_id is not None

        self.btn_overlay.setEnabled(editable)
        self.compact_overlay.setEnabled(editable)
        self.btn_add.setEnabled(editable)
        self.compact_add.setEnabled(editable)
        self.btn_start.setEnabled(editable and has_actions)
        self.compact_start.setEnabled(editable and has_actions)
        self.btn_pause.setEnabled(running)
        self.compact_pause.setEnabled(running)
        self.btn_stop.setEnabled(running or recording)
        self.compact_stop.setEnabled(running or recording)
        self.btn_save.setEnabled(editable)
        self.btn_load.setEnabled(editable)
        self.btn_record.setEnabled(not running)
        self.compact_record.setEnabled(not running)

        self.node_list.setEnabled(editable)
        self.sidebar.setEnabled(editable)
        self.input_profile_name.setEnabled(editable)
        self.check_loop_forever.setEnabled(editable)
        self.spin_repeat_count.setEnabled(editable and not self.check_loop_forever.isChecked())
        self.spin_cycle_delay.setEnabled(editable)
        self.check_append_recording.setEnabled(editable)
        self.check_capture_moves.setEnabled(editable)
        self.btn_move_up.setEnabled(editable and has_selection)
        self.btn_move_down.setEnabled(editable and has_selection)
        self.btn_duplicate.setEnabled(editable and has_selection)
        self.btn_delete.setEnabled(editable and has_selection)

        self._sync_record_button()

    def _on_list_selection_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        del previous
        if current is None:
            self.canvas.clear_selection()
            return
        self._selected_node_id = current.data(Qt.ItemDataRole.UserRole)
        self.canvas.select_node(self._selected_node_id)
        self._refresh_labels()
        self._refresh_state()

    def _on_canvas_selected(self, node) -> None:
        if node is None:
            return
        self._selected_node_id = node.id
        self.sidebar.load_node(node)
        self.node_list.blockSignals(True)
        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == node.id:
                self.node_list.setCurrentItem(item)
                break
        self.node_list.blockSignals(False)
        self._refresh_labels()
        self._refresh_state()

    def _on_sidebar_updated(self, node) -> None:
        self.canvas.update_node(node)
        self._refresh_nodes(node.id)

    def _clear_selection(self) -> None:
        self._selected_node_id = None
        self.sidebar.clear()
        self.node_list.blockSignals(True)
        self.node_list.clearSelection()
        self.node_list.blockSignals(False)
        self._refresh_labels()
        self._refresh_state()

    def _on_execution_started(self) -> None:
        self._set_status_chip("Running", "running")
        self._log("Execution started.")
        self._refresh_state()

    def _on_execution_finished(self) -> None:
        self.overlay.set_input_transparent(False)
        self.canvas.set_active_node(None)
        self._set_status_chip("Error" if self._run_had_error else "Idle", "error" if self._run_had_error else "idle")
        self._log("Execution finished.")
        self._refresh_state()

    def _on_paused_changed(self, paused: bool) -> None:
        self.btn_pause.setText("Resume (F9)" if paused else f"Pause ({config.HOTKEY_PAUSE})")
        self.compact_pause.setText("Resume" if paused else "Pause")
        self._set_status_chip("Paused" if paused else "Running", "paused" if paused else "running")
        self._refresh_state()

    def _on_node_executed(self, node_id: int) -> None:
        self.canvas.set_active_node(node_id)
        self.statusBar().showMessage(f"Executing action ID {node_id}")

    def _on_recording_started(self) -> None:
        self._set_status_chip("Recording", "recording")
        self._log("Recording started.")
        self._refresh_state()

    def _on_recording_finished(self, result: RecordingResult) -> None:
        self._sync_record_button()
        if result.nodes:
            applied = self.canvas.profile.append_nodes(result.nodes) if result.options.append_to_profile else self.canvas.profile.replace_nodes(result.nodes)
            self.canvas.load_profile(self.canvas.profile)
            if applied:
                self.canvas.select_node(applied[0].id)
            self._refresh_nodes(applied[0].id if applied else None)
            mode = "appended to" if result.options.append_to_profile else "replaced"
            self._log(f"Recording saved {len(applied)} action(s) and {mode} the current sequence.")
        else:
            self._log("Recording stopped with no captured actions.")
        self._set_status_chip("Idle", "idle")
        self._refresh_state()

    def _on_runtime_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_engine_error(self, message: str) -> None:
        self._run_had_error = True
        self._set_status_chip("Error", "error")
        self._log(message)
        QMessageBox.warning(self, "Execution Error", message)
        self._refresh_state()

    def _on_recorder_error(self, message: str) -> None:
        self._set_status_chip("Error", "error")
        self._log(message)
        QMessageBox.warning(self, "Recording Error", message)
        self._refresh_state()

    def _on_hotkey_error(self, message: str) -> None:
        self._log(message)

    def _set_status_chip(self, text: str, tone: str) -> None:
        tones = {
            "idle": ("#1f3648", "#dcf1ff"),
            "running": ("#1b4a40", "#b8fff2"),
            "paused": ("#574010", "#ffe9af"),
            "recording": ("#3d4fa6", "#eaf0ff"),
            "error": ("#59251c", "#ffc4b7"),
        }
        background, foreground = tones.get(tone, tones["idle"])
        style = (
            f"background-color: {background}; color: {foreground}; "
            "border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 14px; "
            "padding: 8px 14px; font-weight: 700;"
        )
        self.status_chip.setText(text)
        self.status_chip.setStyleSheet(style)
        self.compact_status_chip.setText(text)
        self.compact_status_chip.setStyleSheet(style)

    def _set_compact_mode(self, compact: bool) -> None:
        if compact == self._compact_mode:
            return
        if self.recorder.is_recording and not compact:
            return
        if compact:
            self._expanded_geometry = self.geometry()
            self._compact_mode = True
            self.stack.setCurrentIndex(1)
            self.statusBar().setVisible(False)
            self.mode_label.setText("Compact strip")
            self.btn_compact.setText("Expand")
            self.setMinimumSize(config.COMPACT_STRIP_WIDTH, config.COMPACT_STRIP_MIN_HEIGHT)
            self.setMaximumWidth(config.COMPACT_STRIP_WIDTH)
            screen = self.screen().availableGeometry() if self.screen() else self.geometry()
            height = max(config.COMPACT_STRIP_MIN_HEIGHT, min(self.height(), screen.height() - 40))
            x = max(screen.left(), min(self._expanded_geometry.x() + self._expanded_geometry.width() - config.COMPACT_STRIP_WIDTH, screen.right() - config.COMPACT_STRIP_WIDTH))
            y = max(screen.top(), min(self._expanded_geometry.y(), screen.bottom() - height))
            self.setGeometry(x, y, config.COMPACT_STRIP_WIDTH, height)
            self.showNormal()
            return
        self._compact_mode = False
        self.stack.setCurrentIndex(0)
        self.statusBar().setVisible(True)
        self.mode_label.setText("Full workspace")
        self.btn_compact.setText("Compact Strip")
        self.setMaximumWidth(16777215)
        self.setMinimumSize(config.FULL_MIN_WIDTH, config.FULL_MIN_HEIGHT)
        if self._expanded_geometry is not None:
            self.setGeometry(self._expanded_geometry)
        self.showNormal()

    def _log(self, message: str) -> None:
        self.log_output.appendPlainText(f"[{QTime.currentTime().toString('HH:mm:ss')}] {message}")

    def showMinimized(self) -> None:
        self._set_compact_mode(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.hotkeys.stop()
        self.recorder.stop()
        self.engine.stop()
        self.overlay.close()
        event.accept()
