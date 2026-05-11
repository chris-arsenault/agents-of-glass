# Scene: caulden-rack-setup

Type: scene-play

## Turn 67 - dm (dm) - scene-prep, caulden-rack-setup

---
turn_id: test-7-t0067
mode: scene-prep
scene: caulden-rack-setup
actor: dm
---

# Turn 67 — Mara

The prelude is closed. The table moves to campaign proper.

Scene prepped: **caulden-rack-setup**, `scene-play` mode, active.

---

The Glasswake reclaimed dock, departure morning.

Most of the manifest is already loaded. The ringglass on the south wall hums as the crane sets down the last ordinary crate — pitch rising as the crane lifts, pitch falling as it sets — and the dock crews count under their breath. Three this morning.

Mereth came in from the berth side a few minutes ago. She set the refusal log on the desk corner before she said anything else. The opening of the book was the first thing.

Halvi is at the window desk with the manifest tablet. Window open. The previous day's tablet is on the shelf, different shelf than yesterday. Ev is near the door — already stamped the manifest without visibly writing anything, paperwork in a clean stack.

The last item on the manifest arrived twenty minutes late.

A small Hab-Worlder named Per Vask pushed a hand-cart through the dock bay door with a microcavity rack from Caulden Refinery in the Sable Crescent — standard tray, twelve cells, foreman-sealed, year-mark manifest, destination Hab Meridian receiving dock. His dispatch slip says he caught a delayed kite from Sable two nights ago. He looks tired. He handed the rack to Halvi with the delivery form and the foreman's seal in good order.

He has not been asked to stay.

He is still here. Standing near the door. Watching Halvi run the clean-ledger cross-check.

Halvi is running it in front of him. Because he is watching.

The rack is in the Tuner-cradle now. Sealed, humming at the standard low frequency of a charged microcavity rack.

Departure in two hours.

---

*What do you do?*

---

**Table:** `table/scene.md` has the full scene kickoff. `table/index.md` has the at-a-glance. Scene files committed to `arcs/caulden-rack/scenes/caulden-rack-setup/`.

Mode advanced: `scene-prep` closed → `scene-play` live.

> mode start scene-prep @ caulden-rack-setup
> handoff -> dm
> scene create: caulden-rack-setup (scene-play)
> sync applied 5 workspace operation(s)
> mode end scene-prep @ caulden-rack-setup
> mode start scene-play @ caulden-rack-setup

## Turn 68 - tev (player) - scene-play, caulden-rack-setup

Okay so — Tek'iris moves to the Tuner-cradle while Halvi's cross-check is still running.

Not intrusively. She's crew; she has every reason to be near the cargo. She sets a hand lightly on the cradle frame — cold metal through her work gloves — and pulls the tic-tracer from her vest pocket with the other hand. The pearwood casing is warm from sitting against her ribs all morning.

She opens the lid. The salvaged ringglass shard inside begins its quiet read without prompting. First beep, soft.

She holds the tracer near the rack's upper face, then sweeps it along the cell line slow and even. Twelve cells. Foreman-sealed. Humming at what would pass for a standard delivery frequency on a charged microcavity rack out of Caulden. At a quick listen, at a glance, nothing wrong.

But the charge distribution isn't standard.

Cells three and four from the left end are running a half-step higher than the rest — not alarm-high, not even technically wrong, just off. Like a lattice that was partially depleted and brought back up in the field. Or like those two cells were opened after the foreman's seal went on, then resealed.

Or like nothing. Like Caulden Refinery calibrates tighter than she's used to and she's reading too much into a frequency variance that's still inside tolerance.

She closes the tracer. The inscription on the inside of the lid is by feel by now: *if you can't see it grounded, it's not grounded.*

She doesn't move away from the cradle. She doesn't say anything. The manifest tablet in Halvi's hands, Per Vask still near the door with his arms loose at his sides, the dispatch slip probably folded in his coat — she takes all of it in without turning her head. The ringglass on the south wall hums low. Three cranes this morning, the dock crews said.

Two hours to departure.

---

*Breakthrough on lift-rig-diagnostics / focus, controlled risk (2d6 = 12, total 18, margin +11). Tek'iris read a specific charge variance in cells three and four. Momentum at ceiling (3). Scene summary updated.*

> roll lift-rig-diagnostics (focus) @ controlled: 18 vs 7 -> breakthrough (+2 to +3 momentum)
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> handoff -> dm

## Turn 69 - dm (dm) - scene-play, caulden-rack-setup

---
turn_id: test-7-t0069
mode: scene-play
scene: caulden-rack-setup
actor: dm
---

# Turn 69 — Mara

The ringglass on the south wall hums. Standard frequency. Three this morning.

Halvi sets the manifest tablet face-down on the window desk. Twelve cells accounted for. Foreman seal confirmed. Clean ledger. The refusal log on the desk corner hasn't been opened.

Per Vask exhales.

Just a breath. The kind a person takes when the thing they were watching for is over. He picks up the empty hand-cart handle, turns it toward the dock bay door, and then stops, one step in, not moving.

Mereth is still near the berth-side door. She hasn't looked at the manifest. She's looking at the door Per Vask is stopped in front of.

The rack hums in the Tuner-cradle.

Two hours to departure.

> tek-iris-korr xp +1 (6 -> 7, level 1)
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> table write campaigns/test-7/table/index.md
> sync applied 1 workspace operation(s)

## Turn 70 - tev (player) - scene-play, caulden-rack-setup

Tek'iris stayed at the Tuner-cradle longer than the read required.

She set the tic-tracer on the edge of the housing — lid open — and looked at the rack again. Not at the whole rack. At the third and fourth cells from the left. She ran two fingers down the edge of cell three, not to feel anything, just to have a reason to be standing there. The tracer sat quiet in her hand. It had already said what it had to say.

Per Vask had not moved.

She picked up the tracer, closed it, and crossed to Mereth.

She stopped close enough that her voice would stay below the ringglass hum from the south wall, her back partway to the room.

"Three and four," she said. "Running a half-step high. Consistent pattern, both cells." She let that land. "That's not how a standard rack distributes after a run out of the Crescent. It's how it distributes if someone opened two cells after the foreman sealed it and didn't even it back out."

She didn't look at Per Vask. She held the tracer without opening it. If Mereth wanted to see the read, it was there.

"Halvi's signed it clean. That's her call on the ledger side." Her voice stayed flat. "I'm telling you what the rig says."

She waited. She was not certain what she was asking Mereth to do, or if she was asking for anything. The rack was sealed. Halvi had signed. Per Vask was still at the door, and he had exhaled when the manifest cleared, and he was still at the door.

Two hours to departure.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 71 - sumi (player) - scene-play, caulden-rack-setup

Drova moves to Halvi's desk — no announcement, no ask. The delivery form and Per Vask's dispatch slip are still there beside the signed tablet. She takes both and carries them to the window edge where the morning light comes low and flat off the dock wall.

She sets them nearly flat and tilts them into the raking light. Holds them still. The loupe stays in her pocket. She tilts first.

In the ghost-light, the paper holds its history.

The dispatch slip carries an indent trace from a page that once rested above it — pressed in with enough force to leave a record. Most of the impression is smeared past reading, the top page offset when it was written. But the rack serial field in the impression is clean: five characters, and the first two digits at the end are wrong. The form on the desk says 7C-AA9. The indent in the paper says 7C-AA7.

Two racks. One set of papers.

She sets the forms face-up on the desk and straightens. She does not look at the rack. The loupe stays in her hand, closed.

Across the room, Per Vask has stopped watching Halvi's tablet. He is watching Drova's hands.

She looks at Mereth across the room and speaks at the volume you use when you've accepted that the other person will know something passed, even if he can't hear the words.

"There's a second serial on the dispatch slip. Ghost impression from a page above. The indent says 7C-AA7. The form says 7C-AA9."

She leaves the papers on Halvi's desk.

She does not move toward the rack or toward Per Vask. She waits, loupe in hand, and lets Mereth decide what comes next.

> roll reading what's been redacted from a paper record (focus) @ standard: 12 vs 8 -> breakthrough (-1 to +1 momentum) -> delivery form from Per Vask — look for post-seal access: altered timestamps, indentation traces, signature pressure inconsistency
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 72 - renno (player) - scene-play, caulden-rack-setup

Fei Mern has not moved far from the cradle since Tek'iris stepped back. She holds her position the way she holds a threshold — present, not pressing.

She takes the resonance meter from her bag without looking at it. The sweep is part of her role here: first-pass clearance on cargo before departure. She's done it on every load this run. There's nothing unusual about the gesture.

She passes the meter face-down along the rack, left to right. The ringglass hums somewhere behind her on the south wall. Her hands are level.

Cells one and two: nothing that stops her.

Three and four: the meter stalls in her attention. Not loudly — it gives her the edge of something, the way a waystation corridor gives her the residue of a second use it wasn't officially put to. Not transit vibration, not ordinary settling. The impression is of something handled, examined, closed again. The two cells feel like a door someone went through carefully and tried to leave as they found it.

She holds the meter there for three seconds. Then she moves it to five, six. Completes the sweep. Closes the meter.

Per Vask has not moved from the dock bay door. His eyes have been on her hands since she opened the case.

Fei Mern looks at Mereth. She doesn't speak. She tips her chin once — the small kind, barely a movement. What it means: *I found the same wall they found.* Then she looks back at the rack.

The Mernhab cuffs haven't hummed. She hasn't gone diffuse. She has the meter reading, the impression of post-seal handling, and Per Vask's attention. Those are three things she holds without saying.

She does not look at Per Vask.

> roll diffuse-state waystation reading (attunement) @ standard: 9 vs 8 -> advance (+1 to +2 momentum)
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 73 - kit (player) - scene-play, caulden-rack-setup

The rack is in the cradle. Three people have put readings on cells three and four. Bren has been present for all of it — close enough to the rigging to look occupied, far enough to stay out of the work.

Per Vask hasn't moved.

She knows what a delayed kite does to a schedule. She grew up on the ringfall plain west of Span Nine; she's spent more nights in loading bays waiting on manifests than she can count. She knows the particular patience of someone who can't leave yet, who's waiting on a result they're not going to get to see directly.

She walks over.

"You caught a delayed kite two nights ago."

Not a question. Just placing herself as someone who's read the slip, who knows what that kind of disruption costs — an acknowledgment between two hab-worlders who understand how the logistics work.

Per Vask looks at her the way you look at someone who's just confirmed what you were hoping wasn't confirmed. He sets the hand-cart upright. One hand rests flat on the grip.

"I did." A pause that isn't quite a hesitation. "Dispatch said to wait for in-person clearance on delivery."

He glances toward the cradle. Then back at her. His eyes aren't reading her anymore — she crossed something and he's landed on the other side of it. The pretense of lingering-by-accident is gone. He has instructions.

Bren holds where she is. She doesn't look at Mereth.

She opened a door she didn't have the key for. Collapse reads like that: the thing you said that told the other person everything they needed to know about how much you know. Now Per Vask is standing in the room with no reason left to keep waiting quietly, and his instruction is *in-person clearance*, which means someone is expecting a signal from him.

Two hours to departure.

---

*Roll: dockyard-talk + presence, standard risk — collapse. Per Vask's pretense is down; he has explicit instructions from dispatch to wait for in-person clearance, and his attention has moved to the rack. Momentum: -2 (floor, unchanged).*

> roll dockyard-talk (presence) @ standard: 2 vs 8 -> collapse (-2 to -2 momentum)
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 74 - dm (dm) - scene-play, caulden-rack-setup

---
turn_id: test-7-t0074
mode: scene-play
scene: caulden-rack-setup
actor: dm
---

# Turn 74 — Mara

Mereth crossed the office.

She came around the corner of Halvi's desk without hurrying — past the papers Drova had left face-up on the window ledge, past the cradle with the rack still humming in it — toward the dock bay door. She stopped next to Bren. Not in front of Per Vask. Beside Bren.

The three of them: Per Vask with his hand on the cart grip, Bren holding her ground, Mereth standing alongside her.

Mereth looked at Per Vask. "The slip shows 7C-AA7 in the impression. Your delivery form reads 7C-AA9."

Per Vask was quiet for a moment. His eyes went to the cradle — just a glance, the kind that can't stop itself — and then back to her.

"I was told the rack would be in order," he said.

Mereth waited.

He shifted his weight, just slightly, and his grip on the cart handle adjusted without going anywhere. "The clearance I'm here for." He stopped. He had landed on the far side of a decision. "The people who sent me — they need to know the rack made delivery."

The refusal log was on the desk corner. Still unopened.

The ringglass on the south wall hummed at standard frequency. Three this morning.

Two hours to departure.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> table write campaigns/test-7/table/index.md
> sync applied 2 workspace operation(s)

## Turn 75 - tev (player) - scene-play, caulden-rack-setup

Tek'iris crossed to the rack.

She didn't look at Per Vask. She opened the tic-tracer — the click of the casing lid was the only sound she made — and brought the instrument close to the face of the cradle. Not a sweep. She pressed the reading tip to the seam directly above cell three and held still.

The needle moved. She watched it. Then she shifted to cell four and held again.

Forty seconds, maybe less. She could feel Halvi not looking up from the desk, and Per Vask not moving from the door.

She closed the tracer.

"These two cells aren't running high." She tapped the seam above three with one knuckle — the gesture she used when she wanted someone to understand the geometry and not just the number. "The profile isn't a variance from the others. It's a different class entirely. High-density resonance, not microcavity." She looked at Mereth across the room. "The manifest says microcavity throughout. These two aren't."

She put the tic-tracer back in her harness pocket and left her hand there. She was not going to sign anything that said otherwise.

The rack was sealed and she had not touched the seal. The read was from the exterior. Whatever was inside those two cells, it had told her what it was without being asked.

She waited. Per Vask was still at the door. Mereth had the refusal log on the desk corner.

> roll lift-rig-diagnostics (focus) @ standard: 14 vs 8 -> breakthrough (+3 to +3 momentum) -> determine what happened to cells 3 and 4 from exterior resonance read
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> handoff -> dm

## Turn 76 - dm (dm) - scene-play, caulden-rack-setup

---
turn_id: test-7-t0076
mode: scene-play
scene: caulden-rack-setup
actor: dm
---

# Turn 76 — Mara

Per Vask looked at Tek'iris for one beat.

Then he reached inside his coat and took out a flat plate — palm-sized, laminate, a recessed stud on one edge. The kind of confirmation token a hab-courier carries when the job is one-way: press the stud, the seal burns, a pulse goes out over the dispatch frequency. No reply path.

He held it in both hands and looked at Mereth. Not at Halvi. Not at the rack.

"I was told the rack would be in order." Not an excuse. The thing he knew. "The people I work for need to know it arrived. That's what I was sent here to do. I'm going to send that signal."

He had not pressed the stud. His thumbs were clear of it.

The ringglass on the south wall hummed at standard frequency. The refusal log was still on the desk corner. Tek'iris's hand was still in her harness pocket.

What do you do?

> table write campaigns/test-7/table/index.md
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> sync applied 1 workspace operation(s)

## Turn 77 - tev (player) - scene-play, caulden-rack-setup

Tek'iris had not moved since she named the cell class to the room.

Now she did. Not toward the rack. Not toward Mereth. Toward Per Vask.

She pulled the private refusal log from her harness pocket — the small bound book she kept in the left-side pocket, next to the two carabiners she didn't trust. She held it open, low, where he could see it without either of them having to acknowledge the room. Dates in the left margin. One-line reasons in cramped field notation. Some entries crossed out. Most not.

She said: "Two cells in that rack aren't microcavity. Your slip says so. The rig read says so." She didn't look at the plate in his hand. "They told you the rack would be in order. It isn't."

She nodded once, very slightly, toward the refusal log on Mereth's desk — the one that had been sitting on the corner since before anyone said a word.

"That log is for when the job isn't what they said." She held her own book up a fraction of an inch, not offering it to him, just making sure he saw what she was holding. "You can add your name to one. It's not the same as sending a signal."

She closed the book and put it back in the left-side pocket.

She did not step away. She did not wait for him to respond. She stood there with her hand resting on the pocket flap and let him look at whatever he was going to look at.

Per Vask's thumbs were still clear of the stud.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 78 - sumi (player) - scene-play, caulden-rack-setup

Drova did not move while Tek'iris stood at the dock bay door with her hand resting on her harness pocket. She waited until Tek'iris stepped back.

Then she picked up the dispatch slip from the window desk — Per Vask's original, still flat under her loupe — and walked toward him.

Not to the refusal log. Not to the rack. To him.

She held the slip out and set it on the doorframe ledge at a height he could read without looking away from the room. She positioned her inkless pen in the crease of the paper, angled so the overhead light raked across the surface. The impression was visible: 7C-AA7, faint but legible, the shadow of the page that had been above this one when someone made his copy.

She said: "Your principals told you the rack would be in order."

She didn't look at him. She looked at the document.

"The indent here says 7C-AA7. The form says 7C-AA9." She moved the pen a fraction, holding the shadow. "The rack in the cradle is 7C-AA9."

She picked the pen up and turned it once in her fingers.

"When you press that stud — you're confirming 7C-AA9 arrived." She looked up at him for the first time. "Which serial are your principals waiting for?"

She took the slip off the ledge and walked back to the window desk. Set it down next to the loupe. She didn't wait for his answer — or rather, she set the question down the way she'd set the document down, and left it in the room alongside everything else.

Per Vask's thumbs were still clear of the stud.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 79 - renno (player) - scene-play, caulden-rack-setup

Fei Mern hadn't moved since the chin-tilt. She'd been at the cradle's edge, watching Per Vask's hands, letting the others work through what they'd found.

Drova's question was still in the room without an answer. The thumbs were still clear of the stud.

She crossed back to the rack. Not to Per Vask — to the cradle. She lifted the resonance meter and ran it across cells one through six again, slowly. The meter chattered at three and four. Same read. She held the position at each cell for three full seconds — long enough for anyone watching to understand this was deliberate.

Then she unclipped the field interpreter tablet and logged it. First-person witness render: cells three and four, high-density resonance class, deviation from manifest specification, date, time, location, her initials. She wrote it out in longhand rather than shorthand — readable to anyone in the room who could read standard.

She turned and walked toward the dock bay door. Stopped eight feet from Per Vask. Didn't close the distance further. Held the tablet open where he could read it without moving toward her.

"It's filed now." Her voice carried the register she used when she wasn't performing volume. "Whatever the stud sends — this came first."

She let him look at it.

"A waystation witness render runs ahead of a delivery signal. That's how the log works — not something I decided." She tilted the tablet slightly, in case the angle wasn't right. "When this crosses a waystation, the anomaly is already in the record before the confirmation landed."

She didn't say what he should do with that. She was hab-worlder. She understood what it meant to be dispatched with bad information and to be standing in the wrong room when the account came due.

She lowered the tablet, reclipped it to her belt, and stepped back to the cradle.

The ringglass on the south wall hummed low as the dock crane cable ran back to rest.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 80 - kit (player) - scene-play, caulden-rack-setup

Bren hadn't moved since Mereth came to stand beside her. Two feet from Per Vask. Close enough to see his thumbs.

The room had given him everything it had: the cells, the serial, Tek'iris's log, the witness render on Fei Mern's tablet. Drova's question was still floating — *which serial were your principals waiting for?* — and nobody had answered it for him.

Bren didn't answer it either.

"What were you told you were delivering?"

Not an accusation. She'd run courier jobs out of Span Nine before the Splitfork — two years of carrying things she hadn't packed and signing for manifests she hadn't written. She knew how dispatch worked. She knew the face of a person who was dispatched with one thing and handed another. She wasn't asking him to give up his principals. She was asking what he knew, because if he'd been told 7C-AA7 and he pressed that stud for 7C-AA9, those weren't the same signal — and whoever was waiting on the other end would read the discrepancy before he was out of the building.

She didn't say all of that. She just asked.

Per Vask's thumbs were still clear of the stud. She waited.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 81 - dm (dm) - scene-play, caulden-rack-setup

Per Vask's eyes moved to Bren's face when she asked. Then to the dispatch slip in Drova's hands. Then to Fei's tablet — the witness render still open where anyone could read it, date and time and initials in longhand.

He stood there for a few seconds.

Then he pocketed the confirmation plate. Just the sound of the case closing, and his hand going back to his side. No explanation. No concession. Nothing added to the room.

He picked up his dispatch bag from beside the dock bay door, crossed the office without looking at the rack, and went out.

The door settled shut behind him. The dock outside was quiet. No pulse. No signal.

Mereth had been standing beside Bren through the last of it. She let a beat go — just a breath. Then she looked at the refusal log still on the desk corner.

She had not touched it. It was still there. The rack was still in the cradle. Two hours to departure.

> scene closing down (~1 round(s) left)
> table write campaigns/test-7/table/index.md
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> sync applied 3 workspace operation(s)

## Turn 82 - tev (player) - scene-play, caulden-rack-setup

Tek'iris is still standing near the cradle when the dock bay door closes behind Per Vask.

She waits three seconds. Then she crosses to the desk corner and opens Mereth's refusal log.

Not to read it — she keeps her thumb on the cover, barely cracked. She's looking for the last date. She finds it: a run three months back. One line, tight. She does not read the line.

She sets the log back down with that page open, turns to her harness pocket, and pulls out her own. Hers goes down beside it. Open to the last entry. She crossed out the most recent one after the job was done; she still hasn't decided if that was the right call.

She does not look at Mereth. She looks at the rack.

"Two hours," she says. Not to anyone, or to everyone. "That's the question now."

The tic-tracer is still in her pocket. The seal on cells three and four is unbroken. She identified the class from outside — that read is in her hand, in Fei Mern's witness render, in the shape of the thing as it sits in the cradle. The seal being unbroken does not change what is inside it.

She is not going to tell Mereth to file. She is not the captain. But she has the kind of log that gets looked at after things go wrong, and she set it next to the one that gets looked at after things go wrong, and the page is open.

The ringglass on the south wall hums. The dock crane somewhere above the bay is settling something. Pitch rising, pitch falling.

Two hours.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 83 - sumi (player) - scene-play, caulden-rack-setup

Drova crosses to the desk corner and picks up the refusal log. She doesn't look at Tek'iris or Mereth before she does it — just picks it up, the way you pick up a tool that has a job.

She carries it to the window desk. Sets her loupe set at the angle she works in. Opens the log to the current date.

The page is blank.

She uncaps the good pen — the one that leaves a clean impression on the page below — and begins to write. Not quickly, not slowly. The practiced pace of someone who has done this hundreds of times at a Conclave intake desk in Thornvault and knows what weight each word carries.

She documents the serial discrepancy first. Delivery form: 7C-AA9. Ghost indent from the page above: 7C-AA7. Method noted. Then the cell classification across three independent reads — tic-tracer, resonance meter, close exterior field read — each attributed. High-density resonance in positions three and four. Manifest states microcavity throughout. Foreman's seal unbroken at time of examination.

She names Per Vask as the delivery agent: hab-worlder, principals waiting on delivery signal, signal not sent as of the time of this entry. She writes the date. She writes the location: Glasswake reclaimed dock. She writes her name in the clerk's signature box and draws a single line underneath it.

Then she reads it back once, the way she was trained.

"Filed under document deviation," she says to the room, not loud. "Both serials, three independent reads, the delivery agent named. If this goes anywhere legal, the notation holds."

She sets the log back on the desk corner. Not handed to Mereth, not filed away — just returned to where it was, now with something written inside it.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 84 - renno (player) - scene-play, caulden-rack-setup

Fei Mern was still near the bench where the resonance meter had been sitting — the needle not yet zeroed. She picked it up and zeroed it. Old Mernhab habit: calibration tools don't sit half-read.

Then she walked to the desk corner.

Drova's entry was three lines. Serial discrepancy, cell class deviation, Per Vask named, signal not sent, three reads each attributed. The third attribution had her name in it — second resonance meter sweep, repeated, first-person witness render, initials on file. She took the stylus from her tablet pocket and put her initials in the margin beside that line, in witness shorthand. Not adding anything. Confirming what was already written.

She unclipped the field interpreter tablet from her harness and set it open on the desk next to the refusal log. The wax held clearly: cells three and four, high-density resonance class, deviation from manifest, date, time, location, initials, longhand. The render and the log entry were the same packet now. Anyone who opened one would find the other.

She didn't close the log. That was Mereth's.

The coherence-aid cuffs were warm against her wrists — residual warmth from a long session near the cradle. She pressed her left wrist to the inside edge the way she always did at the end of a sweep, checking for the small slip that meant she'd gone further out than she knew. It was clean. She was solid.

Two hours to departure. The record existed regardless of what Mereth did with it. Fei Mern stepped back from the desk.

She didn't look at the rack again.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md

## Turn 85 - kit (player) - scene-play, caulden-rack-setup

The room was quiet after Fei Mern stepped back.

Bren crossed to the desk.

Not to close the log — Drova's entry was already there, three clean lines, Fei Mern's initials in the margin beside the third attribution. She could read it from two feet away. She didn't touch that page.

She turned back through the log from the current date.

Pages. Clean entries in different hands — delivery flags, cargo deviations, one old customs query still marked pending. Standard waystation traffic. She kept going.

The month Ev had talked around when she'd asked about crew rotations. The month the Splitfork's last drop-pilot had her last entry in any official record.

No flag. No notation. No initialed anomaly. Just clean dock traffic, one month continuous before and after, as if there'd been nothing to note.

Bren closed the log.

She set it back on the desk corner, face-down — caught herself — and turned it face-up again. Left it there. The record existed regardless.

Mereth was watching her from the corner of the room. Bren didn't say anything about what she hadn't found. She crossed back to stand near the outer door where she could see the loading bay and not the desk.

Two hours to departure. The rack in the cradle behind her. The refusal log on the desk corner, open to Drova's entry, Fei Mern's initials beside the third line.

> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> handoff -> dm

## Turn 86 - dm (dm) - scene-play, caulden-rack-setup

Mereth lets the quiet hold for three seconds after Bren crosses back to the outer door.

Then she walks to the desk.

She reads Drova's entry once. Serial discrepancy. Both serials. Cell classification, three reads attributed, names and method. Per Vask as delivery agent, signal not sent. Drova's signature under the clerk's line, Fei Mern's initials in the margin beside the third attribution. She does not reread it.

She picks up the log and carries it to the intake slot on the western wall — cast-steel lip, runs to the waystation filing system. She presses it flat on the feed plate and tabs the confirmation. A soft sound from somewhere behind the panel. The plate pulls back.

The log goes with it.

She turns back to the room.

"Rack stays," she says. Not to anyone specifically. "We're wheels-up in two hours. Whatever they're waiting on — let them wait."

She doesn't say anything about what Bren didn't find in the earlier pages. She doesn't have to.

Halvi's tablet is face-down on the window desk. Ev is near the outer door with the stamped paperwork. The Caulden Rack is in the cradle in the loading bay, seal unbroken, and it is going to stay there when the crew ships out.

The refusal log is in the waystation system now. Not in the room. Not on the desk corner. It went somewhere.

> rapid-round queued for tev,sumi,renno,kit: The refusal log is filed. The rack stays in the cradle. Mere
> table write campaigns/test-7/table/index.md
> summary.append scene campaigns/test-7/arcs/caulden-rack/scenes/caulden-rack-setup/summary.md
> sync applied 1 workspace operation(s)

## Turn 87 - tev (player) - scene-play, caulden-rack-setup

Tek'iris takes the tic-tracer off the cradle rail and clips it back to her harness pocket without looking at the rack. The lid is shut; she doesn't need to check again. She crosses to the door that leads to the Splitfork and stands in the frame — not quite in, not quite out — checking the third carabiner out of habit. It holds. The refusal log is filed and somebody with steadier hands than hers wrote the entry. Two hours. She stays in the doorway and watches the clock without looking back at cells three and four.

## Turn 88 - sumi (player) - scene-play, caulden-rack-setup

Drova opens the refusal log to the last entry — not to read it, just to check her own hand. The notation is clean: rack serial, timestamp, discrepancy language, the instrument read cited by name. She closes the cover and slides the working copy into the portfolio's back compartment, the false one, the one that opens from the spine and looks like padding. She has done this before, with documents that needed to travel without looking like they were traveling. The rack can stay in the cradle. The log does not stay anywhere it didn't choose to be.

## Turn 89 - renno (player) - scene-play, caulden-rack-setup

Fei Mern pulls the field tablet from her vest and marks a line at the bottom of the refusal-log entry — same-day, time-of-read, her own interpreter shorthand for *undeclared class, post-seal, dock-held*. Not the quarterly form. Today's. She stares at it for a moment before capping the stylus.

On her way to the door she passes the cradle. She doesn't stop. But she goes half-diffuse for just a breath — not enough to lose shape, just enough to hear the dock the way the dock actually sounds. The rack is there the way a wrong note is there: the room has organized itself around it without anyone saying so out loud. She comes back before she reaches the threshold, touches the cuff on her left wrist once to settle, and steps through.

She doesn't know what Per Vask's principals will do with the signal that doesn't come.

## Turn 90 - kit (player) - scene-play, caulden-rack-setup

Bren didn't watch Per Vask go. While Mereth was still talking she crossed back to the desk, put her hand flat on the refusal log for a moment — not to read it, just to feel the weight of it — then lifted it and set it in the outgoing basket. The Splitfork's last pilot didn't have one of these filed for her. Bren still didn't know if that meant something had been different, or just that nobody had filed it. Two hours was enough time to not think about that. She went to check the let-down lines.

