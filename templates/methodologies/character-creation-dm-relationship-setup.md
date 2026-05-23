# Character Creation DM Relationship Setup

Goal: move the table from individual PCs into relationship commitments.

1. Call `glass_check()`.
2. Run `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. Identify which players still owe relationship facts.
4. Send targeted messages for missing or incoherent relationship commitments.
5. Add or repair neutral relationship prompts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<character-id>", "predicate": "relationship", "object_id": "<other-character-id>", "text": "<neutral relationship commitment>"}])` only when needed.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit a brief public bridge with `glass_turn_append(body="...")`.
