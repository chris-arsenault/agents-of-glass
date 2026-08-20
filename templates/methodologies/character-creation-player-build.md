# Character Creation Player Build

Goal: create one complete, grounded PC without letting tics consume continuity.

Build the person before the professional. The sheet must carry a want the
organization's work cannot satisfy — greed, revenge, a person to find, a
secret to keep, a place to get back to — and that want must be capable of
pulling against the job. Competence coverage is the floor, not the character.

1. Call `glass_check()`.
2. Read the organization facts and required character fields.
3. Create the character with `glass_character_new(...)`, including `starting_items=[...]` and initial `facts=[...]` in that same call. Make `non_work_want` a want the work itself can never deliver, and give `primary_drive` room to conflict with orders.
4. Add the signature move with `glass_character_signature_add(...)`.
5. Do not use separate state-update calls for the initial identity/profile facts unless repairing a failed or incomplete creation.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit the public character introduction with `glass_turn_append(body="...")`.

Do not write intro, notes, journal, relationship, or scratch files.
