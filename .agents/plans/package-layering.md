# Package layering for posit_bakery

Proposal to reorganize `posit-bakery/posit_bakery/` so that the declarative
schema, external resolution, transformation, execution, project mutation, and
CLI layers are separate packages with a one-way dependency rule.

## Current state

~19.7k lines across seven top-level packages. The nominal split is
`config/` (models) → `image/` (targets, bake) → `cli/`, with `plugins/`,
`parallel/`, `registry_management/` alongside. In practice the layers are
tangled:

### Layer violations found

| Symptom | Where |
|---|---|
| Config imports execution | `config/config.py` imports `image.bake`, `image.image_target`, `parallel`, `registry_management.ghcr`, `settings` |
| Execution imports config | `image/image_target.py` imports nine `config.*` modules; `config.tools/__init__.py` imports `config.config` |
| Cycle papered over with local imports | 8 `# avoid circular import` comments (`config.py`, `plugins/registry.py`, `tools/__init__.py`, `protocol.py`) |
| Plugins depend on CLI | `plugins/builtin/{dgoss,hadolint,wizcli}/__init__.py` and `imagetools.py` import `cli.common` |
| Network I/O inside `config/` | `config/dependencies/{python,r,quarto,positron}.py`, `config/image/posit_product/main.py`, `config/image/dev_version/channel.py` |
| Filesystem/templating inside pydantic models | `ImageVersion.render_files`, `ImageMatrix.render_files`, `Image.render_ephemeral_version_files`, `Image.create_version/create_matrix/patch_version` |
| Docker execution on a data model | `ImageTarget.build()`, `ImageTarget.remove()`, `BakePlan.build()` |
| Duplicated selection logic | `cli/ci.py::matrix` re-implements the version/dev/matrix/recent filtering in `BakeryConfig.generate_image_targets` |
| God object | `BakeryConfig` (1366-line file) is a YAML loader, ruamel round-trip writer, scaffolder, target selector, build orchestrator, and registry cleaner |
| Dead package | `services/__init__.py` is a one-line comment |
| Ambiguous naming | `config/image/` (schema) vs `image/` (targets + bake) |

### What is already clean

- `parallel/` — no upward dependencies.
- `registry_management/ghcr`, `registry_management/dockerhub/api|clean` — self-contained (only `readme.py` reaches into `image.image_target`).
- `config/shared.py`, `config/registry.py`, `config/repository.py`, `config/tag.py`, `config/image/{build_os,build_secret,variant,version_os}.py` — pure schema.
- `config/templating/render.py` — env + filters, no model dependency except `dependencies.version`.
- `plugins/builtin/*/{command,suite,report,options}.py` — reasonable internal split per plugin.

### External surface

No sibling repo imports `posit_bakery` Python modules (checked
`images-connect`, `images-workbench`, `images-package-manager`,
`images-examples`). The public surface is the `bakery` CLI, the
`bakery.plugins` entry-point protocol, and the `bakery.yaml` schema. Internal
module paths can move freely; only the plugin `Protocol` and the pydantic
schema need compatibility care.

## Proposed structure

```
posit_bakery/
├── core/            Cross-cutting, depends on nothing internal.
│   ├── const.py
│   ├── errors.py
│   ├── settings.py       (env-driven runtime SETTINGS)
│   ├── log.py
│   ├── retry.py
│   └── util.py
│
├── schema/          Declarative model of bakery.yaml. Pydantic only. No I/O,
│   │                no network, no jinja, no docker.
│   ├── base.py           (BakeryYAMLModel, BakeryPathMixin  — was config/shared.py)
│   ├── document.py       (BakeryConfigDocument, validators only)
│   ├── repository.py
│   ├── registry.py
│   ├── tag.py            (TagPattern; move its jinja rendering to render/)
│   ├── dependencies.py   (DependencyConstraint, DependencyVersions, Version parsing)
│   ├── tools.py          (ToolOptions base + options-class registry + rebuild_tool_models)
│   └── image/
│       ├── image.py
│       ├── variant.py
│       ├── version.py        (fields, validators, derived read-only properties)
│       ├── version_os.py
│       ├── build_os.py
│       ├── build_secret.py
│       ├── matrix.py         (fields, validators, to_image_versions, cartesian logic)
│       ├── parsed_version.py
│       └── dev_version.py    (declarative dev-version specs: base/channel/dependency/spec fields)
│
├── resolve/         Turn declarative specs into concrete values via network.
│   ├── http.py           (cached_session)
│   ├── dependencies/     (python.py, r.py, quarto.py, positron.py fetchers + const URLs)
│   ├── posit_product/    (channel URL table, resolvers, errors — Posit-specific)
│   └── dev_versions.py   (load_dev_versions, _apply_dev_spec, channel resolution)
│
├── render/          Jinja2 templating. Files in, files out.
│   ├── env.py            (jinja2_env, filters, normalize_rendered_output)
│   ├── macros/           (*.j2)
│   ├── templates/        (bakery.yaml.jinja2, Containerfile.jinja2)
│   ├── version.py        (render_version_files(version, variants, filters))
│   ├── matrix.py         (render_matrix_files(matrix, variants, filters))
│   └── tag.py            (render_tag_pattern)
│
├── project/         bakery.yaml file lifecycle and scaffolding. The only
│   │                place that writes bakery.yaml or version directories.
│   ├── loader.py         (find bakery.yaml, ruamel load, validate → Project)
│   ├── document_store.py (ruamel round-trip write, _get_image_index, _get_version_index)
│   ├── scaffold.py       (new project, create_image_files_template)
│   ├── mutations.py      (create/remove image, create/patch/remove version, create matrix)
│   └── ephemeral.py      (render/remove ephemeral dev-version dirs, atexit hook)
│
├── targets/         Transformation: schema → ImageTarget list. Pure.
│   ├── selection.py      (BakerySettings, BakeryConfigFilter, select_targets,
│   │                      apply_recent_versions, version_matches, uid dedupe)
│   ├── target.py         (ImageTarget, Tag, StringableList — properties only, no build/remove)
│   ├── metadata.py       (BuildMetadata, MetadataFile)
│   ├── bake_plan.py      (BakePlan model + from_image_targets; no .build())
│   ├── ci_matrix.py      (flatten selected targets to CI matrix rows — replaces cli/ci.py inline logic)
│   ├── changeset.py      (classify_changes, classify_bakery_yaml_diff)
│   └── dirdiff.py
│
├── build/           Execution against docker/buildx.
│   ├── docker.py         (python_on_whales wrappers: build one target, bake a plan, remove, inspect)
│   ├── runner.py         (build_targets orchestration, strategy switch, retry, metadata merge)
│   └── summary.py        (BuildSummary — inspect sizes/layers)
│
├── registry/        Remote registry HTTP APIs.            (was registry_management/)
│   ├── ghcr/
│   ├── dockerhub/
│   └── clean.py          (clean_caches / clean_temporary over a target list)
│
├── parallel/        Unchanged.
│
├── plugins/
│   ├── protocol.py       (BakeryToolPlugin, ToolCallResult)
│   ├── discovery.py      (entry-point loading, tool-options registration)
│   └── builtin/
│       ├── dgoss/, hadolint/, wizcli/, imagetools/
│       │   ├── cli.py        (typer command registration — the only module importing cli/)
│       │   ├── options.py    (ToolOptions subclass)
│       │   ├── command.py    (subprocess invocation)
│       │   ├── suite.py      (orchestration over targets)
│       │   └── report.py     (rich/markdown output)
│
└── cli/             Typer. Parses args, builds BakerySettings, calls one
    │                function from project/targets/build/registry/plugins,
    │                prints. No business logic.
    ├── main.py
    ├── options.py        (shared decorators — was common.py; exit_if_no_targets moves to targets/)
    ├── build.py, ci.py, clean.py, create.py, get.py, remove.py, run.py, update.py, version.py
    └── reporting.py      (grouped_table — was top-level reporting.py)
```

### Dependency rule

Imports may only point downward in this list. A module may import from any
layer below it, never above or sideways except where noted.

```
cli
plugins/builtin/*/cli.py      → may import cli/options.py
plugins (everything else)
build, registry
targets
project, render, resolve
schema
parallel, core
```

- `schema` must not import `render`, `resolve`, `project`, `targets`, `build`.
- `targets` may import `render` only for `render_tag_pattern` (tag templating is derivation, not file output). If that feels wrong, move tag rendering to `targets/tag.py` and keep `render/` strictly for file output.
- `project` depends on `render` and `resolve` (creating a version renders files; loading with dev versions resolves them). It does not depend on `targets` or `build`.
- `build` and `registry` never import `project`; they receive `list[ImageTarget]` and a `base_path`.
- Enforce with `import-linter` in pre-commit. Cheap and it will catch regressions immediately.

### What replaces `BakeryConfig`

Today every CLI command and plugin does `c = BakeryConfig.from_context(context, settings)` and then reaches for `c.model`, `c.targets`, `c.build_targets(...)`, `c.create_version(...)`. Split into:

```python
# project/loader.py
project = load_project(context)          # Project(document, base_path, config_file, raw_yaml)
                                          # resolves dev versions if settings ask for them

# targets/selection.py
targets = select_targets(project.document, settings)

# build/runner.py
build_targets(base_path, targets, strategy=..., push=..., ...)

# project/mutations.py
create_version(project, image_name, version, ...)
```

`Project` is a thin dataclass; it owns the ruamel document and the validated
pydantic model and nothing else. The `last_build_succeeded_uids` side-channel
becomes a return value of `build_targets`.

### Plugin protocol changes

`register_cli(app: typer.Typer)` stays — plugins own a CLI surface and typer is
already a hard dependency. But:

- Plugin `execute()` receives `base_path` and `targets` (already does). It must not construct a `Project` or call `select_targets` — the CLI layer does that and passes results in.
- Each builtin plugin's `__init__.py` currently holds 300-550 lines of typer command bodies. Move to `cli.py` inside the plugin so `__init__.py` just exports the plugin class.
- `ToolCallResult.target: Any` with a "circular import" comment becomes `ImageTarget` once `targets/` no longer depends on anything that depends on `plugins/`.

### Naming decisions

- `config/` → `schema/`. "Config" is ambiguous (the file? the model? the manager?). `schema` says "this is the shape of bakery.yaml".
- `image/` → split into `targets/` and `build/`. `image/` collides with `config/image/` and mixes derivation with execution.
- `registry_management/` → `registry/`. Shorter; `schema/registry.py` is the *declared* registry, `registry/` is the *remote* one. If that collision is confusing, `remote/` is the alternative.
- `posit_product/` stays Posit-specific inside `resolve/`. It could become a plugin later, but that is a separate decision.
- Delete `services/`.

## Migration order

Each phase is independently shippable and keeps `uv run pytest` green. Add
re-export shims at old paths during the transition and delete them at the end
so test imports can be updated incrementally.

1. **Break the cycle at the top.** Move `build_targets`, `_retry_build`, `clean_caches`, `clean_temporary` out of `config/config.py` into `build/runner.py` and `registry/clean.py`. `config/` no longer imports `image.bake`, `parallel`, or `registry_management`. Highest value, lowest risk — pure function extraction.
2. **Extract target selection.** Move `BakerySettings`, `BakeryConfigFilter`, `generate_image_targets`, `apply_recent_versions`, `version_matches` to `targets/selection.py`. Rewrite `cli/ci.py::matrix` to call `select_targets` and flatten; delete the duplicate loop. Add tests asserting `ci matrix` and `build --plan` agree on the target set.
3. **Extract project mutation.** Move `create_image`, `remove_image`, `create_version`, `patch_version`, `create_matrix`, `remove_version`, `write`, `new`, `_get_*_index`, `create_image_files_template` into `project/`. `Image.create_version/create_matrix/patch_version` become functions taking the image. `BakeryConfig` is now just a loader; rename to `Project`.
4. **Move rendering off the models.** `ImageVersion.render_files` → `render.version.render_version_files(version, ...)`. Same for matrix and ephemeral dirs. Models keep `generate_template_values` (pure dict building).
5. **Move resolvers.** `config/dependencies/{python,r,quarto,positron}.py`, `posit_product/`, `dev_version/` runtime resolution → `resolve/`. `schema/dependencies.py` keeps only the models. `Image.load_dev_versions` → `resolve.dev_versions.load(image, settings)`.
6. **Strip execution from `ImageTarget` and `BakePlan`.** `.build()`, `.remove()` → `build/docker.py`. `image/summary.py` → `build/summary.py`.
7. **Rename packages.** `config/`→`schema/`, `image/`→`targets/`+`build/`, `registry_management/`→`registry/`, top-level singletons → `core/`. Mirror the moves under `test/`. Delete shims and `services/`.
8. **Plugins.** Split each builtin `__init__.py` into `cli.py` + class. Move `exit_if_no_targets` to `targets/selection.py` (it is a "no targets" check, not a CLI concern; the CLI decides what to do with the result).
9. **Add `import-linter` contracts** to pre-commit encoding the dependency rule above.

## Risks and trade-offs

- **Test churn.** `test/` mirrors the package (`test/config/`, `test/image/`, ...). Every rename moves test files and patch targets (`patch("posit_bakery.config.config.time.sleep")` is called out in a docstring). Do renames last and in one commit per package so `git log --follow` stays useful.
- **Pydantic `parent` back-references.** `Image.parent`, `ImageVersion.parent` point up to `BakeryConfigDocument`. That is fine within `schema/`; it does not cross layers. Leave as is.
- **`rebuild_tool_models`** mutates `ImageVariant.model_fields` at runtime after plugin discovery. That stays in `schema/tools.py` but its trigger moves to `plugins/discovery.py`. The local imports there go away once `schema` has no upward dependencies.
- **Over-splitting.** `targets/tag.py` vs `render/tag.py`, `project/document_store.py` vs `project/mutations.py` — collapse if a file ends up under ~50 lines. The layers matter; the file count does not.
- **Not proposed:** abstract interfaces/DI for docker or HTTP. Tests already patch at module boundaries; a cleaner module layout makes those patch points more stable without adding indirection.

## Open questions

- Should `posit_product` resolution be a plugin rather than a core `resolve/` subpackage? It is the only Posit-specific code outside templates and would let the tool be generic. Defer unless there is a concrete need.
- `BakePlan` is a transformation (targets → JSON) with one execution method. Proposed home is `targets/bake_plan.py` for the model and `build/docker.py` for `bake()`. Alternative: keep both in `build/` and accept that `build --plan` reaches into the execution package for a pure function.
- Is `schema/registry.py` vs `registry/` too confusing? Alternative name for the remote-API package: `remote/`.
