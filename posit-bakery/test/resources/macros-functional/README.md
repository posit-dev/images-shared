# macros-functional

Blackbox tests for Bakery's Jinja2 macros (`posit_bakery/config/templating/macros/`).
Each scenario builds a real image with a macro and asserts its behavior with goss.
`test/config/templating/test_macros.py` checks the rendered shell text; this context
checks that the text works.

Ported from pti's blackbox suite (https://github.com/posit-dev/images-shared/issues/202).

## Layout

- One image per macro module: `macros-syspkg` (apt/dnf), `macros-python`, `macros-r`,
  `macros-quarto`.
- One variant per scenario. The Containerfile branches on `Image.Variant`.
- Every OS in `bakery.yaml` runs every scenario. The per-OS Containerfile templates are
  identical and branch on `Image.OS`.
- `test/goss.yaml` includes only `test/scenarios/<variant name>.yaml` at runtime.
  Non-Containerfile templates render once per version, without a variant or OS, so
  scenario selection and OS differences (`.Env.IMAGE_OS_FAMILY`) happen in goss.

`test/config/templating/test_macros_functional_context.py` enforces the layout. The drift
check in `test_fixture_drift.py` fails if the committed rendered files are stale.

## Running

CI runs this context in five `Functional Tests (<OS>)` jobs
(`.github/workflows/ci.yml`), one per OS. Locally,
from `posit-bakery/`:

```bash
just test-macros                                      # everything
just test-macros --image-name '^macros-r$' --image-os 'Rocky Linux 9'
```

After changing a template or macro, re-render the fixtures:

```bash
uv run bakery update files --all --context test/resources/macros-functional
```

## Adding a scenario

1. Add a variant to the image in `bakery.yaml`.
2. Add a branch for it in the image's Containerfile template, then copy the template to
   every `Containerfile.<os>.jinja2`.
3. Add `template/test/scenarios/<variant name>.yaml` (or `.yaml.jinja2` to use
   `Dependencies` or macro helpers; wrap goss templates in `{% raw %}`).
4. Re-render.

## Adding arm64

Assertions avoid arch-specific paths. To test arm64, add `linux/arm64` to each OS's
`platforms` in `bakery.yaml` and move the CI job to `bakery-build-native.yml`, which
needs a temp registry, as the `bakery-native` job does.

## Not covered

Some pti tests have no macro equivalent and were dropped: Pro Drivers, Jupyter kernel
registration, tini, wait-for-it, apt update-only, and Quarto installs to custom paths.
