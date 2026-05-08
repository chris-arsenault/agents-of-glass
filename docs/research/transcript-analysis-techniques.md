# Transcript Analysis Techniques

**Status:** Placeholder. Will be filled in once we have transcripts to analyze.

## What We Want to Know

What kinds of analysis are tractable on TTRPG transcripts of the kind our system produces?

Candidate techniques to evaluate:

- Topic modeling across a corpus of sessions to find recurring themes per character
- Speaker-attribution-aware sentiment tracking (does Sumi roleplay darker than Tev?)
- Beat-advancement metrics (how many beats per session, per mode?)
- "Closure quality" measures — how cleanly did each scene end? Can we measure this from transcript shape alone?
- Voice consistency drift — does Mara sound like Mara across 20 sessions, or does she drift?
- Plot-shape extraction — fit a session against a known structure (Freytag, hero's journey, monster-of-the-week)
- Mode-transition health — what fraction of mode transitions are clean (resolution) vs forced (budget)?

## Why It Matters

Knowing what analysis is tractable shapes what structure we emit at write time. If sentiment analysis on speaker-attributed text is the most useful technique, we double-check our speaker tagging is rock-solid. If beat metrics matter, we ensure beat advancement is always tagged.

## To Do

- Run a v1 session, get a real transcript
- Try a few techniques in a notebook
- Update this file with what worked and what didn't
- Refine `transcripts-as-corpus.md` accordingly
