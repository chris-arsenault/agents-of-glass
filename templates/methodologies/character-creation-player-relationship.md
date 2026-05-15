---
title: Character Creation Player Relationship
status: authored
audience: player
applies_to_modes: [character-creation]
---

# Character Creation Player Relationship

1. Read every `players/*/public/intro.md`.
2. Run `glass character bulk-get --all`.
3. Run `glass check` to read unread messages.
4. Write or update `players/<id>/public/relationships.md` with public
   relationship commitments that create play surface with one or two other PCs.
5. Use messages for proposals that need another player or the DM:
   `glass msg banter <recipient> "<specific relationship proposal or question>"`.
6. Commit with `glass sync apply players/<id>/public/relationships.md`.
7. Write `TURN.md` with only the public relationship commitments.
8. Run `glass done --summary "<relationship commitments updated>" --state "players/<id>/public/relationships.md updated" --rolls none --next default`.

Do not alter hard character numbers on this turn unless the DM explicitly asked
for a correction.
