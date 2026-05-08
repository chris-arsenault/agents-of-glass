---
title: Turn Verbs
---

# Turn Verbs

Words a player or DM can use in their prose to flag what kind of turn this is. **Reference, not validation.** The DM reads your prose either way; these just give the table a shared dialect.

Use them in your turn or in your OOC commentary: *"I'll spend my turn on an inquiry,"* *"this is reflection, no roll."* Or don't — the DM understands plain narration.

## The verbs

### action
Doing a thing in the world. Almost always involves a check. Advances time.
> *"Karrith hauls back the hammer and brings it down."*

### inquiry
Asking the DM about the world or scene state. Usually no check. Doesn't advance time.
> *"What does the patrol leader's posture look like — relaxed, ready?"*

### possibility
Exploring an option without committing. The DM can answer *yes that would work* / *no that wouldn't* / *partly*. No advance.
> *"Could I attune the wall's resonance from outside, or do I have to be in contact?"*

### planning
Coordinating with the party — usually IC, sometimes OOC. Advances time slowly. Often produces `banter` messages on the side.
> *"If Sumi distracts him at the bar, I could get into the back."*

### reflection
In-character thought. The PC's interiority. No external action. In the transcript but doesn't change the world.
> *"Karrith watches her hands and thinks about the last person who asked him for a Tuner's favor."*

### prepare
Declaring a preparatory ability. The setup is now true; the trigger fires later. The DM tracks it from your prose — there is no `prepared_actions` array.
> *"I'll spend this turn attuning a kinetic shield around Karrith. If anything swings on him, the shield fires."*

### address
Directing speech at another player's PC, or at an NPC. Often paired with a `banter` message to the addressed player out-of-band.
> *"Karrith turns to Mork: 'Cover the door, I'll check the body.'"*

## What's not in this list

- `wrap` — modes are ended via `glass mode end`, not in turn prose.
- `clarification` — players ask the DM clarifying questions in plain prose; we don't tag them.
- Specific moves like attack, persuade, prepare-shield — those live in [combat-moves.md](combat-moves.md) and [social-moves.md](social-moves.md).
