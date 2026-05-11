# Turn 3 — Tev

okay so. Round 1, character build. I'm doing my reading-then-building thing so this is going to take a minute, sorry in advance.

**Web pull.** I went non-adjacent into power line / overhead lineworker safety — pre-climb walkaround routines, back-feed risk, the tic tracer as a first-check instrument you don't trust but use anyway, and the maxim *"if you can't see it grounded, it's not grounded."* That's my anti-sameness fuel. (Also, fine, yes, I am an apprentice electrician, this is the texture I have. The methodology says specific and grounded. This is what's specific to me.)

**Concept.** Tek'iris Korr — gnome, Hab-Worlder, kite-wright on the Splitfork. Goes by Tek to the crew. Her thing is that she's losing her resonance sense earlier than she should — chronic Shear exposure on a previous job — and she's been hiding the dulling for two years by cross-checking everything with a handheld tic-tracer she built herself from a salvaged ringglass shard. She joined the Ledger Run because Mereth Kel doesn't ask for Conclave clearance, which Tek would fail. She stayed because of the refusal log; she's been keeping a private one for six years.

I wanted a gnome because the resonance-as-sensory-experience texture in the species page is what I want to actually inhabit — and then I wanted the *loss* of that as the story rather than the having of it. A gnome who used to feel the rig and now mostly feels the meter. The Tuner-shaped hole in her life is what makes the kite-wright work matter.

**Mechanics.** HP 8 (small, specialized). Attributes: superior focus (the walkaround takes patience), advanced finesse + ingenuity (rigger hands, builds her own instruments), rudimentary attunement (the loss is the story; this is the flaw I picked). Skills: virtuoso *lift-rig diagnostics*, artisan *jury-rigged meter-craft* and *climbing-the-spar*, apprentice *back-feed reading* (web-pull) and *refusal-logging*. Inventory: tic-tracer (signature, with the lineworker maxim inscribed inside the lid), rigger harness, private refusal log, an unsent letter to her dead aunt Mere who taught her the check. Signature move: *The walkaround* — slow loop around the kite before flight, back of the hand on the rigging, three independent readings (eyes, hand, meter), forty paces, won't be rushed.

**Traits** are in the intro. The one I'm proudest of is *touches every line with the back of the hand, not the palm* — because the palm she can't trust anymore. That's the kind of trait I want the table to start noticing without me having to flag it.

**Files committed.**
- `glass character new tek-iris-korr ...` — character row in Postgres with species, culture, archetype, org-role, bio, three goals, attributes, skills, HP 8, tags.
- `glass character bulk-update --from scratch/character-update.json` — added the four inventory items, the *Walkaround* signature move (uses my one level-1 slot), and rebuilt the public mirror.
- `glass sync apply players/tev/public` — committed `intro.md` and the regenerated `character.md` mirror. Both are party-readable now.
- One `glass msg table-talk party` at the top of the turn announcing the concept so nobody else accidentally builds the same shape.

Round 1 done from my side. Ready for round 2 when the methodology says we're there — I'll wait until all four intros are on the table before I write relationships.

Done.
