# Modes And Scene Types

A **mode** is the turn protocol currently governing a scene. Runtime active play
has exactly two play modes:

- `scene-play` for open, round-robin scene play.
- `action` for quickfire scenes with tight order, visible pressure, and
  frequent consequential rolls.

A scene's `--type` is a loose toolkit label, not a mode. Labels like `combat`,
`chase`, `social-pressure`, `travel`, `investigation`, `rescue`, or a custom
slug help the DM frame the scene and make the corpus searchable. They do not
change scheduling, methodology selection, budgets, or validation by themselves.

For the universal turn shape that modes parameterize, see
[`turn-loop.md`](turn-loop.md). For closure, see
[`scene-ending.md`](scene-ending.md). For the broader hierarchy of campaign to
arc to scene, see [`game-start.md`](game-start.md) and
[`context-packages.md`](context-packages.md).

## How A Scene Gets A Mode

When the DM scaffolds a scene with
`glass scene create <slug> --type <label>`, the CLI records that `--type` label
as scene metadata. The DM then starts one of the two play modes:

```bash
glass mode start scene-play <scene-slug>
glass mode start action <scene-slug>
```

Use `scene-play` when the table should have broad turns: social scenes,
exploration, investigation, downtime, aftermath, planning, travel montage, or
anything where time can breathe.

Use `action` when every turn should change leverage, position, danger, progress,
or cost: combat, chase, disaster, escape, social pressure, duel, infiltration,
heist, race, exorcism, rescue, or any other quickfire pattern.

Do not start `combat`, `chase`, `social-pressure`, `travel`, or `montage` as
modes. Keep those words in `--type`, scene prep, table artifacts, trackers, and
prose.

## Active Play Protocols

| Protocol | Speaker Selection | Fictional Time Per Turn | Checks | Typical Turn Cap | Ends When |
| --- | --- | --- | --- | --- | --- |
| `scene-play` | round-robin plus handoffs | minutes, hours, or days as needed | fewer; players roll when uncertainty matters; DM rolls DM-side checks when needed | 120 | DM cuts to the next scene, or no player has a new action |
| `action` | action order rolled after DM layout | seconds or a few heartbeats | more common; players still choose their own rolls; DM-side checks stay on DM turns | 120 | visible clocks/beats resolve, the scene closes, or the DM transitions |

## Scene-Play

`scene-play` is the flexible protocol for open-ended scenes. Players can propose
almost anything. Time can advance slowly or in larger chunks. Notes and
relationships can matter without needing action order.

Common scene types that usually use `scene-play`: `town`, `social`,
`exploration`, `investigation`, `downtime`, `research`, `planning`,
`aftermath`, and `travel`.

## Action

`action` is the quickfire protocol for contested moments where turn order and
visible pressure matter.

The action protocol:

1. The DM creates or transitions into a scene with a useful `--type` label.
2. The DM starts `action` mode for that scene.
3. The DM takes an opening layout turn: location, positions, visible pressure,
   stakes, opposition, and likely exit shape.
4. In that opening turn, after the layout, the DM calls `glass turn initiative`.
5. The orchestrator follows that persisted action order. Handoffs and
   rapid-response queues can interrupt; after the queue drains, play continues
   from the stored action cursor.
6. Each player turn is quickfire: move, one action, quick upkeep. Upkeep
   includes messages, inventory checks, relevant state reads, and DM
   clarifications. It should not become a second action.

Common scene types that usually use `action`: `combat`, `chase`,
`social-pressure`, `escape`, `duel`, `infiltration`, `trial`, `disaster`,
`heist`, `race`, `exorcism`, and `rescue`.

## Toolkit Examples

The toolkit is a shelf of scene patterns. The DM can use one, combine two, or
make up a new one.

| Scene Type | Usually Mode | Honest Tracker Examples |
| --- | --- | --- |
| `combat` | `action` | enemy HP, enemy morale, party holdout clock |
| `chase` | `action` | escape distance 0/6, pursuit clock 0/4, route hazards |
| `social-pressure` | `action` | concession clock, suspicion clock, public-support clock |
| `investigation` | `scene-play` | clue web, deadlock clock, lead quality |
| `exploration` | `scene-play` | rooms mapped, hazard clock, supplies |
| `travel` | `scene-play` | days crossed, weather clock, route risk |

## Bootstrap-Only Modes

These modes apply during bootstrap phases, not active play.

| Mode | Phase | Speaker Selection | Output |
| --- | --- | --- | --- |
| `organization-bootstrap` | organization bootstrap | DM only | organization brief and party frame |
| `campaign-planning` | campaign planning | DM only | campaign foundation and opening arc |
| `character-creation` | character creation | players then DM | PCs, intros, relationships, ratification |
| `scene-prep` | scene staging | DM only | scene prep, table setup, mode handoff |
| `intermission` | act break | DM + players | between-act prompt and requests |
| `wrap` | closure | DM only | summary and final persistence |

## Nesting

Modes can nest, but the nested play mode is still only `scene-play` or
`action`. For example, a `combat`-typed action burst can erupt inside a
`social`-typed scene-play parent. When the action burst ends, the parent
resumes.

```yaml
mode_stack:
  - { mode: scene-play, scene_id: keel-quarter, turn_budget_remaining: 94 }
  - { mode: action, scene_id: ringglass-market-chase, turn_budget_remaining: 117 }
```

The scene type carries the narrative label; the mode carries the runtime
protocol.

## Adding New Labels

Most new scene labels do not need a new mode. Add the label to prep, table
artifacts, or scene `--type`, then choose `scene-play` or `action`.

Adding a new mode is a runtime change: it requires speaker selection,
methodology routing, turn validation, tests, and budget policy. Do not add one
just to name a narrative shape.
