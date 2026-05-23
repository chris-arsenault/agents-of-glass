# Organization Bootstrap

Goal: define the campaign organization as neutral durable facts and a concise public prose reveal.

1. Call `glass_check()`.
2. Compare against the injected previous-organization patterns and avoid repeating mission, method, culture, role shape, or pull domain.
3. Record the non-adjacent pull, organization identity, dangerous work, operating method, internal culture, public constraints, and character-creation brief with one `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "campaign", "predicate": "pull", "text": "<neutral non-adjacent pull source and how it is used>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "organization", "predicate": "identity", "text": "<neutral organization identity>"}])` call, adding the remaining facts as full objects in the same list.
4. Do not split bootstrap facts across repeated single-fact calls.
5. End the mode with `glass_mode_end()` when the organization is concrete enough for character creation.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit a short public organization brief with `glass_turn_append(body="...")`.

Do not write organization markdown files. Do not use files as the continuity store.
