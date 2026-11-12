from __future__ import annotations

import sys
from collections.abc import Iterable


DEFAULT_HISTORY_CHOICES: tuple[str, ...] = ("6mo", "1y", "2y", "3y", "5y", "10y", "max")

# Friendly labels <-> yfinance period codes.
PERIOD_ALIASES: dict[str, str] = {"1w": "5d", "1m": "1mo", "3m": "3mo", "6m": "6mo"}
PERIOD_LABELS: dict[str, str] = {code: label for label, code in PERIOD_ALIASES.items()}

# Approximate trading days per lookback, used to scale row minimums and rolling windows.
TRADING_DAYS: dict[str, int] = {
    "5d": 5, "1mo": 21, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504,
    "3y": 756, "5y": 1260, "10y": 2520,
}


def period_label(period: str) -> str:
    """Display label for a yfinance period code (5d -> 1w, 1mo -> 1m, 3mo -> 3m)."""
    return PERIOD_LABELS.get(period, period)


def scaled_minimum_rows(period: str, configured: int) -> int:
    """90% of the expected trading days for the window, capped at the configured minimum."""
    expected = TRADING_DAYS.get(period)
    return configured if expected is None else max(2, min(configured, int(expected * 0.9)))


def scaled_window(period: str, configured: int, floor: int = 5) -> int:
    """Shrink a rolling window (e.g. the spread z-score window) so it fits inside the lookback."""
    expected = TRADING_DAYS.get(period)
    return configured if expected is None else max(floor, min(configured, expected // 2))


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
                input(
                    f"Select {label} [{', '.join(period_label(c) for c in allowed)}] "
                    f"(default: {period_label(configured)}): "
                ).strip()
                or configured
            )
        except EOFError:
            chosen = configured
    else:
        chosen = configured

    chosen = PERIOD_ALIASES.get(chosen.lower(), chosen)
    if chosen not in allowed:
        raise SystemExit(f"Unsupported {label} '{chosen}'. Allowed values: {', '.join(allowed)}.")
    return chosen
