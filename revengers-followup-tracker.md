# The Revengers Follow-Up Tracker

Focused follow-up items from `campaigns/the-revengers`, classified by current
repo state. Item numbers are stable from the first pass so discussion can keep
referring to them directly.

## Status Labels

- **Open:** still looks actionable in current code or prompts.
- **Partial:** partly addressed, but the remaining failure mode is still real.
- **Monitor:** do not implement from this alone; watch the next run.
- **Addressed / Verify:** a fix is now in repo; verify in a future run.
- **Closed:** no further action planned.

## Open

3. **Clock lifecycle can diverge from fiction**

   - **Source:** `Cinder Cascade Reaches The Docks` stayed active at `0/4`
     after several scenes; `Bloom Edge Strains At Cordon Twelve` resolved at
     `0/4`.
   - **Current code/guidance:** Close-check surfaces unresolved clocks, but it
     does not force reconciliation of stale, obsolete, or fiction-resolved
     clocks.
   - **Why it matters:** Danger can resolve in narration without clock movement,
     while stale clocks keep blocking or confusing arc closure.
   - **Likely fix:** Add scene/arc close reconciliation: each active scene or
     arc clock must be advanced, resolved, retired as obsolete, or carried
     forward with a fresh reason.

5. **Item continuity lacks a hard-state reconciliation path**

   - **Source:** Duva's witness bell cane was described as sealed under the
     reset sled, then later used as live equipment. A player note now treats the
     character sheet as canonical unless the DM reopens the contradiction.
   - **Current code/guidance:** Inventory exists, but there is no lightweight
     status/location reconciliation for notable items described as lost, sealed,
     broken, spent, or recovered.
   - **Why it matters:** Equipment stakes become soft if items can drift between
     unavailable and available through prose.
   - **Likely fix:** Require scene closeout to reconcile notable item state, or
     add a small item status/location projection for important equipment.

## Partial

6. **Durable campaign memory projection is still uneven**

   - **Source:** In this run, campaign summary stopped at Skiffmoor, the
     Cinderwake arc summary stopped at Red Thread, and party knowledge stopped
     at Skiffmoor.
   - **Already mitigated:** TURN_START includes active scene summary and command
     nudges for summary work, so agents are not only relying on root summaries.
   - **Still open:** There is no automatic guarantee that scene close updates
     campaign summary, arc summary, party knowledge, and quest log consistently.
   - **Likely fix:** Treat this as a projection design item, not a pure prompt
     issue. Decide which public summaries must be updated automatically on
     scene close.

## Monitor

7. **Offscreen antagonist pressure may need stronger prompting**

   - **Source:** The hidden Coremark route clock remained at `0/4` while the
     party repeatedly won public scenes.
   - **Already mitigated:** Later Mara guidance says an antagonist should always
     exist and act, even offscreen.
   - **Current status:** Monitor narrative output. This does not need to become
     hard state unless future runs show that prompt guidance cannot keep
     antagonists active.

## Addressed / Verify

9. **Proof-chain language dominated this campaign's durable memory**

   - **Source:** The Revengers summaries and notes repeatedly returned to
     proof strips, public boards, signatures, witness chains, tags, and
     evidence integrity.
   - **Fix:** Added broad taste guidance for DM and player narration: action
     scenes may include records, witnesses, and proof, but the story should not
     become documentation that danger happened. Proof should create leverage for
     the next dangerous choice, not become the repeated endpoint of play. Scene
     prep and closeout now ask Mara to keep summaries centered on what action
     changed first.
   - **Verify:** Future summaries should remember who was saved, hurt, moved,
     changed, exposed, adapted, or forced into a choice before they remember how
     the event was documented.

1. **Quest log can persist malformed escaped newlines**

   - **Source:** `campaigns/the-revengers/shared/quest-log.md` had a literal
     `\n` inside the Cordon Twelve bullet.
   - **Fix:** `glass scene end --beats` and `glass quest beat` now normalize
     escaped `\\n` / `\\r\\n` sequences into real line breaks before appending
     quest-log bullets.
   - **Verify:** Future quest-log entries should not contain literal `\n`
     artifacts.

2. **Rolls can auto-create typo skills**

   - **Source:** Sela had both `count beats under load` and
     `count-beats-under-load`; the closeout explicitly said a slug typo created
     the stray skill.
   - **Fix:** `glass roll` and `glass scene pressure` can roll undeclared
     skills as improvised `fool` checks, but they do not become durable and do
     not gain skill XP. A skill is saved only when the caller uses
     `--save-skill` or `glass character skill-declare`; both paths use the
     existing skill-slot cap.
   - **Verify:** A typo skill should remain a one-off roll unless it is
     deliberately saved.

4. **Projected Claude MCP config is schema-noisy**

   - **Source:** Claude debug logs for Kit/Renno showed:
     `MCP config errors for .../.mcp.json: ["Invalid input: expected record, received undefined"]`.
   - **Fix:** Projected `.mcp.json` files are now written as
     `{ "mcpServers": {} }` instead of `{}`.
   - **Verify:** New Claude turns should not report that `.mcp.json` schema
     error.

10. **Planning-mode churn after planning is complete**

    - **Source:** The Revengers had many campaign-planning turns that only
      restated that planning remained complete.
    - **Current repo state:** Campaign-planning methodology now tells Mara to
      run `glass mode end` when complete, and the bootstrap runner can recover
      after mode-budget exhaustion if validation passes.
    - **Current status:** Do not keep this as an open Revengers follow-up unless
      it recurs in a new run.

## Closed

8. **Momentum saturation is separate from solved roll math**

   - **Source:** In this run, all PCs reached momentum 3 and stayed there.
   - **Resolution:** Momentum no longer modifies roll totals, and the old
     reinforcement loop is gone. No further action planned unless a new,
     separate momentum failure appears.
