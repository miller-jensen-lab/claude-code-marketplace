---
name: coding-in-python
description: Python implementation rules for Miller-Jensen lab analysis code — uv, ruff, pytest, pathlib, and notebook-vs-module discipline. TRIGGER when editing .py files, writing analysis scripts, structuring a Python project, or refactoring notebook code into reusable modules in a Miller-Jensen lab repository.
related:
  - programming-and-coding
  - notebooks
  - tabular-data
  - parallel-python
  - plotting
  - starting-a-new-project
  - reproducible-envs
updated: 2026-05-13
---
# Coding in Python

Rule: use a locked environment, keep analysis scripts small and importable, and let notebooks be the *view* on top of plain-Python modules — not the place logic lives.

For general coding philosophy, also load [programming-and-coding](../programming-and-coding/SKILL.md).

## Tooling defaults

- **`uv`** for dependency management, lockfiles, and Python interpreter selection. Replaces `pip`, `virtualenv`, `pyenv`, and `pip-tools`.
- **`ruff`** for lint + format. Run before committing.
- **`pyrefly`** or **`ty`** for type checking. Pick one; don't run both. Don't use `mypy`.
- **`pytest`** for tests. Smoke tests on a small slice of real data beat exhaustive unit coverage.
- **`pathlib`** over `os.path` for every filesystem operation.
- **`logging`** as the baseline. `loguru` only when its structured output materially helps debugging long-running jobs.
- **`click`** when a script grows a reusable CLI; otherwise `argparse` is fine for one-shot analysis scripts.
- `pyproject.toml` + `uv.lock` committed; `.venv/` gitignored.

## Project setup with uv

```bash
cd ~/projects/2026-tnf-bursting
uv init --app
uv add polars pyarrow scanpy
uv add --dev ruff pyrefly pytest jupyter
uv sync --frozen
```

Commit `uv.lock`. Anyone else on the project re-creates the exact environment with `uv sync --frozen`.

## Project layout

Keep analysis code in importable modules, not at the top level of every notebook:

```
2026-tnf-bursting/
├── pyproject.toml
├── uv.lock
├── src/tnf_bursting/    # importable package
│   ├── __init__.py
│   ├── io.py            # readers, writers
│   ├── qc.py            # filtering, QC metrics
│   └── plots.py         # plotting helpers
├── notebooks/           # exploratory; thin, calls into src/
├── scripts/             # batch entry points (one-file run scripts)
├── tests/
├── data/raw/            # never edit; gitignored
├── data/derived/        # intermediate; gitignored
└── results/             # figures, tables; gitignored except final exports
```

Configure `pyproject.toml` so notebooks can `from tnf_bursting.qc import filter_low_quality` directly (`[tool.uv.workspace]` or `[project] packages = ["src/tnf_bursting"]`). See [starting-a-new-project](../starting-a-new-project/SKILL.md) for the full template.

## Python style

- f-strings for formatting. No `%` or `.format()`.
- List comprehensions for simple transforms; `for` loops when branching dominates readability.
- Context managers (`with`) for every file, network, or DB handle.
- Early returns to reduce nesting.
- `pathlib.Path` for paths; never string-concatenate paths.
- `@dataclass(frozen=True, slots=True)` for immutable payloads. Reach for `pydantic` only at trust boundaries (parsing user input, deserializing external JSON).
- Imports at module top unless an import cycle demands lazy loading.
- Set seeds for any stochastic operation: `np.random.default_rng(42)` or `random.seed(42)`. Pass `rng=` through, don't rely on globals.

## Type hints

- Type all public function inputs and outputs.
- Skip type hints on obvious temporaries (`x = df["col"].to_numpy()`).
- Use `np.ndarray[shape, dtype]` annotations sparingly; runtime checks beat fancy types.
- For DataFrame columns, prefer a docstring schema over `pandera`/`patito` unless you actually validate at boundaries.

## Error handling

- Handle exceptions only where recovery changes behavior.
- Catch the specific exception class. Never `except:` or bare `except Exception:` without re-raising.
- Let it bubble if you can't recover cleanly. A traceback at the analysis layer is signal, not noise.

## Logging

- `logging.getLogger(__name__)` at module top. Configure once in the script entry point, not at import.
- INFO for milestones ("loaded 12,341 cells from {path}"), DEBUG for per-iteration noise, WARNING for recoverable surprises.

## Notebooks vs. modules

- A notebook cell over ~30 lines is a function in disguise — refactor into `src/`.
- Never `from notebook import …`. Notebooks are sinks, not sources.
- Use [`jupytext`](https://jupytext.readthedocs.io/) to pair `.ipynb` with `.py` if you want notebooks in git history without committing outputs.

See [notebooks](../notebooks/SKILL.md) for the full discipline.

## Checklist before committing

- [ ] `uv run ruff format . && uv run ruff check .` clean
- [ ] `uv run pyrefly check` (or `uv run ty check`) clean
- [ ] `uv run pytest` passes on the smoke-test data slice
- [ ] No raw data, large outputs, or `.ipynb_checkpoints/` staged
- [ ] Seeds set on any stochastic code path

## Further reading

- [uv documentation](https://docs.astral.sh/uv/)
- [ruff documentation](https://docs.astral.sh/ruff/)
- [pyrefly](https://github.com/facebook/pyrefly)
- [ty (Astral's type checker)](https://github.com/astral-sh/ty)
- [pytest documentation](https://docs.pytest.org/)
- [Python `pathlib`](https://docs.python.org/3/library/pathlib.html)
- [Real Python: Logging](https://realpython.com/python-logging/)
