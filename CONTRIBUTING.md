# Contributing

1. `pip install -e .` in a virtual environment (Python 3.11+).
2. Run the tests before and after a change: `python -m unittest discover tests`.
   They are offline: `tests/__init__.py` blocks network access, and anything that would call
   Yahoo Finance is mocked. Keep new tests that way. CI runs them on Windows and Linux,
   Python 3.11 and 3.12.
3. Settings belong in `config/dashboard_config.json`, not in code.
4. Any change to the universe rules, ranking/fallback order or pair qualification must be logged
   in `codex.md` with what changed and why. Record new failure modes and their fixes there too.
5. Keep the heatmap on the fixed `[-1, 1]` scale with its configured colours.
6. Write artifacts through `atomic_io` (`write_csv`, `write_json`, `atomic_target`) so the
   dashboard never reads a half-written file.

Code style: `from __future__ import annotations` at the top of every module, type hints,
`pathlib.Path`, relative imports inside the package (`dashboard.py` is the exception: Streamlit runs
it as a script).
