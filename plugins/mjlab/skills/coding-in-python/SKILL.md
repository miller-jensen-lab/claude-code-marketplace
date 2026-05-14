---
name: coding-in-python
description: Python implementation rules for Miller-Jensen lab analysis code — uv environments, ruff, portable paths, and notebook-vs-script discipline. TRIGGER when editing .py files, writing analysis scripts, structuring a Python project, or refactoring notebook code into reusable modules in a Miller-Jensen lab repository.
related:
  - programming-and-coding
  - notebooks
  - tabular-data
  - plotting
  - starting-a-new-project
  - reproducible-envs
updated: 2026-05-14
---
# Coding in Python

Rule: use a locked environment, write portable paths, and keep notebooks thin by moving reusable functions into a `.py` file next to them.

For general coding philosophy, also load [programming-and-coding](../programming-and-coding/SKILL.md).

## Tooling defaults

- **`uv`** for dependency management, lockfiles, and Python interpreter selection. Replaces `pip`, `virtualenv`, `pyenv`, and `pip-tools`. Install with one curl command from <https://docs.astral.sh/uv/>.
- **`ruff`** for lint + format. Run before committing; it's fast and the defaults are sensible.
- **`pathlib`** over `os.path` for every filesystem operation.
- **`argparse`** for batch scripts. Graduate to **`click`** only when the script grows multiple subcommands or you find yourself parsing args by hand.
- **`logging`** as the baseline. Use `loguru` only if its structured output is materially helpful.
- `pyproject.toml` + `uv.lock` committed; `.venv/` gitignored.

Optional (add when the codebase grows past a few hundred lines or you start sharing modules across projects):

- **`pyrefly`** or **`ty`** for type checking. Pick one; don't run both. Don't use `mypy`.
- **`pytest`** for tests. For analysis code, prefer **smoke tests on a small real-data slice** to extensive unit tests. Skip tests entirely for one-off scripts.

## Project setup with uv

```bash
cd ~/projects/2026-tnf-bursting
uv init
uv add polars pyarrow scanpy
uv add --dev ruff jupyter
uv sync --frozen
```

Commit `uv.lock`. Anyone else on the project re-creates the exact environment with `uv sync --frozen`. See [reproducible-envs](../reproducible-envs/SKILL.md).

## Project layout

A flat layout is fine for most analyses:

```
2026-tnf-bursting/
├── pyproject.toml
├── uv.lock
├── README.md
├── notebooks/           # exploratory, one per question
├── scripts/             # batch entry points (run_de.py, fit_bursts.py)
├── lib.py               # shared helpers; import from notebooks/scripts
├── data/raw/            # never edit; gitignored
├── data/derived/        # intermediate; gitignored
└── results/             # figures, tables; gitignored except final exports
```

Reach for an installable `src/<package>/` layout only when shared code grows past one file, or when more than one repo wants to import the same helpers.

## Portable paths — don't hardcode

A path that works on your laptop will not work on the next person's. Never commit:

- `/Users/jdoe/Desktop/data.csv`
- `C:\Users\jdoe\...`
- `~/Dropbox/...`
- Absolute paths to a cluster scratch directory

Instead:

```python
from pathlib import Path

# Path relative to the repo root (this file lives at repo root or in scripts/)
REPO = Path(__file__).resolve().parent
DATA = REPO / "data" / "raw" / "counts.csv"
```

Or read the location from an environment variable / CLI arg so the same script runs on any machine:

```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--data", type=Path, required=True)
args = parser.parse_args()
```

For shared data on the lab fileserver, put the mount point in a project `.env` file (gitignored) and load it with `os.environ` or `python-dotenv`. The script itself stays portable.

## Python style

- f-strings for formatting. No `%` or `.format()`.
- List comprehensions for simple transforms; `for` loops when branching dominates readability.
- Context managers (`with`) for every file or network handle.
- Early returns to reduce nesting.
- `pathlib.Path` for paths; never string-concatenate paths with `+` or `os.path.join`.
- `@dataclass(frozen=True)` for small immutable payloads. Reach for `pydantic` only when validating external/untrusted input.
- Imports at module top.
- Set seeds for any stochastic operation: `rng = np.random.default_rng(42)`. Pass `rng` through as an argument; don't rely on global state.

## Error handling

- Handle exceptions only where recovery changes behavior.
- Catch the specific exception class. Never bare `except:`.
- Let it bubble if you can't recover cleanly — a traceback in an analysis script is signal, not noise.

## Logging

- `logging.getLogger(__name__)` at module top. Configure once at the entry-point of the script, not at import time.
- INFO for milestones ("loaded 12,341 cells from {path}"), WARNING for recoverable surprises.

## Notebooks vs. scripts

- A notebook cell longer than ~30 lines is a function in disguise — move it into `lib.py` and import it.
- Never `from notebook import …`. Notebooks consume helpers; they don't export them.
- Use [`jupytext`](https://jupytext.readthedocs.io/) to pair `.ipynb` with `.py` if you want notebooks tracked in git without committing outputs.

See [notebooks](../notebooks/SKILL.md) for full discipline.

## Detecting code smells

The 1000-line `main()`, the function with 12 parameters, the helper nobody calls — catchable with tools you already have. For bug-finding in a diff, see [code-review](../code-review/SKILL.md); this section is about structural drift.

**Ruff** covers most smells once you enable the right rule groups in `pyproject.toml`:

```toml
[tool.ruff.lint]
extend-select = [
  "C90",   # mccabe — cyclomatic complexity
  "PLR",   # pylint refactor — too-many-args, too-many-branches, etc.
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 6
max-branches = 12
max-returns = 6
max-statements = 50
```

These then run as part of `uv run ruff check`.

For one-off audits (a new student's codebase, a stale repo), reach for:

- `uvx radon cc -s -a lib.py` — per-function cyclomatic complexity, graded A–F with an average.
- `uvx radon mi lib.py` — maintainability index (a composite of complexity, LOC, and Halstead volume).
- `uvx vulture lib.py scripts/` — unused functions, imports, and arguments.

`uvx` runs a tool without adding it to the project's dependencies — right for ad-hoc audits, not for CI.

## Checklist before committing

- [ ] `uv run ruff format . && uv run ruff check .` clean
- [ ] No hardcoded absolute paths to your laptop, Desktop, Dropbox, or `/Users/...`
- [ ] No raw data, large outputs, or `.ipynb_checkpoints/` staged
- [ ] Seeds set on any stochastic code path
- [ ] `uv.lock` committed

## Further reading

- [uv documentation](https://docs.astral.sh/uv/)
- [ruff documentation](https://docs.astral.sh/ruff/)
- [pyrefly](https://github.com/facebook/pyrefly)
- [ty (Astral's type checker)](https://github.com/astral-sh/ty)
- [Python `pathlib`](https://docs.python.org/3/library/pathlib.html)
- [`argparse` tutorial](https://docs.python.org/3/howto/argparse.html)
- [`click` documentation](https://click.palletsprojects.com/) — when you outgrow argparse
- [Ruff rule index](https://docs.astral.sh/ruff/rules/) — the `C90` and `PLR` groups are the smell catchers
- [`radon`](https://radon.readthedocs.io/) — complexity and maintainability metrics
- [`vulture`](https://github.com/jendrikseipp/vulture) — dead-code detector
