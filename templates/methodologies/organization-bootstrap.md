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

## Organization Action Contract

The organization is not the campaign yet, but it is the first signal about what
play will feel like. Build an organization whose normal work sends characters
into dangerous, physical, mobile situations. Procedure, records, hierarchy, and
authority can exist, but they must support field action rather than become the
main play loop.

Every organization brief must answer:

- What dangerous situations does this crew enter in person?
- Who can be physically harmed if the crew fails, delays, or chooses badly?
- What action-facing jobs does the organization need: rescue, breaching,
  fighting, scouting, chase, containment, evacuation, infiltration, repair under
  fire, strange-matter handling, hostile negotiation, or another on-screen task?
- What kinds of hazards, creatures, hostile people, unstable places, or moving
  threats commonly oppose the work?
- Why paperwork, permission, reputation, or procedure cannot solve the job by
  itself?

## Sequence

1. **Read the org-facing surfaces.**
   - Read `dm/persona.md`, `shared/lore/`, `table/scene.md`, and
     [`how-to/party-organization.md`](../how-to/party-organization.md).
   - Search the world bible only for concepts the organization obviously needs
     right now.

2. **Do one anti-generic pull before writing.**
   - Make one non-adjacent real-world pull from a current nonfiction source
     outside the repo.
   - Do not begin from team-type, profession-type, emergency-response, fiction,
     RPG, or campaign-advice searches. Begin from recent nonfiction about real
     people or groups under pressure, then choose a source with vivid observed
     behavior.
   - Use ensemble shows only as shape checks for cast function, not as the
     borrowed detail source.
   - The pull must change at least four organization surfaces: what the
     organization wants when no mission is active; how members show status,
     trust, rivalry, or belonging; what kinds of scenes the organization
     naturally creates; what action-facing situations it sends characters into;
     and what the character creation brief makes players excited to become.
   - The pull fails if its main contribution is checklist, custody,
     authorization, safety hierarchy, documentation, or compliance. Procedure
     can exist, but it cannot be the borrowed fantasy.
   - Record the pull with:

     ```bash
     glass campaign pull-note \
       --source "<real-world domain/source>" \
       --used-in "organization identity" \
       --used-in "character creation brief" \
       --note "<borrowed behavior/culture and the organization surfaces it changes>"
     ```

3. **Write the public organization.**
   - Author `shared/lore/organization.md` with public identity, standing,
     dangerous work, field constraints, action-facing capabilities, internal role
     shape, and advancement shape.
   - Name the kinds of places the organization physically enters and the kinds of
     harm it exists to prevent.
   - Describe procedure as field discipline, authority under pressure, or
     after-action truth. Do not make it the thing most scenes are about.

4. **Write the private organization note.**
   - Author `dm/notes/organization.md` with private compromises, hidden
     tensions, leverage points, and load-bearing truths.
   - Keep this broad. Do not predict named player lanes or pre-assign who each
     future PC is for.
   - Keep private tensions adventure-facing: dangerous shortcuts, compromised
     gear, rivals who act, places the org fears entering, debts that can put
     bodies in danger, or rules that fail under pressure.

5. **Write the org-only character creation brief.**
   - Replace `table/scene.md` with a brief that tells players what kind of org
     they are joining, what dangerous work it does, what action-facing jobs it
     needs, and what kinds of people fit.
   - This brief should be organization-first, not campaign-first.

6. **Commit and register.**
   - `glass sync apply shared/lore/organization.md dm/notes/organization.md table/scene.md`
   - `glass lore upsert shared/lore/organization.md`

7. **Close the bootstrap turn.**
   - Write `TURN.md` as a short public org brief.
   - Run `glass done --summary "party organization ready for character creation" --state "<org lore, private org note, table brief, and pull note updated>" --rolls none --next default`.
   - Run `glass mode end`.

## Prohibitions

- Do not write `dm/foundation.md`.
- Do not write campaign scarcity, pressure clocks, factions, NPC rosters, hook
  inventories, secrets boards, or opening-arc prep.
- Do not create any arcs.
- Do not create campaign-level pressure before the characters exist.
- Do not write player-specific predictions such as "Kit will..." or "Sumi's
  lane is...".
- Do not build an organization whose main work is legal drama, audit drama,
  claims handling, custody preservation, workplace procedure, or institutional
  negotiation. Those can be support texture; they cannot be the reason the crew
  exists.
- Do not make the internal role shape primarily "who carries procedure" or "who
  interfaces with institutions." The role shape must include people who enter
  danger, move through space, change the physical situation, and protect others.
- Do not build an organization whose default missions can be solved from one
  desk, office, hearing room, archive, or command post.
