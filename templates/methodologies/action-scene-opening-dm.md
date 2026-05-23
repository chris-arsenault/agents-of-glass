# Action Scene Opening DM

Goal: stage a concrete action scene before the first action slot.

1. Call `glass_check()`.
2. Declare or confirm the objective clock, any threat/timer clocks, and opening beat with `glass_scene_clock_*` and `glass_beat_*`.
3. Record the visible objective, danger, positions, and interactable scene objects as neutral facts.
4. Start or confirm action order.
5. Close with `glass_done(..., scene_status="active")`.
6. Submit the visible opening with `glass_turn_append(body="...")`.

Do not write files.
