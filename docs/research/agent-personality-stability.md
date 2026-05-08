# Agent Personality Stability

**Status:** Placeholder. Will be filled in once we've run enough sessions to see drift.

## What We Want to Know

The five people (Mara, Tev, Sumi, Renno, Kit) are spawned fresh as `claude -p` invocations every turn. Their continuity comes from:

- Their person file (stable role prompt)
- Their private notes (which they wrote in earlier turns)
- The transcript window (recent turns)

How well does this preserve consistent personality across hundreds of turns and many sessions?

Specific risks:

- **Drift toward generic "helpful agent" voice** as turns accumulate
- **Convergence** — the four player agents starting to sound the same after long sessions
- **Identity bleed** — an agent picking up the voice of whoever spoke last in the transcript window
- **Note neglect** — the agent stops reading their own private notes, so character continuity breaks

## Why It Matters

The whole point of "people, not personas" (see [`../principles/goals-and-motivation.md`](../principles/goals-and-motivation.md)) is friction between distinct voices. If the voices collapse, the experiment fails on its central question.

## To Do

- Run multiple sessions
- Sample turns from early/mid/late sessions and have a separate analysis pass score voice distinctiveness
- If drift is real, design countermeasures (regular voice-anchor turns, voice-sample injections in prompts, periodic person-file refreshes)
- Update this file with findings
