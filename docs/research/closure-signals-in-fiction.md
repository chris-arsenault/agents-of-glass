# Closure Signals in Fiction

**Status:** Placeholder. Linked to the deferred design in [`../design/scene-ending.md`](../design/scene-ending.md).

## What We Want to Know

Human writers and editors have implicit knowledge of when a scene is "done." We want to make that knowledge explicit enough to encode it — particularly for the scene-closer agent (deferred Layer D in `scene-ending.md`).

Questions to investigate:

- What linguistic / structural signals reliably mark a scene's natural endpoint in published prose?
- How do different genres mark closure differently (action vs. dialogue vs. introspection)?
- How do TV/film scripts mark scene breaks, and how much of that translates?
- Are there checklist-style heuristics editors use ("does the scene answer its dramatic question? has the POV character changed state? is there a button line?")?
- Can closure be detected from local (last-N-turns) signals alone, or does it need scene-level context?

## Why It Matters

The closure problem is the hardest design challenge in this project (see [closure_problem memory](../../../../home/dev/.claude/projects/-home-dev-repos-agents-of-glass/memory/closure_problem.md) — wait, no: see the discussion in [`../design/scene-ending.md`](../design/scene-ending.md)). The DM agent's helpfulness gradient pulls toward continuation; the closer agent's job is to pull the other way. The closer's prompt needs to be specific about *what to look for*, not just "lean toward closing."

A research-backed checklist would make the closer agent dramatically more useful than a vibes-based prompt.

## To Do

- Survey writing-craft literature on scene structure (Robert McKee, Jack Bickham, John Yorke)
- Pull out the explicit "scene is done when..." heuristics
- Distill into a prompt-shaped checklist for the closer agent
- Test on real session transcripts (forward — does the checklist agree with the human-perceived right ending point?)
- Update this file with the synthesis
