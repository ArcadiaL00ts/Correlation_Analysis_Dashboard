from __future__ import annotations

import sys
from collections.abc import Iterable


DEFAULT_HISTORY_CHOICES: tuple[str, ...] = ("6mo", "1y", "2y", "3y", "5y", "10y", "max")


def resolve_history_period(
    cli_value: str | None,
    configured: str,
    choices: Iterable[object] | None,
    label: str,
) -> str:
    """Pick a history window from the CLI flag, an interactive prompt, or config.

    Priority: explicit ``cli_value`` > interactive prompt (TTY only) > ``configured``.
    Exits with a readable message when the chosen value is not in ``choices``.
    """

    allowed = [str(choice).strip() for choice in (choices or []) if str(choice).strip()]
    if not allowed:
        allowed = list(DEFAULT_HISTORY_CHOICES)

    if cli_value:
        chosen = cli_value.strip()
    elif sys.stdin.isatty():
        try:
            chosen = (
                input(f"Select {label} [{', '.join(allowed)}] (default: {configured}): ").strip()
                or configured
            )
        except EOFError:
            chosen = configured
    else:
        chosen = configured

    if chosen not in allowed:
        raise SystemExit(f"Unsupported {label} '{chosen}'. Allowed values: {', '.join(allowed)}.")
    return chosen
