---
title: Arc Creation Methodology
status: authored
audience: dm
applies_to_modes: [campaign-planning, arc-creation, scene-prep, intermission]
---

# Arc Creation

Run this when the DM formalizes a multi-scene pressure unit. An arc is not a
plot. It is a durable pressure surface with threats, clocks, possible outcomes,
and a strong start.

Arc baseline: every arc has an active antagonist or antagonistic force and a
concrete physical danger to people. The antagonist can work off screen, but they
must be doing something now. The arc cannot be mainly a legal, audit, claims, or
workplace-procedure problem. The arc also cannot sit in one place: after two
scenes in the same location or location family, the next scene must
substantially move.

## Sequence

1. **Create or select the arc.**
   - If the arc does not exist, make one non-adjacent real-world pull before
     creating it. Do not use fantasy, RPG, fiction-writing, or campaign advice.
     Choose a source/domain whose operating details are not adjacent to the
     campaign premise.
   - Record exactly how the pull changes the arc in the create command:

     ```bash
     glass arc create <arc-slug> \
       --pull-source "<real-world domain/source>" \
       --pull-utilization "<which threat, node, clock, scarcity, strong start, clue, hazard, or end-state pressure uses it>"
     ```

   - The utilization note must name a concrete borrowed detail and the arc surface
     it changes. Examples: "airport lost-bag triage tags shape the evidence node
     and the three clock labels"; "food-safety cold-chain logs shape the smuggled
     medicine hazard and inspection NPC practice."
   - Run `glass arc activate <arc-slug>` when this arc should receive new
     scenes by default.
   - Run `glass arc current` and verify the intended arc is active.

2. **Read current state.**
   - `glass summary show campaign`
   - `glass summary show arc <arc-slug>` if a summary already exists.
   - `glass lore list`
   - `glass clock list --scope arc --anchor <arc-slug> --all`
   - Read `dm/foundation.md`, relevant `dm/notes/`, and current player-facing
     surfaces in `shared/` and `table/`.

3. **Import only load-bearing lore.**
   - Use `glass lore search <query>` to find world-bible entries.
   - Use `glass lore import <world-bible-path>` only for entries the players
     or this arc will actually touch.

4. **Write `arcs/<arc-slug>/plan.md` in this order.**
   - Non-adjacent pull utilization: copy the source/domain and utilization note
     from `arcs/<arc-slug>/pulls.md`, then keep the borrowed detail visible in the
     sections it shaped.
   - Stakes question: one question the DM does not know the answer to.
   - Active antagonist: who or what is pushing against the party, what they want,
     and their next off-screen move if no one stops them.
   - Concrete danger: the bodily harm, contamination, collapse, violence,
     abduction, exposure, starvation, or other physical cost this arc can inflict
     on named people or groups.
   - Threats: 2-4 active people, factions, places, or conditions, each with an
     impulse and an off-screen next move.
   - Clocks: 1-3 escalation tracks, each with 3-5 concrete segments; at least
     one clock segment must visibly worsen physical danger, coercion, pursuit, or
     antagonist position.
   - Possible end states: 3-5 plausible conclusions; commit to none.
   - Strong start: the first scene pressure, not the arc solution. It must put
     danger, coercion, pursuit, fighting, or direct antagonist action into reach
     by the end of the first scene.
   - Nodes: 3-5 places, people, records, routes, or institutions the party may
     engage; each names what can be learned and at least two outbound clues.
     Include enough physically distinct nodes to support a substantial location
     shift at least every third scene.
   - Curated ingredients: specific NPCs, factions, locations, creatures, named
     things, and public lore already in play.
   - Secrets: 3-7 atomic facts, unattached to fixed scenes.
   - Done criteria: when the arc should close or be abandoned.

5. **Write `arcs/<arc-slug>/context.md`.**
   - Include only what the players currently know or can fairly infer.
   - Keep it short enough to read during a turn.

6. **Create durable clocks.**
   - For public or cross-scene pressure, run:
     `glass clock set <clock-id> --scope arc --anchor <arc-slug> --max <n> [--public]`.
   - Do not leave important countdowns only in `plan.md`.

7. **Commit and register.**
   - Run `glass sync apply arcs/<arc-slug>`.
   - Run `glass summary write arc <arc-slug> --body "<compact current arc summary>"`.
   - Run `glass clock list --scope arc --anchor <arc-slug> --all`.

8. **Close the turn.**
   - Write `TURN.md` with the arc state that is now ready.
   - Run `glass turn end --summary "<arc created or updated>" --state "<arc files/clocks/summaries updated>" --rolls none --next default`.

## Prohibitions

- Do not write a planned sequence of scenes.
- Do not choose the end state in advance.
- Do not create secrets that can be learned in only one way when the arc needs
  them to land.
- Do not put player-facing facts only in DM notes.
- Do not create or update an arc without a non-adjacent pull utilization note
  naming the concrete detail and where it is used.
- Do not build an arc whose main play loop is interpreting records, making
  claims, preserving chain of custody, or winning an institutional argument.
  Those may expose the threat; they cannot be the threat.
- Do not plan an arc around repeated scenes in the same place or same kind of
  room. A different desk, window, counter, lane, bench, or hearing inside the
  same institutional complex is not a substantial location shift.

## CLI Encoding Opportunities

These are not commands yet:

- `glass arc plan-check <arc>` for required sections, clocks, outbound clues,
  context freshness, and summary presence.
- `glass arc threat add` and `glass arc node add` for structured pressure that
  can later feed scene prep.
