# Character Creation Player Relationship

Goal: define concrete relationships between characters, not relationships between quirks.

1. Call `glass_check()`.
2. Run `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. For each relationship, name the other character, the concrete history or obligation, the current tension, and what it changes at the table.
4. Record relationships with one `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<character>", "predicate": "relationship", "object_id": "<other>", "text": "<neutral commitment>"}])` call.
5. Use messages for coordination when another player needs to accept or answer.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit only public relationship commitments with `glass_turn_append(body="...")`.

Do not write relationship markdown files. Do not make every relationship about character tics.
