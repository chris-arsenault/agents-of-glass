"""In-process executor for granted Glass runtime commands."""

from __future__ import annotations

import contextlib
import os
import threading
import traceback
from pathlib import Path
from typing import Any, Iterator

from click.testing import CliRunner

from .api_grants import validate_grant
from .config import get_paths


_invoke_lock = threading.Lock()


def invoke_current_turn_args(args: list[str]) -> dict[str, Any]:
    """Invoke a granted command using the current process environment."""

    return invoke_granted_args(args, os.environ.get("GLASS_API_GRANT", ""))


def invoke_granted_args(args: list[str], grant: str) -> dict[str, Any]:
    """Validate a grant and invoke the command in-process."""

    paths = get_paths()
    claim = validate_grant(paths.campaigns, grant, args)
    return invoke_claim_args(args, claim)


def invoke_claim_args(args: list[str], claim: dict[str, Any]) -> dict[str, Any]:
    """Invoke a command with already-validated grant claims."""

    from .main import main as glass_main

    campaigns_dir = get_paths().campaigns
    campaign_id = str(claim["campaign_id"])
    campaign_root = campaigns_dir / campaign_id
    env = os.environ.copy()
    env.update(
        {
            "GLASS_API_INTERNAL": "1",
            "GLASS_CAMPAIGN_ID": campaign_id,
            "GLASS_ROLE": str(claim["glass_role"]),
            "GLASS_TURN_ID": str(claim["turn_id"]),
        }
    )
    runner = CliRunner()
    with _invoke_lock, _pushd(campaign_root):
        raw = runner.invoke(glass_main, args, env=env, prog_name="glass")
    return {
        "exit_code": raw.exit_code,
        "output": raw.output or format_invoke_exception(raw.exception),
    }


def format_invoke_exception(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    if isinstance(exc, SystemExit):
        return ""
    message = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return f"glass internal error: {message}\n"


@contextlib.contextmanager
def _pushd(path: Path) -> Iterator[None]:
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)
