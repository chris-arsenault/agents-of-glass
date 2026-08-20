# Organization Bootstrap

Goal: define a campaign organization whose work generates adventure, as durable
facts and a concise public prose reveal.

Premise gate — apply before writing anything: **the organization wants
something that someone else guards, hides, or contests** — salvage claims,
bounties, relics, routes, cargo, secrets, territory, a score. An organization
that provides a service produces service-delivery fiction, and the campaign
will be procedure no matter how dangerous the job looks. If your candidate org
is best described by the service it renders, discard it and start from what it
wants and who is in the way.

1. Call `glass_check()`. If an operator direction fact is present in the
   injected prompt, treat it as the seed phrase for the organization's shape.
2. Compare against the injected previous-organization patterns and avoid
   repeating mission, method, culture, role shape, or pull domain.
3. Record the non-adjacent pull, organization identity, the organization's
   want (what it pursues and who guards or contests it), dangerous work,
   operating method, internal culture, public constraints, and
   character-creation brief with one `glass_state_update(updates=[{"kind": "fact", "audience": "continuity", "importance": "high", "subject_id": "organization", "predicate": "want", "text": "<what the org pursues, and who guards or contests it>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "campaign", "predicate": "pull", "text": "<non-adjacent pull source and how it is used>"}, {"kind": "fact", "audience": "continuity", "importance": "medium", "subject_id": "organization", "predicate": "identity", "text": "<organization identity>"}])` call, adding the remaining facts as full objects in the same list.
4. Do not split bootstrap facts across repeated single-fact calls.
5. The character-creation brief must ask each player for a character who wants
   something this work cannot give them, alongside their competence coverage.
6. End the mode with `glass_mode_end()` when the organization is concrete
   enough for character creation.
7. Close with `glass_done(..., scene_status="active")`.
8. Submit a short public organization brief with `glass_turn_append(body="...")`.

Do not write organization markdown files. Do not use files as the continuity
store.
