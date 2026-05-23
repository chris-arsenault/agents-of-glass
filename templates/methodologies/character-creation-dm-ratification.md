# Character Creation DM Ratification

Goal: ratify the party only after sheets and relationship facts are present.

1. Call `glass_check()`.
2. Run `glass_character_bulk_get(all_characters=True)` and `glass_fact_pack(audience="continuity", output_format="markdown")`.
3. Confirm every PC has a character record and usable relationship facts.
4. Repair only concrete missing facts; do not add prose motifs.
5. Call `glass_mode_end()` when the party is ready for play.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit the public party lock-in with `glass_turn_append(body="...")`.
