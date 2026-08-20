# Arc Creation

Goal: create or activate an arc built on an opponent with a will, through
hard-state MCP tools and plainly recorded facts.

An arc is not valid without three things, each recorded as a fact:

- **An antagonist** — a named opposing agent (person, faction, creature,
  or institution acting through people) with a goal, resources, and a next
  move. Weather, terrain, and decay are complications, not antagonists.
- **Stakes** — what the party or the people they care about can lose for
  good.
- **An inaction consequence** — what the antagonist takes or breaks if the
  party does nothing. The arc must move without the party; they respond to
  it, not the reverse.

1. Call `glass_check()`.
2. Create or activate the arc with `glass_arc_*`.
3. Set required arc clocks with `glass_clock_*`. Give the antagonist's next
   move a clock when it advances on its own.
4. Advance recurring threads only with `glass_thread_advance(...)`.
5. Record the required facts with `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "high", "subject_id": "<arc-id>", "predicate": "antagonist", "text": "<named opponent: goal, resources, next move>"}, {"kind": "fact", "audience": "continuity", "importance": "high", "subject_id": "<arc-id>", "predicate": "stakes", "text": "<what can be lost for good>"}, {"kind": "fact", "audience": "continuity", "importance": "high", "subject_id": "<arc-id>", "predicate": "inaction-consequence", "text": "<what the antagonist takes or breaks if the party does nothing>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "<arc-id>", "predicate": "premise", "text": "<premise>"}])`.
6. Close with `glass_done(..., scene_status="active")`.
7. Submit public arc readiness prose with `glass_turn_append(body="...")`.

Do not write plan files.
