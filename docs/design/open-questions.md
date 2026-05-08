# Open Design Questions

Design questions that aren't yet settled. We've thought about them but want to see real sessions before committing. Listed here so they don't get lost.

These are different from [`scene-ending.md`](scene-ending.md): that doc has a worked design we've chosen to defer. The questions here haven't reached "design" yet — they need more shape before we commit.

---

## Speaker Selection Beyond the Mode Default

The mode determines the default speaker rule (initiative for combat, round-robin for exploration, DM-prompted for social, etc.). That handles the common case.

The unsettled part is when the default isn't right. Real tables have moments where:

- One player has something pointed to interject — a reaction, a callback, a piece of in-character backup — that the default order won't give them.
- The DM senses a player has been quiet too long and pulls them in.
- A previous turn ended on something specifically directed at one player and the round-robin would skip them.

A few candidate mechanisms have come up:

1. **DM picks freely.** The DM is the table's neutral arbiter — let them override the default rule whenever they want, in their own turn. Cheapest. Risk: the DM's continuation gradient might consistently pick the player who keeps the scene going, not the player who should go next.
2. **A neutral conscience agent.** A separate small invocation whose only job is "given the recent transcript, who should go next?" Independent of the DM's biases. Risk: another LLM call per turn, another decision layer to debug, duplicates work the DM is already doing.
3. **Player-flagged interjections.** Players signal in their prose ("I want to back Renno up before Kit rejects this") and the DM honors or doesn't. The mechanism is just reading what the player wrote — no schema, no `interjection_request:` field. Risk: the DM might miss the signal, or take it as narrative flavor rather than a turn-order request.

We've tentatively committed to #1 (DM picks freely, default rule otherwise) as the v1 path because it's cheapest and matches real GM behavior. #3 is a natural extension if #1 misroutes consistently. #2 is reserved for if both fail.

What we want to know from real sessions:

- Does the DM pick well, or do scenes drift toward whoever produces the most material?
- Do players ever try to interject and get ignored?
- Is there a class of moments where neither default-order nor DM-pick produces the right next speaker?

---

## Inter-Player Dialog (Table Talk) — partially settled

Real tables have continuous low-stakes dialog between players that doesn't fit the formal turn loop: IC asides, OOC banter, quick coordination, reactions to other players' moves.

**v1 path: the message bus.** `glass msg <type> <recipient> <body>` (see [`messaging.md`](messaging.md)) gives players durable, typed inter-agent communication that survives across turns and lands in the corpus. A player can `glass msg banter sumi "..."` mid-turn; Sumi sees it on her next turn via her inbox. The message bus also handles DM-private hints and party-wide instructions.

This solves most of the dialog need: the *content* of inter-player communication, the *typed indexing* for analysis, and the *per-recipient privacy* (file-permission-enforced).

**Still open: real-time-feeling reactions.** The bus is durable but turn-bounded. A truly reactive moment — A says something startling, B reacts immediately, before the DM proceeds — isn't expressible. Possible additions if real sessions show this matters:

1. **Addressed-reaction mini-invocations.** When a player addresses another player in their turn, the addressed player gets a tiny `claude -p` ("respond in 1-2 sentences, IC or OOC, or pass") before the formal turn order proceeds. Cost: extra invocations; risk of cascade.
2. **Inter-turn table-talk rounds.** The DM can call `glass talk-round` at moments worth reacting to. Each player gets a brief opt-in invocation. Bursty by design; cheap when not used.

What we want to know from real sessions:

- Does the message bus produce convincing dialog, or does it read as monologue with reply-letters?
- How often do players use `banter` and `instruction` types?
- Are there moments where the lack of real-time reaction makes a transcript feel artificial enough to justify mini-invocations?
- Is the in-character vs out-of-character split real-feeling without explicit support, or do agents collapse into one register?

---

## How to Use This Doc

When we run sessions, log specific moments where one of these questions hits a real failure. Don't generalize from one session — but if a class of failure repeats, that's the signal to commit a design.

When something here gets resolved, move it out of this doc. Either into the relevant design doc as a settled choice, or into the implementation as a feature. This file should shrink over time, not grow.
