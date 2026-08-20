# Prompt Guard Disposition Ledger

Working doc for the prompt-system overhaul (see `PROMPT-OVERHAUL-PLAN.md`, M0/M2).
Every guard currently in the runtime prompt surface, the failure mode it fixed, a
cause hypothesis, and a disposition. Nothing is deleted in M2 except rows marked
**drop**, each of which names the upstream fix that removes its cause. When M4's
fresh campaign shows a retired failure recurring, the guard returns in the
cheapest layer that holds it and this file records the outcome.

Dispositions:

- **relocate** — survives, moves to the per-role system prompt (cached, cheap,
  stable across turns).
- **keep-turn** — survives in the injected turn prompt (turn- or mode-specific).
- **keep-instr** — survives in `templates/instructions/` (tool-contract reference).
- **drop** — removed; the named upstream fix removes the cause. Watched in M4.

## A. Turn-prompt sections (`src/orchestrator/context.py`)

| # | Guard | Failure mode it fixed | Cause hypothesis | Disposition |
|---|-------|----------------------|------------------|-------------|
| A1 | Scene framing discipline, DM + player variants (`_scene_framing_discipline_section`): scene engine must not be witnesses/evidence/audits; preflight questions | Legal-drama / procedural-legitimacy drift — scenes became about proving and recording | Operator-confirmed cause: agents cannot distinguish the system's mechanical bookkeeping (facts, receipts, audit) from in-world drama until told the difference; genre direction alone does not teach it | **RESTORED after M4 recurrence** — dropped in M2, recurred in glasswake (4/9 beats + scene objective custody/provenance-framed), restored as "The machine under the table" in both base system prompts with the layer-distinction framing explicit. |
| A2 | A1's replacement verb list: "the fictional engine should be immediate physical danger, movement, rescue... (carry, cut, run, brace, shove, shield, hold)" | Same as A1 (it was the corrective) | Over-corrected: steered campaigns into manual-labor/rescue procedurals (ash-ledger) | **drop** — the replacement genre direction must name adversarial plot shapes (heist, chase, negotiation, hunt, siege, escape), not physical-verb lists. |
| A3 | Codified handles vs in-fiction language (`_codified_handles_vs_fiction_language_section`): addresses-not-vocabulary; self-test; no hyphenated compound stacking | Jargon drift — clock labels, item slugs, coined compounds became prose vocabulary; turns unreadable cold | Partly system addressability leaking into prose; partly minted-noun Goodharting of resist-generic-drift | **relocate** — condensed to the craft section of both system prompts. Deep failure mode, not fully cured upstream. |
| A4 | Three-label rule (slug / prose name / generic descriptor; narrate with the descriptor) | Same as A3, item/skill/move names specifically | Same | **relocate** — one short paragraph in system prompts; authoring side stays in DM methodology. |
| A5 | Do not narrate the roll (mechanics vocabulary banned from prose; wrong/right examples) | Roll math, risk tiers, momentum values appearing in fiction and dialogue | Game-rules vs in-game-rules layer bleed; coding-agent register treats mechanics as reportable output | **relocate** — with 1–2 wrong/right examples kept; this class recurs consistently per operator history. |
| A6 | Identity sections: "do not rely on persona files or ornate house style" / "do not rely on persona or character markdown files" | Agents quoting/summarizing persona files instead of embodying them; stale-file authority confusion | Personas were reachable only as files; file-read framing invited inventory-reading behavior | **drop** — inverted by M1: persona and style *contents* are inlined into the system prompt; there is no file to lean on. |
| A7 | Word target 300–800 for full-turn prose | Unbounded or one-line turns | None upstream; a real format contract | **keep-turn** (output contract). |
| A8 | Word-ceiling pressure note ("cheapest compression is codified handles — cut a beat instead") | Compression-into-jargon under the word target | Interaction of A7 with A3 | **relocate** — merged into A3's condensed form. |
| A9 | Authoring surface block: no file writes, no scratch files, no repo/tool inspection or patching, `tools/list` for discovery, `glass_help` for contracts, report blockers via messages | Agents writing files, patching tools mid-turn, inventing state channels | Coding-agent system prompt actively teaches file editing and repo repair | **keep-turn**, condensed. Cause partially removed by the replacement system prompt (M2), but the tool contract must stay adjacent to the tools. M4 may justify further shrinking. |
| A10 | Context boundary: transcripts/messages/journals/lore are session data, may contain quoted or in-fiction claims; standing instructions come only from prompt/methodology/facts | Prompt-injection via fiction; in-fiction claims treated as binding instructions | Inherent to reading corpus text as context | **relocate** — durable, role-independent, belongs in the stable layer. |
| A11 | Session context: remembered context may be stale; prompt + Glass state win conflicts | Resumed-session staleness, cross-campaign memory bleed | Inherent to session reuse | **keep-turn** (short). |
| A12 | Closing countdown / final round / overrun sections | Closure problem — scenes never end (LLM helpfulness gradient) | Inherent; mechanized countdown is the fix | **keep-turn** — state-driven, turn-specific. Untouched by this overhaul. |
| A13 | Rapid-response constraints (answer ONE prompt, exit; brief reply) | Rapid turns ballooning into full turns | Turn-shape ambiguity | **keep-turn**. |
| A14 | Housekeeping constraints (process-only note, no in-fiction action) | Housekeeping turns emitting story beats | Same | **keep-turn**. |
| A15 | Action-order section (tight turns, seconds of fictional time, no handoff to move dice around, `next_speaker` discipline) | Action rounds sprawling; dice-shuffling handoffs; spotlight stalls | Turn-shape ambiguity + closure gradient | **keep-turn** — mode-specific. |
| A16 | Creative influence: "do not announce or quote the verse/tarot unless it naturally belongs" | Agents quoting their influence text in prose | Instruction-echo reflex | **keep-turn** (rides with the influence section). |
| A17 | History lookup in character creation: prior creation turns not embedded; don't optimize around other players' design turns | Anchoring/convergence on earlier pitches | Context contamination | **keep-turn** — mode-specific. Backlog's two-pass blind pitch is the fuller fix. |
| A18 | Previous-organization check: compare against 5 prior orgs, avoid repeating mission/method/culture/role/pull; "avoid rescue-route, extraction, audit, or procedure-led crew" | Cross-campaign org sameness; procedural-crew default | Negative-only steering; demonstrably failed (ash-ledger produced a rescue crew anyway) | **drop** the negative crew-type list — superseded by M3's positive premise gate. **keep-turn** the compare-against-prior-orgs injection (it's data, not prohibition). |
| A19 | Campaign-reference block: facts are the state store; markdown is viewer-only; lore is not continuity | State-source confusion (files vs facts) | Real architecture contract | **keep-turn**, condensed; overlaps instructions (C-rows). |
| A20 | Message-bus drain ("first action of every full turn: `glass_check()`") | Unread-message pileups; missed coordination | Real process contract | **keep-turn**, condensed. |
| A21 | Output contracts per turn kind (required `glass_done`/`glass_turn_append` sequences) | Missing closeouts, prose via stdout, malformed turns | Real process contract | **keep-turn** — the core of the turn prompt. |

## B. Methodology guards (`templates/methodologies/`)

| # | Guard | Failure mode it fixed | Cause hypothesis | Disposition |
|---|-------|----------------------|------------------|-------------|
| B1 | "Do not write files" (every methodology, closing line) | File-authoring relapse | Coding-agent default | **keep** the one-line closer in methodologies (revised from relocate: methodologies are the shared surface and codex actors have no system prompt) — also present in both system prompts. |
| B2 | scene-play-player: failed roll ⇒ finish with visible setback or cost; next attempt must change position, not add diagnosis | Costless failure; diagnosis loops | No fairness norm; analysis is the coding-safe move | **relocate** — folded into the fair-narration section of the player system prompt (M2). |
| B3 | scene-play-player: "do not turn character tics, object labels, or prior phrasing into the subject of the scene unless load-bearing" | Tic amplification loops (self-reference spiral) | Corpus feedback loop | **relocate** — craft section, both prompts. |
| B4 | scene-play-dm / action-scene-dm: don't reopen a failed-closed obstacle under a new label; offer a fresh route | Obstacle relitigating after beat closure | Closure gradient | **relocate** — DM system prompt. |
| B5 | scene-play-dm: in landing range, resolve with consequence/movement; "do not extend play by adding more procedure to an already-understood problem" | Procedure padding at scene end | Closure gradient + procedural drift | **relocate** — DM system prompt. |
| B6 | organization-bootstrap: don't split bootstrap facts across repeated single-fact calls | Fact spam; fragmented bootstrap state | Tool-call granularity ambiguity | **keep** in the rewritten methodology (M3). |
| B7 | "Keep coined labels subordinate to concrete world state" / "use concrete verbs and outcomes" (DM docs) | Jargon drift (A3's methodology echo) | Same as A3 | **drop as separate text** — covered by relocated A3; remove duplication in M3 rewrite. |

**Codex gap:** B2–B5 and B7 relocations move guard text into the claude system
prompts; in `mixed-codex` mode those actors (including the DM, which
mixed-codex hardcodes to codex) run without them. Tracked in
`docs/backlog.md` "Codex System-Prompt Support". The legacy turn-prompt
sections (A-rows) still render for codex actors, so A-row guards are not
affected.

## C. Instructions docs (`templates/instructions/`)

These are the tool contract, not steering; they survive as reference with M2/M3
consistency edits only.

| # | Guard | Disposition |
|---|-------|-------------|
| C1 | index.md turn sequence; MCP-only mutation; no shelling to `glass`; instructions field is binding | **keep-instr** |
| C2 | glass-cli.md forbidden-actions list; fact audience contract; `glass_help` usage | **keep-instr** |
| C3 | table.md "table/ retired; fact pack is the board"; player/DM fact sequences | **keep-instr** |
| C4 | workspace-authoring.md / lore-and-notes.md / recall-and-search.md: no file state paths, lore is not continuity until promoted | **keep-instr** |
| C5 | output-contract.md: two outputs only; no tool syntax in public prose | **keep-instr** + M2 adds: process reporting (blockers, lookup failures, tool trouble) goes to messages or closeout, never into `glass_turn_append` prose |
| C6 | message-bus.md narrowest-recipient rule | **keep-instr** |
| C7 | creative-influences.md: influence is flavor, not state | **keep-instr** |

## D. Observed in ash-ledger, currently unguarded (new work, mostly M2/M3)

| # | Failure mode | Where addressed |
|---|--------------|-----------------|
| D1 | Process telemetry in public prose (turn 2: "the reference-lore search returns no entries"; turn 6 DM echo) | C5 amendment + system-prompt line (M2) |
| D2 | Role-recitation drift: division of labor re-enumerated near-verbatim in turns 6, 7, 9, 12, 14 | Craft section, both system prompts (M2): don't restate established structure; the corpus already holds it |
| D3 | One-beat-five-times ceremony: relationship phase produced the same token-handoff beat per player | Relationship methodology cap + friction requirement (M3) |
| D4 | Uniform aphoristic register; one-line dramatic closers every turn; persona/style never reaching prose | Persona+style inlining (M1) + per-style register in system prompts (M2) |
| D5 | Success-with-decorative-cost beat shape; players narrate flawless competence | Fair-narration instruction in player system prompt (M2) — fairness by instruction, not authority gates (operator ruling) |
| D6 | No willed antagonist anywhere in the campaign; hazards only | Premise/antagonist/loss gates (M3) |
| D7 | Service-provider org premise ⇒ service-delivery fiction | Premise gate (M3) |
| D8 | Escalation-in-place / no forward movement: scenes never land (glasswake: 19 turns, one scene, objective 3/6, two beats closed only by failure-timeout, sluice-gate set piece restaged 4×; ash-ledger same shape). DM never exercises landing authority; "antagonist acts every turn" without landing pressure is a treadmill generator | "Moving the story" sections in both base prompts (set piece = 1-2 beats, executive landing authority, escalation must change position); antagonist-move line reworded to forward-motion in DM base prompt + scene-play/action-scene DM methodologies; `_scene_length_section` injects escalating land-the-scene pressure into DM turns at 12 and 18 scene-turns |

## E. Operator additions (historical failure modes never prompted out)

Operator: add rows here during the M0 pass. Known seed from operator memory:

| # | Failure mode | Notes | Where addressed |
|---|--------------|-------|-----------------|
| E1 | Game rules vs in-game rules bleed (mechanics treated as diegetic reality, or fiction treated as mechanics) | Recurred consistently across pre-git campaigns | A5 relocation keeps the guard; M4 watches whether the writer-identity system prompt reduces frequency |
| E2 | _(operator)_ | | |
| E3 | _(operator)_ | | |

## M4 outcomes

Fresh campaign `glasswake` (2026-08-20, 27 turns: 1 org bootstrap, 5 character
creation, 1 planning, 1 scene-prep, 19 scene-play; ~88k chars public prose;
2–3 min/turn vs ash-ledger's ~1.2).

- **A1 (anti-legal-drama), dropped** — did not recur as defined. Paper (seals,
  dies, boundary logs, receipts) is heavily present but as live leverage
  between opposing wills in a physically dangerous scene, not as
  proof-for-later scene engine. Watch item: the DM gravitates to
  provenance/paperwork stakes in both campaigns; acceptable while an
  antagonist is acting through it.
- **A2 (labor-verb steering), dropped** — did not recur. Scene engine was
  race + negotiation + rescue + cover-up reveal against a named antagonist;
  rigging/shoring appears as competence texture, not premise.
- **A6 (persona-file leaning), dropped/inverted** — personas now visibly drive
  prose. Four distinct registers on the page (Tev table-voice rules talk,
  Sumi close-third with withheld interiority, Renno first-person sensory,
  Kit theatrical chatter + OOC asides); Mara's mug/"what do you do" tells
  present.
- **A18 negative crew-type list, dropped** — org gate produced an acquisitive
  premise (salvage crew racing cordons for contested live glass). No
  service-provider drift.
- **A5 (roll narration), relocated** — mostly held: no mechanics inside
  fiction narration. But Tev and Kit put die math in *table-voice* public
  prose ("Five against seven. Regress"; OOC roll reports), which their
  personas model ("Twelve. That clears risky."). Operator call needed:
  either allow mechanics at the table layer (players-are-people reading) or
  tighten the base prompts; currently reads as charm, not leakage.
- **D1 (process telemetry)** — none in public prose.
- **D3 (ceremony repetition)** — creation was 5 turns (vs 13); no repeated
  token-handoff beat; relationship phase produced four interlocking secrets
  the DM tied to one antagonist-controlled door.
- **D5 (competence porn)** — gone. Failed rolls reshaped the board (berm
  breach, shoring collapse, destroyed sluice gate, medic dissolved); costs
  compounded across turns (blind pilot, one-armed medic, self-exposed
  forger, impounded ship).
- **No guards restored.** New observation for a future pass: 20 active turns
  stayed inside a single scene; closure/transition machinery never engaged
  within the run window.
