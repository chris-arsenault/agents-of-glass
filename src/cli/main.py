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

import sys

import click

from .commands.arc import arc
from .commands.character import character
from .commands.clock import clock
from .commands.db import db
from .commands.entity import entity
from .commands.lore import lore
from .commands.mode import mode
from .commands.msg import msg_group
from .commands.note import note
from .commands.quest import quest
from .commands.roll import roll
from .commands.scene import scene
from .commands.search import search_group
from .commands.session import session
from .commands.summary import summary
from .commands.table import table
from .commands.tarot import tarot
from .commands.thread import thread
from .commands.turn import turn
from .commands.turns import turns


class GlassGroup(click.Group):
    def main(
        self,
        args=None,
        prog_name=None,
        complete_var=None,
        standalone_mode=True,
        **extra,
    ):
        resolved_args = list(sys.argv[1:] if args is None else args)
        from .api_client import proxy_args, should_proxy

        if should_proxy(resolved_args):
            exit_code = proxy_args(resolved_args)
            if standalone_mode:
                raise SystemExit(exit_code)
            return exit_code
        return super().main(
            args=resolved_args,
            prog_name=prog_name,
            complete_var=complete_var,
            standalone_mode=standalone_mode,
            **extra,
        )


@click.group(cls=GlassGroup)
def main() -> None:
    """In-session state CLI for Agents of Glass."""
    from .local_env import load_repo_env

    load_repo_env()


@click.group()
def api() -> None:
    """Local API server commands."""


@api.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--config", "config_path", type=click.Path())
def api_serve(host: str, port: int, config_path: str | None) -> None:
    """Run the local glass API in the foreground."""
    from .api_server import serve_forever

    serve_forever(host=host, port=port, config_path=config_path)


@api.group("daemon")
def api_daemon_group() -> None:
    """Manage the detached local glass API daemon."""


@api_daemon_group.command("start")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.option("--config", "config_path", type=click.Path())
def api_daemon_start(url: str | None, config_path: str | None) -> None:
    from .api_daemon import start_daemon
    from .api_grants import DEFAULT_API_URL

    _echo_api_daemon(
        start_daemon(url=url or _api_url_default(DEFAULT_API_URL), config_path=config_path)
    )


@api_daemon_group.command("restart")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
@click.option("--config", "config_path", type=click.Path())
def api_daemon_restart(url: str | None, config_path: str | None) -> None:
    from .api_daemon import restart_daemon
    from .api_grants import DEFAULT_API_URL

    _echo_api_daemon(
        restart_daemon(url=url or _api_url_default(DEFAULT_API_URL), config_path=config_path)
    )


@api_daemon_group.command("stop")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
def api_daemon_stop(url: str | None) -> None:
    from .api_daemon import stop_daemon
    from .api_grants import DEFAULT_API_URL

    _echo_api_daemon(stop_daemon(url=url or _api_url_default(DEFAULT_API_URL)))


@api_daemon_group.command("status")
@click.option("--url", default=None, help="API URL. Defaults to GLASS_API_URL or localhost.")
def api_daemon_status(url: str | None) -> None:
    from .api_daemon import status_daemon
    from .api_grants import DEFAULT_API_URL

    _echo_api_daemon(status_daemon(url=url or _api_url_default(DEFAULT_API_URL)))


def _api_url_default(default: str) -> str:
    import os

    return os.environ.get("GLASS_API_URL", default)


def _echo_api_daemon(info) -> None:
    click.echo(
        f"glass API {info.message}: url={info.url} "
        f"pid={info.pid or '-'} running={str(info.running).lower()}"
    )
    click.echo(f"log: {info.log_path}")


main.add_command(session)
main.add_command(mode)
main.add_command(roll)
main.add_command(character)
main.add_command(clock)
main.add_command(note)
main.add_command(entity)
main.add_command(thread)
main.add_command(msg_group)
main.add_command(turn)
main.add_command(turns)
main.add_command(db)
main.add_command(arc)
main.add_command(scene)
main.add_command(search_group)
main.add_command(summary)
main.add_command(table)
main.add_command(tarot)
main.add_command(quest)
main.add_command(lore)
main.add_command(api)


if __name__ == "__main__":
    main()
