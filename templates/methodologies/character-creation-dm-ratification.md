# Character Creation DM Ratification

Goal: ratify the party only after sheets and relationship facts are present.

1. Call `glass_check()`.
2. Run `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. Confirm every PC has a character record and usable relationship facts.
4. Confirm every PC has a want the work cannot satisfy and at least one `friction` fact with another PC — a live conflict of interest, not a safety protocol. If any are missing, message the player instead of ratifying.
5. Repair only concrete missing facts; do not add prose motifs.
6. Call `glass_mode_end()` when the party is ready for play.
7. Close with `glass_done(..., scene_status="active")`.
8. Submit the public party lock-in with `glass_turn_append(body="...")`.
