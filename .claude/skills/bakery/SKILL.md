---
name: bakery
description: >
  Use when working in any Posit container image repo (images-connect,
  images-workbench, images-package-manager, images-shared) on tasks involving:
  editing Containerfile templates, adding or updating image versions, running
  bakery commands, or modifying CI workflows that call bakery ci matrix/merge.
  Encodes critical invariants and common workflows to prevent known mistakes.
---

# bakery

Posit Bakery is the CLI for building, testing, and managing container images across
the posit-dev image repos. This skill encodes critical invariants and common workflows.

## Critical invariants

Check these before acting on any bakery-related task.

### 1. Never edit rendered files — only templates

Image repos contain Jinja2 templates in `template/` directories **and** rendered output
in version directories (e.g., `2025.08.0/`). Rendered files are generated — never edit
them directly.

**Always:**
1. Edit the template: `<image>/template/Containerfile.jinja` (or other `.jinja` files)
2. Re-render with filter flags scoped to the most recent version:
   `uv run bakery update files --image-name <name> --image-version <version>`

**Never:** run `uv run bakery update files` without filter flags — it re-renders every
version, which is almost never the right action.

**Exception:** for systematic changes that must land in every version, it is often easier
to render one version, make the change locally in that rendered file to validate it, then
apply the edit to the template and re-render.

### 2. Invoke bakery with `uv run`

Always prefix bakery commands with `uv run`:

```bash
uv run bakery build --plan
uv run bakery update files
uv run bakery create version 1.2.3
```

Bare `bakery` is not on the system PATH — it is installed via uv in the `posit-bakery/`
project and only available through `uv run`.

### 3. Read sibling repos before cross-repo changes

When a task requires editing templates, macros, or `bakery.yaml` in a sibling repo
(`images-connect`, `images-workbench`, `images-package-manager`), read that repo's
`CLAUDE.md` and `bakery.yaml` before making any changes there.

### 4. Forward filter flags to `bakery ci merge`

When modifying a CI workflow that uses `bakery ci merge`, ensure any filter flags
passed to the build step are also passed to the merge step:

- `--dev-versions [include|exclude|only]`
- `--dev-stream [release|preview|daily]`
- `--matrix-versions [include|exclude|only]`

Mismatched flags cause the merge step to match metadata by UID and fan a single built
image out to multiple targets — including targets in the wrong registry. A release
version and a dev-stream version that share the same version number have identical UIDs
and will collide. (Tracked as posit-dev/images-shared#553; fix in PR #554.)

## Common workflows

### Add a new image version

```bash
uv run bakery create version <version>
# Edit the generated template if the new version needs adjustments
uv run bakery update files --image-name <name> --image-version <version>
uv run bakery build --plan   # preview before building
```

### Update a template (Containerfile, goss tests, etc.)

```bash
# Edit the template — never the rendered output
$EDITOR <image>/template/Containerfile.jinja

# Re-render scoped to the most recent version (always specify filters)
uv run bakery update files --image-name <name> --image-version <version>
```

### Build locally

```bash
uv run bakery build --plan                              # dry run
uv run bakery build                                     # build + load into Docker
uv run bakery build --image-name connect --image-version 2025.08.0
```

### Run goss tests

```bash
uv run bakery run dgoss
```

### Inspect the CI matrix

```bash
uv run bakery ci matrix
```

### Debug a CI failure

```bash
gh run list -R posit-dev/<repo>
gh run view <run-id> -R posit-dev/<repo>
gh run view <run-id> -R posit-dev/<repo> --log-failed
```

## Key CLI flags

| Flag | Purpose |
|------|---------|
| `--image-name <name>` | Scope to an image (regex) |
| `--image-version <ver>` | Scope to a version |
| `--image-variant <var>` | Scope to Standard or Minimal |
| `--image-os <os>` | Scope to an OS |
| `--image-platform <plat>` | Scope to a platform (e.g. `linux/amd64`) |
| `--dev-versions [include\|exclude\|only]` | Include/exclude dev-stream versions |
| `--dev-stream [release\|preview\|daily]` | Filter to a specific dev stream |
| `--matrix-versions [include\|exclude\|only]` | Include/exclude matrix versions |
| `--plan` | Print the bake plan and exit (build only) |
| `--push` / `--no-push` | Push to registry after build |
| `--strategy [bake\|build]` | `bake` = Docker Buildx parallel; `build` = sequential |

## Template variables

Available in all Jinja2 templates:

- `Image.Version`, `Image.Variant`, `Image.IsDevelopmentVersion`
- `Image.OS` with `.Name`, `.Family`, `.Version`, `.Codename`
- `Path.Base`, `Path.Image`, `Path.Version`
- `Dependencies.python`, `Dependencies.R`, `Dependencies.quarto` (lists of version strings)

Custom filters: `tagSafe`, `stripMetadata`, `condense`, `regexReplace`, `quote`, `split`
