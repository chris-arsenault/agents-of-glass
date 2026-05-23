# Character Creation DM Setup

Goal: make the organization constraints and missing character requirements clear.

1. Call `glass_check()`.
2. Use `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. Identify which players still need sheets or required fields.
4. Use messages for specific missing choices.
5. Add or repair neutral setup facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<character-id>", "predicate": "<predicate>", "text": "<neutral setup fact>"}])`.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit a short public setup note with `glass_turn_append(body="...")`.

Do not write character-creation files.
