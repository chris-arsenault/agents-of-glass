# Rapid Response Character

Goal: answer the specific rapid prompt from inside the character.

1. Read the injected rapid prompt.
2. Call `glass_check()` only if messages or state are needed to answer.
3. Close with `glass_done(summary="<what changed or no state change>", state=["no state change"], rolls="none", scene_status="active", next_speaker="default")`.
4. Submit a brief direct public response with `glass_turn_append(body="...")`.

Do not write files or broaden the prompt.
