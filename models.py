"""Data models for automation actions, runtime settings, and profiles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from config import (
    DEFAULT_CYCLE_DELAY,
    DEFAULT_DRAG_DURATION_MS,
    DEFAULT_HOLD_MS,
    DEFAULT_MOVE_DURATION_MS,
    DEFAULT_POST_DELAY,
    DEFAULT_PRE_DELAY,
    DEFAULT_REPEAT_COUNT,
)

ACTION_TYPES = ("Click", "Long Press", "Drag", "Move")
CLICK_TYPES = ("Left", "Right", "Middle", "Double")


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ActionNode:
    """Represents a single automation action in a profile sequence."""

    id: int
    x: int
    y: int
    click_type: str = "Left"
    action_type: str = "Click"
    target_x: int | None = None
    target_y: int | None = None
    pre_delay: int = DEFAULT_PRE_DELAY
    post_delay: int = DEFAULT_POST_DELAY
    hold_ms: int = DEFAULT_HOLD_MS
    drag_duration_ms: int = DEFAULT_DRAG_DURATION_MS
    move_duration_ms: int = DEFAULT_MOVE_DURATION_MS
    source: str = "manual"

    def __post_init__(self) -> None:
        self.id = max(1, _to_int(self.id, 1))
        self.x = _to_int(self.x, 0)
        self.y = _to_int(self.y, 0)
        self.target_x = None if self.target_x is None else _to_int(self.target_x, self.x)
        self.target_y = None if self.target_y is None else _to_int(self.target_y, self.y)
        self.pre_delay = max(0, _to_int(self.pre_delay, DEFAULT_PRE_DELAY))
        self.post_delay = max(0, _to_int(self.post_delay, DEFAULT_POST_DELAY))
        self.hold_ms = max(50, _to_int(self.hold_ms, DEFAULT_HOLD_MS))
        self.drag_duration_ms = max(50, _to_int(self.drag_duration_ms, DEFAULT_DRAG_DURATION_MS))
        self.move_duration_ms = max(0, _to_int(self.move_duration_ms, DEFAULT_MOVE_DURATION_MS))
        self.source = (self.source or "manual").strip() or "manual"
        if self.click_type not in CLICK_TYPES:
            self.click_type = "Left"
        if self.action_type not in ACTION_TYPES:
            self.action_type = "Click"

    @property
    def summary(self) -> str:
        if self.action_type == "Drag" and self.target_x is not None and self.target_y is not None:
            return f"Drag {self.x},{self.y} -> {self.target_x},{self.target_y}"
        if self.action_type == "Long Press":
            return f"Hold {self.click_type} at {self.x},{self.y} for {self.hold_ms} ms"
        if self.action_type == "Move":
            return f"Move pointer to {self.x},{self.y} in {self.move_duration_ms} ms"
        if self.click_type == "Double":
            return f"Double-click at {self.x},{self.y}"
        return f"{self.click_type} click at {self.x},{self.y}"

    def ensure_drag_target(self) -> None:
        if self.target_x is None:
            self.target_x = self.x + 120
        if self.target_y is None:
            self.target_y = self.y

    def clone(self, new_id: int, offset: tuple[int, int] = (24, 24)) -> "ActionNode":
        duplicate = ActionNode.from_dict(self.to_dict())
        duplicate.id = new_id
        duplicate.x += offset[0]
        duplicate.y += offset[1]
        if duplicate.target_x is not None:
            duplicate.target_x += offset[0]
        if duplicate.target_y is not None:
            duplicate.target_y += offset[1]
        return duplicate

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "ActionNode":
        return ActionNode(**data)


@dataclass
class RunSettings:
    """Controls how a profile sequence is replayed."""

    loop_forever: bool = True
    repeat_count: int = DEFAULT_REPEAT_COUNT
    cycle_delay: int = DEFAULT_CYCLE_DELAY

    def __post_init__(self) -> None:
        self.loop_forever = bool(self.loop_forever)
        self.repeat_count = max(1, _to_int(self.repeat_count, DEFAULT_REPEAT_COUNT))
        self.cycle_delay = max(0, _to_int(self.cycle_delay, DEFAULT_CYCLE_DELAY))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "RunSettings":
        data = data or {}
        return RunSettings(
            loop_forever=data.get("loop_forever", True),
            repeat_count=data.get("repeat_count", DEFAULT_REPEAT_COUNT),
            cycle_delay=data.get("cycle_delay", DEFAULT_CYCLE_DELAY),
        )


@dataclass
class Profile:
    """A named automation profile that can be saved to and loaded from JSON."""

    name: str = "Default Profile"
    nodes: list[ActionNode] = field(default_factory=list)
    settings: RunSettings = field(default_factory=RunSettings)

    def __post_init__(self) -> None:
        self.name = (self.name or "Default Profile").strip() or "Default Profile"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "settings": self.settings.to_dict(),
            "nodes": [node.to_dict() for node in self.nodes],
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Profile":
        return Profile(
            name=data.get("name", "Default Profile"),
            settings=RunSettings.from_dict(data.get("settings")),
            nodes=[ActionNode.from_dict(node) for node in data.get("nodes", [])],
        )

    def save_to_file(self, filepath: str) -> None:
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=4)

    @staticmethod
    def load_from_file(filepath: str) -> "Profile":
        with Path(filepath).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return Profile.from_dict(data)

    def snapshot(self) -> "Profile":
        return Profile.from_dict(self.to_dict())

    def next_node_id(self) -> int:
        return max((node.id for node in self.nodes), default=0) + 1

    def get_node(self, node_id: int) -> ActionNode | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def duplicate_node(self, node_id: int) -> ActionNode | None:
        original = self.get_node(node_id)
        if original is None:
            return None
        duplicate = original.clone(self.next_node_id())
        insert_at = self.nodes.index(original) + 1
        self.nodes.insert(insert_at, duplicate)
        return duplicate

    def remove_node(self, node_id: int) -> bool:
        for index, node in enumerate(self.nodes):
            if node.id == node_id:
                del self.nodes[index]
                return True
        return False

    def move_node(self, node_id: int, direction: int) -> bool:
        for index, node in enumerate(self.nodes):
            if node.id != node_id:
                continue

            target_index = index + direction
            if not 0 <= target_index < len(self.nodes):
                return False

            self.nodes[index], self.nodes[target_index] = self.nodes[target_index], self.nodes[index]
            return True
        return False

    def replace_nodes(self, nodes: list[ActionNode]) -> list[ActionNode]:
        self.nodes = []
        return self.append_nodes(nodes)

    def append_nodes(self, nodes: list[ActionNode]) -> list[ActionNode]:
        appended: list[ActionNode] = []
        for node in nodes:
            clone = ActionNode.from_dict(node.to_dict())
            clone.id = self.next_node_id()
            self.nodes.append(clone)
            appended.append(clone)
        return appended
