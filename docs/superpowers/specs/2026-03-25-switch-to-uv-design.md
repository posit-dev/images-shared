# Switch posit-bakery from poetry to uv

**Date:** 2026-03-25
**Branch:** feature/use-uv

## Overview

Replace all poetry tooling in the `posit-bakery` project with `uv`. The migration covers the build system, dependency management, dev tooling, and CI. The change is done in a single pass (no phased rollout).

## Scope

Files changed:

- `posit-bakery/pyproject.toml`
- `posit-bakery/justfile`
- `posit-bakery/poetry.toml` — deleted
- `posit-bakery/poetry.lock` — deleted (replaced by `uv.lock`)
- `.github/workflows/ci.yml`

Files unchanged:

- `setup-bakery/action.yml` — installs via `pipx install git+...` using PEP 517 directly; no poetry involvement

## Design

### 1. `pyproject.toml`

**Build system** — replace `poetry-core` + `poetry-dynamic-versioning` with `uv-dynamic-versioning`:

```toml
[build-system]
requires = ["uv-dynamic-versioning"]
build-backend = "uv_dynamic_versioning"
```

**Dynamic versioning config** — rename `[tool.poetry-dynamic-versioning]` to `[tool.uv-dynamic-versioning]`. The Jinja2 format string and all variables (`base`, `distance`, `commit`, `serialize_pep440`, `bump_version`, etc.) are identical; both back onto `dunamai`.

**Dev dependencies** — replace `[tool.poetry.group.dev.dependencies]` and the `[tool.poetry]` version placeholder with a PEP 735 dependency group:

```toml
[dependency-groups]
dev = [
    "ruff>=0.12.9,<1.0.0",
    "mypy~=1.17.1",
    ...
]
```

**Dependency syntax** — several runtime dependencies use poetry's `"pkg (>=x,<y)"` syntax (space before parenthesis). These are updated to standard PEP 508: `"pkg>=x,<y"`.

### 2. File deletions

- `posit-bakery/poetry.toml` — configured `virtualenvs.in-project = true`. uv creates `.venv` in the project directory by default; no replacement needed.
- `posit-bakery/poetry.lock` — replaced by `uv.lock` (generated on first `uv sync`).

### 3. `posit-bakery/justfile`

| Before | After |
|--------|-------|
| `poetry install` | `uv sync` |
| `poetry build` | `uv build` |
| `poetry run -- pytest` | `uv run pytest` |
| `_setup-poetry` recipe | `_setup-uv` recipe |

The `_setup-uv` recipe checks for `uv` and falls back to the root justfile's `_python-executable` helper (which already mentions `uvx`).

### 4. CI (`ci.yml`)

Both `test` and `release` jobs are updated identically:

**Remove:**
- `pipx install poetry` step
- `pipx inject poetry "poetry-dynamic-versioning[plugin]"` step (release job only)
- `actions/setup-python@v5` with `cache: "poetry"`

**Add:**
```yaml
- name: Setup uv
  uses: astral-sh/setup-uv@v5
  with:
    python-version-file: "posit-bakery/pyproject.toml"
```

**Replace:**
- `poetry install` → `uv sync`
- `poetry run pytest ...` → `uv run pytest ...`
- `poetry build` → `uv build`

## Non-goals

- No changes to `setup-bakery/action.yml`
- No changes to sibling repositories
- No changes to runtime behaviour of `posit-bakery` itself
