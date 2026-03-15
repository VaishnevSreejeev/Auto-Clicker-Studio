from __future__ import annotations

from pynput import keyboard
from PyQt6.QtCore import QObject, pyqtSignal


class HotkeyListener(QObject):
    record_requested = pyqtSignal()
    start_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        if self.listener is not None:
            return

        try:
            self.listener = keyboard.GlobalHotKeys(
                {
                    "<f8>": self._on_record,
                    "<f10>": self._on_start,
                    "<f9>": self._on_pause,
                    "<esc>": self._on_stop,
                }
            )
            self.listener.start()
        except Exception as exc:
            self.listener = None
            self.error.emit(f"Global hotkeys are unavailable: {exc}")

    def stop(self) -> None:
        if self.listener is None:
            return

        try:
            self.listener.stop()
        finally:
            self.listener = None

    def _on_record(self) -> None:
        self.record_requested.emit()

    def _on_start(self) -> None:
        self.start_requested.emit()

    def _on_pause(self) -> None:
        self.pause_requested.emit()

    def _on_stop(self) -> None:
        self.stop_requested.emit()
