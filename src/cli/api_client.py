"""Client side of the local glass API proxy."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


DEFAULT_TIMEOUT_SECONDS = 600


def should_proxy(args: list[str], env: dict[str, str] | None = None) -> bool:
    env = env or os.environ
    if env.get("GLASS_API_INTERNAL"):
        return False
    if args and args[0] == "api":
        return False
    return bool(env.get("GLASS_API_URL") and env.get("GLASS_API_GRANT"))


def proxy_args(args: list[str], env: dict[str, str] | None = None) -> int:
    env = env or os.environ
    url = env["GLASS_API_URL"].rstrip("/") + "/v1/command"
    payload = json.dumps(
        {
            "grant": env["GLASS_API_GRANT"],
            "args": args,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_timeout_seconds(env)) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
    except OSError as exc:
        sys.stderr.write(f"glass API request failed: {exc}\n")
        return 69

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        sys.stderr.write(f"glass API returned invalid JSON: {body}\n")
        return 70

    output = data.get("output")
    if isinstance(output, str) and output:
        sys.stdout.write(output)
        if not output.endswith("\n"):
            sys.stdout.write("\n")
    return int(data.get("exit_code", 1))


def _timeout_seconds(env: dict[str, str]) -> float:
    raw = env.get("GLASS_API_TIMEOUT_SECONDS")
    if raw is None:
        return float(DEFAULT_TIMEOUT_SECONDS)
    try:
        value = float(raw)
    except ValueError:
        return float(DEFAULT_TIMEOUT_SECONDS)
    return max(value, 1.0)
