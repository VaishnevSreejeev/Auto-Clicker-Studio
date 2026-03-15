# Auto Clicker Studio

Auto Clicker Studio is a PyQt6 desktop automation suite for building, recording, editing, and replaying mouse-driven workflows.

## Features

- Visual overlay with draggable numbered action nodes.
- Action editor with support for:
  - `Click`
  - `Long Press`
  - `Drag`
  - `Move`
- Per-action timing:
  - pre-delay
  - post-delay
  - hold duration
  - drag duration
  - move duration
- Mouse recording:
  - capture clicks, long presses, drags
  - optionally capture pointer movement between actions
  - save recorded actions directly into the active profile
- Profile system:
  - save to JSON
  - load from JSON
  - switch between automation profiles
- Execution controls:
  - `F8` record / stop recording
  - `F10` start
  - `F9` pause or resume
  - `Esc` stop
- Compact strip mode:
  - minimizing the main window collapses it into a thin utility strip with essential controls
- Safety:
  - PyAutoGUI failsafe remains enabled
  - desktop safety border prevents invalid coordinates

## Workflow

1. Run `python main.py`.
2. Use `Add Action` for manual steps or `Record` to capture live mouse activity.
3. Open the overlay to drag nodes onto exact screen coordinates.
4. Select an action from the sequence list to edit it in the inspector.
5. Save the profile when the sequence is ready.
6. Start playback with `Start` or `F10`.

## Notes

- The overlay is translucent on purpose so it can act as a placement layer without replacing the real desktop.
- The main window uses solid panels for readability and a compact strip when minimized.
- Recorded actions can replace the current sequence or append to it, depending on the selected recording mode.
