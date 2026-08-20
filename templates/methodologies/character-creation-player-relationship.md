# Character Creation Player Relationship

Goal: define concrete relationships between characters, not relationships
between quirks — and at least one that pulls the party in two directions.

Relationships are history and friction, not protocols. A working agreement
("you may stop me", "sound my rigging first") is not a relationship; it is a
procedure two colleagues share. Give each relationship a concrete past and at
least one live disagreement, debt, rivalry, or conflicting want that play can
aggravate.

1. Call `glass_check()`.
2. Run `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. For each relationship, name the other character, the concrete history or obligation, the current tension, and what it changes at the table.
4. Record one relationship where your interests genuinely conflict with the other character's — something both of you want that you cannot both have, or a course of action you would each take that the other would block. Record it with `predicate="friction"`.
5. Record relationships with one `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<character>", "predicate": "relationship", "object_id": "<other>", "text": "<concrete history and tension>"}, {"kind": "fact", "audience": "continuity", "importance": "high", "subject_id": "<character>", "predicate": "friction", "object_id": "<other>", "text": "<the live conflict of interest>"}])` call.
6. Use messages for coordination when another player needs to accept or answer.
7. Close with `glass_done(..., scene_status="active")`.
8. Submit only public relationship commitments with `glass_turn_append(body="...")`. One turn covers all your relationships; do not perform the same handoff beat once per crewmate.

Do not write relationship markdown files. Do not make every relationship about character tics.
