"""Small in-process bridge to the `glass` CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import os

from click.testing import CliRunner

from cli.main import main as glass_main

from .config import AogConfig, config_env_value


@dataclass(frozen=True)
class GlassResult:
    args: list[str]
    exit_code: int
    output: str


class GlassBridgeError(RuntimeError):
    def __init__(self, result: GlassResult):
        super().__init__(result.output.strip() or f"glass exited with {result.exit_code}")
        self.result = result


class GlassBridge:
    def __init__(self, config: AogConfig):
        self.config = config
        self.runner = CliRunner()

    def invoke(
        self,
        args: list[str],
        *,
        role: str | None = None,
        campaign: str | None = None,
        extra_env: Mapping[str, str] | None = None,
    ) -> GlassResult:
        env = os.environ.copy()
        env["GLASS_CONFIG"] = config_env_value(self.config)
        env["GLASS_API_INTERNAL"] = "1"
        if role is not None:
            env["GLASS_ROLE"] = role
        if campaign is not None:
            env["GLASS_CAMPAIGN_ID"] = campaign
        if extra_env:
            env.update(extra_env)

        raw_result = self.runner.invoke(glass_main, args, env=env, prog_name="glass")
        result = GlassResult(
            args=args,
            exit_code=raw_result.exit_code,
            output=raw_result.output,
        )
        if result.exit_code != 0:
            raise GlassBridgeError(result)
        return result
