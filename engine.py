"""Execution engine for replaying automation profiles safely."""

from __future__ import annotations

import threading
import time

import pyautogui
from PyQt6.QtCore import QObject, pyqtSignal

from config import DESKTOP_BOUNDS, SAFETY_BORDER
from models import ActionNode, Profile


class ExecutionEngine(QObject):
    """Runs a snapshot of the current profile in a worker thread."""

    started = pyqtSignal()
    finished = pyqtSignal()
    paused_changed = pyqtSignal(bool)
    node_executed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pause_gate = threading.Event()
        self._pause_gate.set()
        self._thread: threading.Thread | None = None
        self._running = False
        self._paused = False
        self.profile: Profile | None = None

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            return self._running

    @property
    def is_paused(self) -> bool:
        with self._state_lock:
            return self._paused

    def start(self, profile: Profile) -> bool:
        snapshot = profile.snapshot()
        if not snapshot.nodes:
            self.error.emit("Add at least one step before starting.")
            return False

        with self._state_lock:
            if self._running:
                return False

            self.profile = snapshot
            self._running = True
            self._paused = False
            self._stop_event.clear()
            self._pause_gate.set()
            self._thread = threading.Thread(target=self._run_loop, name="auto-clicker-engine", daemon=True)
            self._thread.start()

        self.started.emit()
        self.status_changed.emit("Running")
        return True

    def stop(self) -> bool:
        with self._state_lock:
            was_running = self._running
            self._stop_event.set()
            self._paused = False
            self._pause_gate.set()

        if was_running:
            self.status_changed.emit("Stopping...")
            self.paused_changed.emit(False)
        return was_running

    def toggle_pause(self) -> bool:
        with self._state_lock:
            if not self._running:
                return False

            self._paused = not self._paused
            paused = self._paused

        if paused:
            self._pause_gate.clear()
            self.status_changed.emit("Paused")
        else:
            self._pause_gate.set()
            self.status_changed.emit("Running")

        self.paused_changed.emit(paused)
        return paused

    def _run_loop(self) -> None:
        try:
            assert self.profile is not None
            settings = self.profile.settings
            cycle = 0

            while not self._stop_event.is_set():
                cycle += 1
                self.status_changed.emit(f"Running cycle {cycle}")

                for node in self.profile.nodes:
                    if not self._wait_until_resumed():
                        return
                    if not self._sleep_ms(node.pre_delay):
                        return
                    self._execute_node(node)
                    self.node_executed.emit(node.id)
                    if not self._sleep_ms(node.post_delay):
                        return

                if not settings.loop_forever and cycle >= settings.repeat_count:
                    break

                if settings.cycle_delay and not self._sleep_ms(settings.cycle_delay):
                    return

            self.status_changed.emit("Stopped")
        except pyautogui.FailSafeException:
            self.error.emit("PyAutoGUI failsafe triggered. Move the cursor away from the screen corner and start again.")
        except Exception as exc:
            self.error.emit(f"Execution error: {exc}")
        finally:
            with self._state_lock:
                self._running = False
                self._paused = False
                self.profile = None
                self._thread = None
                self._stop_event.set()
                self._pause_gate.set()

            self.paused_changed.emit(False)
            self.finished.emit()

    def _wait_until_resumed(self) -> bool:
        while not self._stop_event.is_set():
            if self._pause_gate.wait(timeout=0.1):
                return True
        return False

    def _sleep_ms(self, duration_ms: int) -> bool:
        remaining = max(0, int(duration_ms)) / 1000.0
        while remaining > 0:
            if self._stop_event.is_set():
                return False
            if not self._pause_gate.wait(timeout=0.1):
                continue

            sleep_slice = min(0.05, remaining)
            started = time.monotonic()
            time.sleep(sleep_slice)
            remaining -= max(0.0, time.monotonic() - started)
        return True

    def _execute_node(self, node: ActionNode) -> None:
        safety_issue = self._validate_node(node)
        if safety_issue:
            self.status_changed.emit(f"Skipped step {node.id}: {safety_issue}")
            return

        if node.action_type == "Move":
            pyautogui.moveTo(node.x, node.y, duration=max(0.0, node.move_duration_ms / 1000.0))
            return

        if node.action_type == "Click":
            button = self._normal_button_name(node.click_type)
            if node.click_type == "Double":
                pyautogui.click(x=node.x, y=node.y, clicks=2, interval=0.12, button="left")
            else:
                pyautogui.click(x=node.x, y=node.y, button=button)
            return

        if node.action_type == "Long Press":
            button = self._normal_button_name(node.click_type)
            pyautogui.mouseDown(x=node.x, y=node.y, button=button)
            try:
                if not self._sleep_ms(node.hold_ms):
                    return
            finally:
                pyautogui.mouseUp(x=node.x, y=node.y, button=button)
            return

        if node.action_type == "Drag" and node.target_x is not None and node.target_y is not None:
            button = self._normal_button_name(node.click_type)
            pyautogui.moveTo(node.x, node.y)
            pyautogui.dragTo(
                node.target_x,
                node.target_y,
                duration=max(0.05, node.drag_duration_ms / 1000.0),
                button=button,
            )

    def _validate_node(self, node: ActionNode) -> str | None:
        if not self._is_safe_point(node.x, node.y):
            return f"source point {node.x},{node.y} is outside the safe desktop area"
        if node.action_type == "Drag":
            if node.target_x is None or node.target_y is None:
                return "drag target is missing"
            if not self._is_safe_point(node.target_x, node.target_y):
                return f"drag target {node.target_x},{node.target_y} is outside the safe desktop area"
        return None

    def _is_safe_point(self, x: int, y: int) -> bool:
        left = DESKTOP_BOUNDS.left + SAFETY_BORDER
        top = DESKTOP_BOUNDS.top + SAFETY_BORDER
        right = DESKTOP_BOUNDS.right - SAFETY_BORDER
        bottom = DESKTOP_BOUNDS.bottom - SAFETY_BORDER
        return left <= x < right and top <= y < bottom

    @staticmethod
    def _normal_button_name(click_type: str) -> str:
        if click_type == "Right":
            return "right"
        if click_type == "Middle":
            return "middle"
        return "left"
