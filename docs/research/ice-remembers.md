# ice-remembers

**Status:** Placeholder. Not yet researched.

## What We Need to Know

The user has referenced a project called "ice remembers" as a model for what we'll do *with* the transcripts our system produces — turn raw transcripts into narrative prose, presumably preserving structure (who, what, when, why) while smoothing voice into something like fiction.

## Why It Matters

This is the downstream consumer of the corpus we're producing. Understanding its input requirements *now* will save us from emitting transcripts in a shape that's awkward to feed in later. Specifically:

- Does it want turn-by-turn structure, or session-level prose?
- Does it preserve speaker attribution, or smooth speakers into omniscient narration?
- What does it expect to do with mode boundaries — treat them as scene breaks, or invisible?
- Does it want OOC content, or only IC?
- Does it consume structured deltas or only prose?

## To Do

- Locate the project (likely under `/home/dev/repos/`)
- Read its input contract / sample inputs
- Add a section to [`../principles/transcripts-as-corpus.md`](../principles/transcripts-as-corpus.md) confirming our transcript shape is compatible
- Update this file with the actual summary
