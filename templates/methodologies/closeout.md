---
title: Scene and Act Closeout Methodology
status: authored
audience: dm
applies_to_modes: [scene-play, action, prelude, arc-creation, scene-prep, intermission]
---

# Scene and Act Closeout

Use this whenever Mara closes a scene, prelude, act, or arc. This is an ordered
workflow, not advice. Execute every step in order. A step may end with "no
lore change," "no journal change," or "no state change," but it must be
considered and recorded in `dm/scratchpad.md`.

The purpose is commitment. Long-running mysteries can stay unresolved, but the
core tension of the scene or act cannot close as unknown. Assign consequence
and impact before calling the close command.

## Before You Start

Read:

1. The active `table/` and active scene `summary.md`.
2. The relevant arc `plan.md`, `context.md`, and `summary.md`.
3. `dm/scratchpad.md`.
4. Any unread messages.
5. Character state if HP, inventory, XP, consequences, or signature moves
   changed during the scene.

Then create a `dm/scratchpad.md` section titled:

```markdown
## Closeout - <scene-or-act-id>
```

Record the result of each step below under that heading, even when the answer
is "no change."

## Scene Close Steps

1. **Name the core tension.** One sentence: what was this scene actually
   deciding? If the party only partly succeeded, name the partial. If they
   failed, name the failure.

2. **Assign consequence and impact.** Write what changed in the world, who paid
   a cost, who gained leverage, what is delayed, what is exposed, or what option
   narrowed. Do not write "unclear," "TBD," or "intentionally unresolved" for
   the scene's core tension.

3. **Enumerate outcomes.** Draft one or two in-universe bullets for
   `glass scene end --outcome`. These are referenceable facts, not commentary:
   what became true, changed hands, was lost, was owed, was witnessed, or was
   filed.

4. **NPC carry-forward.** List every NPC who appeared or was materially affected.
   For each, choose one:
   - promote or update a durable `dm/notes/npcs/` entry
   - add a scratchpad callback if they may return
   - write "no NPC carry-forward"

5. **Mechanical and fictional state.** Apply persistent changes before close:
   character consequences, HP, momentum, inventory, signature status, durable
   clocks, faction clocks, public clocks, or relationship leverage. If nothing
   persists mechanically, write "no mechanical/state change."

6. **Lore and canon.** If a new public fact should be available later, update
   `shared/lore/` or import/canonize with the lore tools. If it is DM-only,
   update `dm/notes/`, `dm/secret/`, or `dm/scratchpad.md`. If none, write
   "no lore change."

7. **Journals and reflection.** Do not write player journals. If Mara needs a
   private dated reflection, update `dm/journal/`. Otherwise write "no journal
   change."

8. **Summaries.** Prepare the scene summary text. Append or update arc and
   campaign summaries when the scene changed durable continuity. If the scene
   did not change a higher level, write "no arc summary change" or "no campaign
   summary change."

9. **Party-visible beats.** Prepare the `--beats` lines for `shared/quest-log.md`.
   These are party-visible canon beats, not private implications. If none,
   write "no quest-log beat."

10. **XP and rewards.** Decide XP and any immediate rewards, costs, item
    requests, training hooks, or ability hooks. If none, write "no reward
    change."

11. **Run the close command.** Use the outcomes from step 3:

```bash
glass scene end \
  --summary "..." \
  --outcome "..." \
  --beats "..." \
  --xp tev=2,sumi=2,renno=2,kit=2
```

Use a second `--outcome` only when two durable outcomes are clearer than one.
Then end the mode if the mode is finished.

## Act / Arc Close Steps

Run this only after all active scenes in the act are closed.

1. **Review scene outcomes.** Read each scene summary and outcome section.
   Identify what the act proved, cost, changed, or left as a live hook.

2. **Name the act's core tension.** One sentence. Do not close the act on a
   question mark. The answer may be "they failed," "they only bought time," or
   "they changed the problem."

3. **Enumerate act outcomes.** Draft one or two in-universe bullets for
   `glass arc close --outcome`.

4. **Promote recurring NPCs and locations.** Any NPC, place, object, faction
   face, or institution that may recur gets a durable note or an explicit
   scratchpad callback. If none, write "no promoted NPC/location."

5. **Log lasting consequences.** Apply cross-scene character consequences,
   durable clocks, faction clock ticks, inventory/reward changes, obligations,
   debts, reputational changes, or route changes. If none, write "no lasting
   consequence."

6. **Update continuity.** Update the arc summary, campaign summary, `dm/notes/`,
   `shared/lore/`, quest log, and DM journal as needed. Each surface must get
   either an update or a written "no change."

7. **Carry hooks forward.** Add a compact `dm/scratchpad.md` list:
   - callbacks Mara wants to bring back
   - unresolved mysteries that are intentionally still live
   - player requests to honor in intermission or scene prep
   - magic item, ability, training, ally, or payoff requests

8. **Run the close command.**

```bash
glass arc close <arc-id> \
  --summary "..." \
  --outcome "..."
```

Then start intermission or scene prep according to campaign lifecycle.

## Prohibitions

- Do not use "left unresolved" as a substitute for consequence.
- Do not leave a scene's main roll/failure without impact.
- Do not rely on final narration alone. If a fact matters later, put it in a
  summary, note, lore entry, quest beat, state command, or scratchpad callback.
- Do not write player journals for them.
