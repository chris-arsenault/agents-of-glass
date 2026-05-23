# Character Creation Player Build

Goal: create one complete, grounded PC without letting tics consume continuity.

1. Call `glass_check()`.
2. Read the organization facts and required character fields.
3. Create the character with `glass_character_new(...)`, including `starting_items=[...]` and initial `facts=[...]` in that same call.
4. Add the signature move with `glass_character_signature_add(...)`.
5. Do not use separate state-update calls for the initial identity/profile facts unless repairing a failed or incomplete creation.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit the public character introduction with `glass_turn_append(body="...")`.

Do not write intro, notes, journal, relationship, or scratch files.
