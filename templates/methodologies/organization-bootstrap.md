---
title: Organization Bootstrap
status: authored
audience: dm
applies_to_modes: [organization-bootstrap]
---

# Organization Bootstrap

Run this as exactly one Mara turn. Build the party organization with enough
fidelity that character creation has a strong frame. Do not build the campaign
yet.

## Sequence

1. **Read the org-facing surfaces.**
   - Read `dm/persona.md`, `shared/lore/`, `table/scene.md`, and
     [`how-to/party-organization.md`](../how-to/party-organization.md).
   - Search the world bible only for concepts the organization obviously needs
     right now.

2. **Do one anti-generic pull before writing.**
   - Make one non-adjacent real-world pull outside the repo.
   - Start by searching for "cool teams", "specialized crews", or another
     plain-language team search, then choose a real operating domain rather
     than fiction advice.
   - Use ensemble shows only as shape checks for cast function, not as the
     borrowed detail source.
   - Record the pull with:

     ```bash
     glass campaign pull-note \
       --source "<real-world domain/source>" \
       --used-in "organization identity" \
       --used-in "character creation brief" \
       --note "<concrete borrowed detail and how it changes the org>"
     ```

3. **Write the public organization.**
   - Author `shared/lore/organization.md` with public identity, standing,
     constraints, capabilities, internal role shape, and advancement shape.

4. **Write the private organization note.**
   - Author `dm/notes/organization.md` with private compromises, hidden
     tensions, leverage points, and load-bearing truths.
   - Keep this broad. Do not predict named player lanes or pre-assign who each
     future PC is for.

5. **Write the org-only character creation brief.**
   - Replace `table/scene.md` with a brief that tells players what kind of org
     they are joining, what jobs it needs, and what kinds of people fit.
   - This brief should be organization-first, not campaign-first.

6. **Commit and register.**
   - `glass sync apply shared/lore/organization.md dm/notes/organization.md table/scene.md`
   - `glass lore upsert shared/lore/organization.md`

7. **Close the bootstrap turn.**
   - Write `TURN.md` as a short public org brief.
   - Run `glass turn end --summary "party organization ready for character creation" --state "<org lore, private org note, table brief, and pull note updated>" --rolls none --next default`.
   - Run `glass mode end`.

## Prohibitions

- Do not write `dm/foundation.md`.
- Do not write campaign scarcity, pressure clocks, factions, NPC rosters, hook
  inventories, secrets boards, or opening-arc prep.
- Do not create any arcs.
- Do not create campaign-level pressure before the characters exist.
- Do not write player-specific predictions such as "Kit will..." or "Sumi's
  lane is...".
