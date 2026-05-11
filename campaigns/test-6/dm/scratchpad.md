---
status: working
turn: 0001
---

# Scratchpad

## Where I am in campaign-planning

Turn 1 of probably 2–4. Done: the Question, the Scarcity, the player-facing campaign context, the working DM foundation. Next turn picks up at the party's organization.

- **Question:** *What do you owe what you find?*
- **Scarcity:** *Witnesses.*
- **Setting frame:** small salvage crew, working the Shear and Bloom edges. Day-forward, hopecore played straight.

## Lore + web pulls used (turn 1)

- **Lore pull:** Fermata Station — *sustained signal-band resonance shapes ringglass over time.* Salvage isn't neutral material recovery; what comes out has been *written into.*
- **Web pull:** the inherited voicemail — a signal that keeps arriving after the recipient is gone, and the question of who turns it off.

## Pulls budget remaining

- Roughly 3–5 more lore pulls and 2–3 more web pulls across the next 1–3 invocations.
- One per major output (org, factions block, NPCs block, opening arc).

## Next-turn queue (in methodology order)

1. Party organization — DM-only `dm/notes/organization.md` and player-facing `shared/lore/organization.md`. Salvage crew, named, with a base, a leader-not-PC, a fixer, an absent founder if it serves. Probably operating from a specific named locale rather than "Sithari."
2. Two to four factions with goals + clocks. Imports first, then campaign-specific layers.
3. Three to six NPCs, ≥1 antagonist with their own clock.
4. Two to four creatures.
5. Three to five named things — including the personal-comm shard with the recorded voice (the one that's been saying its message into the dark).
6. Three to five locales.
7. Ten atomic secrets.
8. Three to five hooks (DM-facing).
9. One or two short philosophy entries.
10. Opening arc via `glass arc create`.

## Lore imports planned (target 8–15)

`concepts/ringglass`, `concepts/tuners`, `concepts/stillwater`, `cosmology/resonance`, `locations/regions/the-shear`, `locations/landmarks/bloom-zones`, `npcs/factions/tempered-accord`, `npcs/factions/shear-compact`, `npcs/factions/echo-ledger-conclave`, `npcs/factions/coremark`, plus the crew's base locale once chosen. Eleven; room for a couple more.

## Authoring notes / mechanical findings

- `glass note write <path> --body "$VAR"` is the way to write to non-projected paths (`dm/foundation.md`, `context.md`, etc). The `--from <file>` flag silently exits 1 in this environment; use `--body "$(cat ...)"` instead.
- `dm/` itself isn't writable for new files via the FS; `dm/workspace/` is. Use `glass note write` for the canonical paths.
- Don't pre-author the prelude. Per the methodology, that comes after character creation.

## Things to refuse

- Tavern openers. Job-briefing first scenes. "Thorgrim" anything. Generic-fantasy NPC names. The Conclave hires you to retrieve an artifact. If I find myself there — rewrite.
