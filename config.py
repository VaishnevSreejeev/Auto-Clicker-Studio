"""Application-wide constants, desktop bounds, and stylesheet definitions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyautogui
from screeninfo import get_monitors

APP_NAME = "Auto Clicker Studio"
APP_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_DIR = APP_DIR / "profiles"

SAFETY_BORDER = 6
DEFAULT_PRE_DELAY = 100
DEFAULT_POST_DELAY = 100
DEFAULT_HOLD_MS = 700
DEFAULT_DRAG_DURATION_MS = 450
DEFAULT_MOVE_DURATION_MS = 250
DEFAULT_REPEAT_COUNT = 1
DEFAULT_CYCLE_DELAY = 250

FULL_MIN_WIDTH = 920
FULL_MIN_HEIGHT = 640
COMPACT_STRIP_WIDTH = 156
COMPACT_STRIP_MIN_HEIGHT = 470

HOTKEY_RECORD = "F8"
HOTKEY_PAUSE = "F9"
HOTKEY_START = "F10"
HOTKEY_STOP = "Esc"

RECORDING_LONG_PRESS_MS = 450
RECORDING_DOUBLE_CLICK_GAP_MS = 320
RECORDING_DRAG_THRESHOLD = 14
RECORDING_MOVE_THRESHOLD = 24
RECORDING_MIN_MOVE_DURATION_MS = 75

pyautogui.PAUSE = 0.05
pyautogui.FAILSAFE = True


@dataclass(frozen=True)
class DesktopBounds:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.left + (self.width // 2), self.top + (self.height // 2))

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def clamp(self, x: int, y: int, border: int = 0) -> tuple[int, int]:
        if self.width <= (border * 2) or self.height <= (border * 2):
            return x, y

        clamped_x = min(max(x, self.left + border), self.right - border - 1)
        clamped_y = min(max(y, self.top + border), self.bottom - border - 1)
        return clamped_x, clamped_y


def load_desktop_bounds() -> DesktopBounds:
    try:
        monitors = [monitor for monitor in get_monitors() if monitor.width and monitor.height]
        if monitors:
            left = min(monitor.x for monitor in monitors)
            top = min(monitor.y for monitor in monitors)
            right = max(monitor.x + monitor.width for monitor in monitors)
            bottom = max(monitor.y + monitor.height for monitor in monitors)
            return DesktopBounds(left, top, right - left, bottom - top)
    except Exception:
        pass

    width, height = pyautogui.size()
    return DesktopBounds(0, 0, width, height)


DESKTOP_BOUNDS = load_desktop_bounds()

STYLESHEET = """
QMainWindow {
    background-color: #0f1620;
    color: #f8fbff;
    font-family: "Segoe UI Variable Text", "Segoe UI", "Tahoma";
}
QWidget {
    color: #f8fbff;
    font-size: 13px;
}
QFrame#HeaderBar,
QFrame#ControlBar,
QFrame#CompactStrip,
QFrame#StatusCard {
    background-color: #182331;
    border: 1px solid #314456;
    border-radius: 16px;
}
QLabel#AppTitle {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}
QLabel#AppSubtitle,
QLabel#SectionHint,
QLabel#MetaText,
QLabel#CompactMeta {
    color: #d4e0ea;
}
QLabel#SectionHint {
    font-size: 12px;
}
QLabel#MetaText,
QLabel#CompactMeta {
    font-size: 12px;
}
QLabel#StatusValue {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}
QLabel#StatusLabel {
    color: #b8cad8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
QLabel#CompactTitle {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#OverlayHint {
    background-color: rgba(8, 14, 22, 220);
    border: 1px solid rgba(115, 143, 167, 195);
    border-radius: 12px;
    color: #f8fbff;
    padding: 10px 12px;
    font-size: 12px;
}
QGroupBox {
    background-color: #182331;
    border: 1px solid #314456;
    border-radius: 16px;
    margin-top: 14px;
    padding: 16px 14px 14px 14px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #dff4ff;
}
QLineEdit,
QSpinBox,
QComboBox,
QListWidget,
QPlainTextEdit {
    background-color: #0b121a;
    border: 1px solid #3e566c;
    border-radius: 12px;
    padding: 8px 10px;
    color: #ffffff;
    selection-background-color: #4ec3ff;
    selection-color: #071018;
}
QLineEdit:focus,
QSpinBox:focus,
QComboBox:focus,
QListWidget:focus,
QPlainTextEdit:focus {
    border: 1px solid #82dcff;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QSpinBox::up-button,
QSpinBox::down-button {
    width: 18px;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 10px;
    margin: 3px 0;
    color: #f8fbff;
}
QListWidget::item:hover {
    background-color: #21374b;
}
QListWidget::item:selected {
    background-color: #2a4760;
    border: 1px solid #85d3ff;
}
QPushButton {
    background-color: #234056;
    border: 1px solid #527390;
    border-radius: 12px;
    color: #ffffff;
    padding: 10px 14px;
    font-weight: 700;
}
QPushButton:hover {
    background-color: #2d516d;
}
QPushButton:pressed {
    background-color: #193040;
}
QPushButton:disabled {
    background-color: #162632;
    border-color: #2a3e50;
    color: #7d94a7;
}
QPushButton#PrimaryButton {
    background-color: #2dc9b7;
    border-color: #86efe2;
    color: #071615;
}
QPushButton#PrimaryButton:hover {
    background-color: #51dbc9;
}
QPushButton#PauseButton {
    background-color: #f0cb68;
    border-color: #ffe69e;
    color: #231a05;
}
QPushButton#PauseButton:hover {
    background-color: #f6d985;
}
QPushButton#DangerButton {
    background-color: #df6a50;
    border-color: #f3a08f;
    color: #fffaf8;
}
QPushButton#DangerButton:hover {
    background-color: #ea7d65;
}
QPushButton#GhostButton {
    background-color: #182331;
    border: 1px solid #4c657b;
}
QPushButton#GhostButton:hover {
    background-color: #202f40;
}
QPushButton#RecordButton {
    background-color: #3b5cb8;
    border-color: #8eb0ff;
    color: #f9fbff;
}
QPushButton#RecordButton:hover {
    background-color: #4b70d1;
}
QPushButton#RecordButton[recording="true"] {
    background-color: #b84444;
    border-color: #ffb1b1;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QCheckBox::indicator:unchecked {
    background-color: #0b121a;
    border: 1px solid #527390;
    border-radius: 5px;
}
QCheckBox::indicator:checked {
    background-color: #4ec3ff;
    border: 1px solid #9ce5ff;
    border-radius: 5px;
}
QStatusBar {
    background-color: #0b1118;
    border-top: 1px solid #243442;
}
QSplitter::handle {
    background-color: #15222f;
}
QSplitter::handle:horizontal {
    width: 8px;
}
QSplitter::handle:vertical {
    height: 8px;
}
QFrame#Canvas {
    background-color: transparent;
    border: none;
}
"""
