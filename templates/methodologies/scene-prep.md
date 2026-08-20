# Scene Prep

Goal: stage a playable scene with hard state and plainly recorded facts.

A scene is not ready until it has all three:

- **An opposing will on screen** — the arc antagonist or an agent of it,
  present or acting into the scene, with a move it makes this scene. Hazards
  and weather complicate; they do not carry a scene alone.
- **Something irrevocably losable this scene** — a person, place, cargo,
  standing, machine, or route that can be gone at the end.
- **A problem family that changes the shape of play** — pick from the
  families in `how-to/problem-families.md`. The injected prompt lists the
  problem families of recent scenes; do not repeat any of them. Favor the
  families this campaign has not touched: heist/breach, chase/escape,
  social pressure/coercive bargain, fight/monster, investigation, triage.

1. Call `glass_check()`.
2. Confirm the active arc with `glass_arc_current()` or `glass_arc_close_check(arc_id="<arc-id>")`.
3. Create the scene with `glass_scene_create(scene_id="...", scene_type="<problem-family>", arc_id="...")`.
4. End scene-prep if it is active, then start the play mode with `glass_mode_start(mode_name="scene-play|action", scene_id="<scene>")`.
5. Declare the objective clock and any needed threat/timer clocks with `glass_scene_clock_declare(...)`. Give the opposing will's pressure a threat clock when it advances on its own.
6. Start the opening beat with `glass_beat_start(...)`.
7. Record facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "high", "scope_id": "<scene-id>", "subject_id": "scene", "predicate": "opposing-will", "text": "<who or what opposes the party here and its move this scene>"}, {"kind": "fact", "audience": "continuity", "importance": "high", "scope_id": "<scene-id>", "subject_id": "scene", "predicate": "at-stake", "text": "<what can be irrevocably lost this scene>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "scene", "predicate": "objective", "text": "<visible objective>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "scope_id": "<scene-id>", "subject_id": "<object-id>", "predicate": "descriptor", "text": "<plain descriptor and affordance>"}])` for the opposing will, the stake, the objective, positions, and three interactable scene objects.
8. Close with `glass_done(..., scene_status="active")`.
9. Submit the visible scene opening with `glass_turn_append(body="...")`.

Do not write prep, summary, table, or lore files.
