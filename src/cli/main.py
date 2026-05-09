"""Entry point for the `glass` CLI.

The CLI is the in-session tool surface for Agents of Glass. It records only
coherence-critical state — sessions, mode labels, dice, character numbers,
messages, note ratification state, turn metadata — and keeps prose in
markdown.

This file is a thin shell. Each command group lives in `cli/commands/<group>.py`;
shared helpers live in sibling modules (errors, constants, ids, yaml_io,
config, role, paths_resolve, validation, state, campaign, messages, entities).
"""

from __future__ import annotations

import click

from .commands.arc import arc
from .commands.character import character
from .commands.db import db
from .commands.entity import entity
from .commands.lore import lore
from .commands.mode import mode
from .commands.msg import msg_group
from .commands.note import note
from .commands.quest import quest
from .commands.roll import roll
from .commands.scene import scene
from .commands.session import session
from .commands.thread import thread
from .commands.turn import turn
from .commands.turns import turns


@click.group()
def main() -> None:
    """In-session state CLI for Agents of Glass."""


main.add_command(session)
main.add_command(mode)
main.add_command(roll)
main.add_command(character)
main.add_command(note)
main.add_command(entity)
main.add_command(thread)
main.add_command(msg_group)
main.add_command(turn)
main.add_command(turns)
main.add_command(db)
main.add_command(arc)
main.add_command(scene)
main.add_command(quest)
main.add_command(lore)


if __name__ == "__main__":
    main()
