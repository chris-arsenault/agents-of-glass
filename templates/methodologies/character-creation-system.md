---
title: Character Creation — System Reference
status: authored
audience: players, dm
---

# Character Creation — System Reference

The mechanical layer for character creation. Read alongside
[`character-creation.md`](character-creation.md), which is the *process* (what
to do, in what order, with what creative pulls). This doc is the *rules* — the
numbers, budgets, and what each tier means in play.

## Species

Pick one. The five defined species are in [`shared/lore/species/`](../shared/lore/species/):

- **Elves** — vanished centuries ago. Rare, freighted, never casual. Talk to your DM if you want to play one.
- **Humans** — the demographic default. No resonance affinity, big cultural diversity.
- **Orcs** — physically powerful, materially attuned, communicatively direct.
- **Gnomes** — engineered, resonance-native, part-crystalline. Long-lived if maintained.
- **Fae** — engineered, spatially dislocated, dependent on coherence aids.

Read the species page. Don't skim. Each one has texture (orc pain response is muted; fae go diffuse when they rest; gnomes need lattice maintenance to age well) that shapes how a person from that species moves through the world. Pick the one whose texture you actually want to play with — not the one that sounds coolest.

Mechanical effects of species are narrative, not numerical. There's no orc-bonus-to-strength. A character's attribute spread reflects who *they* are, not what their species typically is.

## Culture

Orthogonal to species. Pick one of the defined cultures from [`shared/lore/cultures/`](../shared/lore/cultures/) — Sithari (formal register, two-part names), Hab-Worlder (clipped, hab-marker names), or Independent (catch-all) — or invent one grounded in the world if you have a strong reason. Names follow the cultural convention, not the species. A Sithari orc and a Sithari human share more naming pattern than two orcs from different cultures.

Pick a name that follows the convention exactly. See [`shared/lore/cultures/naming-conventions.md`](../shared/lore/cultures/naming-conventions.md). No "Thorgrim the Bold."

## Class / Role

There is no class system. Don't pick a class.

You invent what your character does — grounded in this world's professions and roles. Tuner, dock-runner, Conclave archivist, syndicate fixer, route-walker, hab medic, glass-rind harvester, Reconnection witness — anything that exists or could plausibly exist in the Kaleidos system. The org has needs (see [`campaign-planning.md`](campaign-planning.md) Output #2 for the party org's required capabilities); you fit one or more of those needs through *who your character is*, not by picking a label.

The character.md `archetype` field is one short string — a working description of what they are. "Lapsed Tuner." "Hab-bred mechanic with a Conclave grudge." "Ex-Sithari diplomat now running supplies." This is descriptive, not categorical.

## Attributes

Seven attributes: `vitality`, `finesse`, `focus`, `resolve`, `attunement`,
`ingenuity`, `presence`.

**Starting tier budget:**

- All seven default to `standard` (modifier 0).
- Bump **two** attributes to `advanced` (+1).
- Bump **one** attribute to `superior` (+2). *Optional* — you can stay at advanced-max if you want a more even character.
- Optionally drop **one** attribute to `rudimentary` (-2). This is a flaw, not a points trade. It buys you nothing mechanically; it gives you something to play.

`transcendent` is plot-only. You don't pick it.

The point of the budget is to make your character *bad at something*. Generic-fantasy drift makes characters competent everywhere; specificity comes from being notably good at two things and mediocre at the rest. Pick attribute strengths that match the character you're building, not the character you wish you could play.

### CLI

```bash
glass character new <id> --player <agent-id> --name "<name>" --archetype "<short-string>" \
    --hp 10 \
    --attribute focus=advanced \
    --attribute attunement=superior \
    --attribute presence=rudimentary
```

Unspecified attributes default to `standard`.

## Skills

Skills are arbitrary strings. There is no skill list. You declare what your character is good at by naming it.

**Starting skill budget:**

- Pick **5 skills**. Distribute across these tiers:
  - **One** at `virtuoso` (+2) — your single defining capability
  - **Two** at `artisan` (+1) — solid working skills
  - **Two** at `apprentice` (0) — competent, not specialized
- Skills you don't pick default to `fool` (-2). The character is *unskilled* at them, not just untrained — the check is actively harder.

`legend` (+4) is plot-only.

### Skill naming guidelines

- **Be specific.** "Resonance tuning" is fine. "Magic" is not.
- **Cover narratively, not exhaustively.** "Hab-network navigation" covers reading hab maps, knowing transit schedules, identifying which corridor is safe. Don't try to enumerate every situation.
- **Match the world's terminology.** Read the lore. The world has Tuners, Reconnection witnesses, route-walkers, glass-rind harvesters. Use those words where they fit.
- **Include at least one social/intellectual skill.** Combat-only character sheets get boring fast.
- **Include at least one skill that hints at where the character is from.** "Sithari court etiquette" tells the DM something. So does "Hab-Worlder air-quality assessment."

### CLI

```bash
glass character new <id> --player <agent-id> ... \
    --skill resonance-tuning=virtuoso \
    --skill hab-network-navigation=artisan \
    --skill diplomacy=artisan \
    --skill close-combat=apprentice \
    --skill mechanical-repair=apprentice
```

## HP and Momentum

**Starting HP:** 10 max. You can take **8** instead if your character is fragile or specialized for something other than physicality (a desk archivist, a frail elder, a fae with poor coherence aids); take **12** if your character is physically robust to the point of being a defining trait (an orc soldier, a vitality-superior survivor). The default is 10.

**Starting momentum:** 0, with floor -2 and ceiling +3. Players don't choose this.

The DM can adjust momentum out-of-band for narrative reasons.

## Starting Inventory

Pick **3-5 items**. One must be a **signature item** — something specific to this character, not generic gear. The rest are practical (tools of the trade) or sentimental (carried for a reason).

**Bad inventory:**

- "Sword, shield, rope, rations." (Generic.)
- "Resonance tools, knife, food." (Vague.)
- "Magic crystal, +1 vest." (Game-mechanical thinking.)

**Good inventory:**

- "Tuning fork from my master's shop, calibrated to a frequency I haven't heard hum back in fifteen years." (Signature, specific, narratively loaded.)
- "Hab-Worlder air-quality reader, second-hand, sticky button." (Practical with character.)
- "A child's drawing of me, folded in my breast pocket. Don't ask whose." (Sentimental, specific, refuses easy explanation.)
- "Sithari formal-register glove, left hand only. The right one was lost." (Cultural, specific, history.)
- "Resonance-laced fishing line, 12m. Doesn't catch fish. Catches other things." (World-grounded, ambiguous.)

You're describing items, not stat-blocking them. The DM decides if/when an item matters mechanically.

Items may have free-text effect tags when that helps the table remember how
they matter:

```yaml
effect_tags:
  - "May justify pressure against exposed human-scale targets."
  - "Can constrain a creature if the fiction supports getting the net around it."
```

The inventory CLI can store these tags with `--effect-tag`, but no command
interprets them mechanically. They are prompts for honest play: cite them when
they make sense, ignore them when they do not.

### CLI

After `glass character new`, add inventory:

```bash
glass character inventory-add <id> tuning-fork --qty 1
glass character inventory-add <id> resonance-laced-net --qty 1 \
  --effect-tag "Can constrain a creature if the fiction supports getting the net around it."
```

Item ids are short slugs; full descriptions live in the character's intro.md or the character.md notes section.

## Tags

The character.md `tags` field holds a few short labels — `[tuner, ringside-born]`-style — that the DM can use to filter or reference. Pick 2-4 tags that capture demographic facts (species, culture, profession, hab-of-origin). These are search keys, not personality.

## What's Not Here

Deliberately not in the system:

- **Hit points by class** — there are no classes.
- **Spell slots / abilities** — recurring techniques belong in signature moves, not a power list.
- **Damage types / armor** — HP is a number; damage is coarse pressure impact plus narration.
- **Currency / money** — narrate around it; if it matters, the DM tracks it as a tag.
- **XP / leveling** — no advancement system at character creation. Multi-session arcs may add one.
- **Saves / resistances** — covered by attribute checks under the relevant attribute.
- **Alignment** — characters have specific traits and goals; no axis system.

When in doubt, narrate it instead of mechanizing it.
