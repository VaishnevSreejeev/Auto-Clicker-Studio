"""Mouse recording service that converts live activity into action nodes."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from pynput import mouse
from PyQt6.QtCore import QObject, pyqtSignal

import config
from models import ActionNode


@dataclass
class RecordingOptions:
    """Options that control how live recording is converted into nodes."""

    append_to_profile: bool = False
    capture_moves: bool = True


@dataclass
class RecordingResult:
    nodes: list[ActionNode]
    options: RecordingOptions


class MouseRecorder(QObject):
    """Captures mouse activity and emits recorded automation nodes."""

    started = pyqtSignal()
    finished = pyqtSignal(object)
    status_changed = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._lock = threading.Lock()
        self._listener: mouse.Listener | None = None
        self._recording = False
        self._options = RecordingOptions()
        self._nodes: list[ActionNode] = []
        self._active_press: dict[mouse.Button, dict[str, object]] = {}
        self._pending_move: dict[str, object] | None = None
        self._last_action_end_ts = 0.0
        self._last_emitted_position: tuple[int, int] | None = None
        self._last_click_info: dict[str, object] | None = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._recording

    def start(self, options: RecordingOptions | None = None) -> bool:
        with self._lock:
            if self._recording:
                return False

            self._recording = True
            self._options = options or RecordingOptions()
            self._nodes = []
            self._active_press = {}
            self._pending_move = None
            self._last_click_info = None
            self._last_action_end_ts = time.monotonic()
            self._last_emitted_position = self._current_pointer_position()

        try:
            self._listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click)
            self._listener.start()
        except Exception as exc:
            with self._lock:
                self._recording = False
                self._listener = None
            self.error.emit(f"Mouse recording is unavailable: {exc}")
            return False

        self.started.emit()
        self.status_changed.emit("Recording mouse activity")
        return True

    def stop(self) -> bool:
        listener: mouse.Listener | None = None
        result: RecordingResult | None = None

        with self._lock:
            if not self._recording:
                return False

            self._recording = False
            self._flush_pending_move(force=True)
            listener = self._listener
            self._listener = None
            result = RecordingResult(
                nodes=[ActionNode.from_dict(node.to_dict()) for node in self._nodes],
                options=self._options,
            )

        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

        self.status_changed.emit(f"Recorded {len(result.nodes)} step(s)")
        self.finished.emit(result)
        return True

    def _on_move(self, x: int, y: int) -> None:
        self._handle_move(x, y)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        self._handle_click(x, y, button, pressed)

    def _handle_move(self, x: int, y: int) -> None:
        now = time.monotonic()
        x, y = config.DESKTOP_BOUNDS.clamp(x, y, border=config.SAFETY_BORDER)

        with self._lock:
            if not self._recording:
                return

            if self._active_press:
                for press in self._active_press.values():
                    press["last_pos"] = (x, y)
                    if self._distance(press["start"], (x, y)) >= config.RECORDING_DRAG_THRESHOLD:
                        press["moved"] = True
                return

            if not self._options.capture_moves:
                return

            if self._pending_move is None:
                self._pending_move = {
                    "start": self._last_emitted_position or (x, y),
                    "current": (x, y),
                    "start_ts": now,
                    "last_ts": now,
                }
                return

            self._pending_move["current"] = (x, y)
            self._pending_move["last_ts"] = now

    def _handle_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        now = time.monotonic()
        x, y = config.DESKTOP_BOUNDS.clamp(x, y, border=config.SAFETY_BORDER)

        with self._lock:
            if not self._recording:
                return

            if pressed:
                self._flush_pending_move(force=False)
                self._active_press[button] = {
                    "start": (x, y),
                    "press_ts": now,
                    "last_pos": (x, y),
                    "moved": False,
                }
                return

            press = self._active_press.pop(button, None)
            if press is None:
                return

            start = press["start"]
            end = (x, y)
            press_ts = float(press["press_ts"])
            moved = bool(press["moved"]) or self._distance(start, end) >= config.RECORDING_DRAG_THRESHOLD
            click_type = self._button_to_click_type(button)

            if moved:
                node = ActionNode(
                    id=len(self._nodes) + 1,
                    x=start[0],
                    y=start[1],
                    click_type=click_type,
                    action_type="Drag",
                    target_x=end[0],
                    target_y=end[1],
                    drag_duration_ms=max(50, int((now - press_ts) * 1000)),
                    post_delay=0,
                    source="recorded",
                )
                self._append_node(node, press_ts, now)
                self._last_click_info = None
            else:
                duration_ms = max(0, int((now - press_ts) * 1000))
                if duration_ms >= config.RECORDING_LONG_PRESS_MS:
                    node = ActionNode(
                        id=len(self._nodes) + 1,
                        x=end[0],
                        y=end[1],
                        click_type=click_type,
                        action_type="Long Press",
                        hold_ms=max(50, duration_ms),
                        post_delay=0,
                        source="recorded",
                    )
                    self._append_node(node, press_ts, now)
                    self._last_click_info = None
                elif self._should_merge_double_click(click_type, end, now):
                    previous = self._nodes[-1]
                    previous.click_type = "Double"
                    previous.post_delay = 0
                    self._last_action_end_ts = now
                    self._last_click_info = {
                        "click_type": click_type,
                        "position": end,
                        "time": now,
                    }
                else:
                    node = ActionNode(
                        id=len(self._nodes) + 1,
                        x=end[0],
                        y=end[1],
                        click_type=click_type,
                        action_type="Click",
                        post_delay=0,
                        source="recorded",
                    )
                    self._append_node(node, press_ts, now)
                    self._last_click_info = {
                        "click_type": click_type,
                        "position": end,
                        "time": now,
                    }

            self._last_emitted_position = end
            self._pending_move = None

    def _flush_pending_move(self, force: bool) -> None:
        if not self._options.capture_moves or self._pending_move is None:
            return

        start = self._pending_move["start"]
        end = self._pending_move["current"]
        if self._distance(start, end) < config.RECORDING_MOVE_THRESHOLD:
            self._pending_move = None
            return

        start_ts = max(self._last_action_end_ts, float(self._pending_move["start_ts"]))
        end_ts = float(self._pending_move["last_ts"])
        duration_ms = max(
            config.RECORDING_MIN_MOVE_DURATION_MS,
            int((end_ts - start_ts) * 1000),
        )

        node = ActionNode(
            id=len(self._nodes) + 1,
            x=end[0],
            y=end[1],
            action_type="Move",
            move_duration_ms=duration_ms,
            post_delay=0,
            source="recorded",
        )
        self._append_node(node, start_ts, end_ts)
        self._last_emitted_position = end
        self._pending_move = None
        self._last_click_info = None

    def _append_node(self, node: ActionNode, event_start_ts: float, event_end_ts: float) -> None:
        if self._nodes:
            node.pre_delay = max(0, int((event_start_ts - self._last_action_end_ts) * 1000))
        else:
            node.pre_delay = 0
        self._nodes.append(node)
        self._last_action_end_ts = event_end_ts
        self.status_changed.emit(f"Recording mouse activity ({len(self._nodes)} step(s))")

    def _should_merge_double_click(self, click_type: str, position: tuple[int, int], now: float) -> bool:
        if not self._nodes or self._last_click_info is None:
            return False
        if self._nodes[-1].action_type != "Click" or self._nodes[-1].click_type == "Double":
            return False
        if click_type != "Left":
            return False

        return (
            self._last_click_info["click_type"] == click_type
            and self._distance(self._last_click_info["position"], position) <= config.RECORDING_DRAG_THRESHOLD
            and (now - float(self._last_click_info["time"])) * 1000 <= config.RECORDING_DOUBLE_CLICK_GAP_MS
        )

    @staticmethod
    def _distance(start: tuple[int, int], end: tuple[int, int]) -> float:
        return math.hypot(end[0] - start[0], end[1] - start[1])

    @staticmethod
    def _button_to_click_type(button: mouse.Button) -> str:
        if button == mouse.Button.right:
            return "Right"
        if button == mouse.Button.middle:
            return "Middle"
        return "Left"

    @staticmethod
    def _current_pointer_position() -> tuple[int, int]:
        try:
            x, y = mouse.Controller().position
        except Exception:
            x, y = config.DESKTOP_BOUNDS.center
        return config.DESKTOP_BOUNDS.clamp(x, y, border=config.SAFETY_BORDER)
