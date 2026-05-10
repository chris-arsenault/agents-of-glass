# Resist Generic Drift

LLMs default to generic fantasy. Sessions will drift there if we don't actively resist.

## The Failure Mode

The training data is saturated with D&D, Tolkien, generic medieval, MMO templates. When an LLM is asked to "play a TTRPG," its default trajectory is toward those templates: orc raiders, dragon hoards, "Thorgrim the Bold," dimly-lit taverns, mysterious cloaked figures, ancient evils stirring. Even with a specific setting briefed in the prompt, the gravitational pull of generic fantasy is constant.

In a single-prompt narrative engine this is annoying. In a multi-agent loop running for hundreds of turns, it's existential. Each turn nudges the world half a step toward the average; over a session, the world *becomes* average. Over a campaign, the corpus is indistinguishable from any other LLM-narrated fantasy text.

We are not building a generic fantasy simulation. The Glass Frontier is **serious hopecore** — Firefly + Iain M. Banks Culture + Sanderson-grade hard systems. Crystal-saturated post-collapse sci-fantasy. Habs governed by jazz, presented matter-of-factly. Resonance with defined bands and bandwidths and supply chains. Sithari, the Tempered Accord, Coremark, ringglass, Tuners — these are *specific* names with *specific* connotations. Generic fantasy is not a different aesthetic; it is the failure state.

## How Drift Looks in a Transcript

- An NPC suddenly has a generic-fantasy name ("Aldric the Wise") instead of a Sithari two-part name, a hab-worker clipped functional name, an orcish mononym, a gnomish apostrophe-compound, etc.
- The party heads to "the tavern" or "the inn" instead of a specific named locale grounded in this world.
- A combat scene reaches for "the wizard casts a spell" instead of resonance-tuning, ringglass arrays, the Tuner's actual mid-bandwidth practice.
- The DM narrates "an ancient evil stirs" instead of something specific (the Bloom is a contained zone with specific effects; the Adversary is referenced with restraint, not invoked).
- A player describes their character as "a half-elf rogue with a tragic past" instead of building from the world's actual species/culture/archetype space.
- "Energy," "magic," "the wizard channels," "ancient power" — vocabulary that fits anywhere is vocabulary that fits nowhere.

These are all signals. They mean the agents have stopped writing in *this* world.

## The Defenses

We don't have a single layer that solves this. We need several, applied continuously:

**Specificity injection at every TURN_START.** The orchestrator surfaces specific lore in every turn's context — relevant entities, recent corpus details, table state, SRD terms, and creative influences that fit the moment. The agent is anchored to specific names and specific concepts before they start writing.

**The people files.** Mara, Tev, Sumi, Renno, Kit each have a specific voice and specific tastes. A player file that says "loves Sithari political maneuvering, hates anything that smells like generic fantasy" is a defense. A persona-level "the optimizer" is not. (See [`/docs/design/agents.md`](../design/agents.md).)

**Public rules and lore as anchors.** The SRD and lore docs are populated with world-specific terms — `kite-flight`, `attunement`, `momentum`, `band`, `bandwidth` — instead of `mana`, `levitation`, `concentration`. Agents reaching for rules, examples, and lore find the world, not generic fantasy.

**The DM's gatekeeper role.** When a player drafts a generic-fantasy NPC and proposes it via `glass note propose`, the DM rejects or rewrites. Canonization is the choke point against generic content polluting the campaign.

**Corpus review.** Periodic passes over the transcript looking for slop signals — generic names, off-world tropes, stock phrases. Caught early, we adjust prompts and people files; caught late, we tag the session as a "drift example" and study what went wrong.

**Naming the failure.** The DM and players are written as people who *know* generic fantasy is a thing they want to avoid, the same way an actual GM running a sci-fantasy game is consciously not running D&D. Putting "I hate when sessions drift toward generic fantasy" in a person file makes it a thing the agent actively resists.

## What Specificity Looks Like

| Generic | Specific |
|---------|----------|
| "Thorgrim the Bold" | A Sithari two-part name, a hab-worker clipped functional name, an orcish mononym, a fae epithet — pick a culture and commit |
| "the tavern" | a named place with one resonance-shaped detail (the bar's lights flicker on a Tuner's old mid-bandwidth array) |
| "the wizard casts fire" | a Tuner working a kinetic-band ringglass array, with cost and a tell |
| "an ancient evil stirs" | the Bloom is a contained zone with specific effects; the Adversary is referenced with restraint, not invoked |
| "a half-elf rogue with a tragic past" | a Sitharian human raised in the Shear, kite-flying tic, Conclave dropout |
| "magic energy" | resonance, a specific band, a specific bandwidth, a specific cost |

The right side is not better because it has more words. It's better because every word lands in *this world* and not in any other.

## A Reading

When in doubt about whether something feels generic, read [`/home/dev/repos/the-glass-frontier-lore/player/cosmology/resonance.md`](../../../the-glass-frontier-lore/player/cosmology/resonance.md). Note how concrete it is. Specific bands. Specific bandwidths. Specific costs. No "energy," no "magic," no "the user channels their power." The lore plays it straight; the prose is dense with this-world detail.

That is the bar. Every turn the agents write should be defensible against that standard.

## Companion Principles

- [`codify-only-what-drifts.md`](codify-only-what-drifts.md) — codify the drift-prone (numbers, names, dice). This principle is the prose-side companion: the prose itself drifts, and we resist with specificity.
- [`transcripts-as-corpus.md`](transcripts-as-corpus.md) — the corpus is the product. Generic transcripts are a degraded product, even if every turn is mechanically correct.
- [`goals-and-motivation.md`](goals-and-motivation.md) — the central question is whether multi-agent autonomy produces *richer* fiction than single-prompt generation. Generic drift is the failure case for that question.
