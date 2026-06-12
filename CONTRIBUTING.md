# Maintainer guide

This guide covers common maintenance tasks shared across the Posit container image
repositories (`images-connect`, `images-workbench`, `images-package-manager`). For
product-specific context, examples, and CI workflow details, see `CONTRIBUTING.md` in
the product repository.

## Add a version

The `product-release.yml` workflow creates versions automatically when a product releases. For hotfixes or when the dispatch fails, use the bakery CLI directly.

See [Step 3: Create an image version](https://posit-dev.github.io/images-shared/#step-3-create-an-image-version)
in the bakery getting-started guide for the full command reference.

The `product-release.yml` shared workflow handles automatic releases:

- If the version's edition (e.g., `2026.05`) already exists in `bakery.yaml`, it
  patches it with `bakery update version`.
- If the edition is new, it creates it with `bakery create version`, marking it
  `--mark-latest` if it is newer than the current latest edition.

After any version create or update, re-render templates:

```bash
bakery update files --image-name <name> --image-version <edition>
```

## Add an image

Adding an image means a new entry in `bakery.yaml` and a new `template/` directory.
Follow the existing images in the repo as your model.

See [Step 2: Create an image](https://posit-dev.github.io/images-shared/#step-2-create-an-image)
for the full bakery CLI walkthrough.

When a new image name is added:

- Update the relevant CI caller workflows to include it in the build scope.
- Add goss tests in `template/test/goss.yaml.jinja2`.
- If the image pushes to a separate registry namespace, add a registry entry in
  `bakery.yaml`.

```bash
# Scaffold the image entry and template directory
bakery create image <image-name>
```

## Update dependencies

Bakery resolves dependency versions (Python, R, Quarto) at build time using
`dependencyConstraints` in `bakery.yaml`. A constraint of `latest: true` causes bakery
to query upstream registries for the current latest compatible version.

See [DependencyConstraint](https://posit-dev.github.io/images-shared/configuration.html#dependencyconstraint)
in the configuration reference for the full schema.

To pin a specific version instead of tracking latest, replace the constraint with an
explicit `dependencyVersions` list for the relevant image version. See
[DependencyVersions](https://posit-dev.github.io/images-shared/configuration.html#dependencyversions).

**UV availability:** see [Footguns](#footguns) before adding a new Python minor version.

## Update older versions

Update older versions when a base image or system package receives a Common Vulnerabilities and Exposures (CVE) fix, or when a
shared template change needs to apply retroactively.

#### Procedure

1. Edit the template in `template/`. Never edit the rendered file in the version directory.
2. Re-render: `bakery update files --image-name <name> --image-version <edition>`.
3. Build and test locally:

    ```bash
    bakery build --image-name <name> --image-version <edition>
    bakery dgoss run --image-name <name> --image-version <edition>
    ```

4. Open a pull request (PR) that includes both the template change and the re-rendered version
   directory.

Do not backport cosmetic changes, new feature additions, or non-security dependency upgrades. Backports increase maintenance surface. Reserve them for security fixes and regressions.

## Footguns

- **Never edit rendered files.** Files in version directories (e.g., `<image>/<edition>/Containerfile.<os>.<variant>`) are generated from templates. `bakery update files` silently overwrites any edits there. Always edit the `template/` files.

- **Never work directly on `main`.** Multiple CI sessions may be running concurrently. Use a branch. For changes spanning multiple repos, use a git worktree per repo so each change is isolated from `main`.

- **Python version not yet in UV.** When a new CPython minor version is released, there is a lag before UV's managed Python manifest includes it. `bakery build` fails with a `uv python install` error. Check [UV's download-metadata.json](https://raw.githubusercontent.com/astral-sh/uv/refs/heads/main/crates/uv-python/download-metadata.json) to confirm availability before adding the version.

- **Stale UV base image cache.** Even after UV upstream adds a new Python version, a cached builder layer from a previous run might not know about it. If a build fails on `uv python install` despite the version being in the manifest, clear the cache:

    ```bash
    bakery clean cache-registry ghcr.io/posit-dev
    ```

    The `clean.yml` workflow removes caches older than 14 days on a schedule.

- **Version format mismatch.** Product repos dispatch with raw git-describe versions (e.g., `v2026.03.0-473-g072bb6fd1f`). Bakery normalizes these to semver-with-metadata (e.g., `2026.03.0-dev+473-g072bb6fd1f`). If `bakery ci matrix` produces an empty matrix after a dispatch, the formats did not align. The shared workflows strip a leading `v` automatically. Check the rest of the version string against bakery's normalization.

## Diagnose a build failure

**1. Find the failing run:**

```bash
gh run list -R posit-dev/<product-repo>
```

**2. View the run** to see which job failed (`matrix`, `build-amd64`, `build-arm64`,
`merge`, `readme`):

```bash
gh run view <run-id> -R posit-dev/<product-repo>
```

**3. Read the failed logs:**

```bash
gh run view <run-id> -R posit-dev/<product-repo> --log-failed
```

**4. Common failure modes:**

| Failure | Symptom | Fix |
|---|---|---|
| Python version not in UV | `uv python install` fails — "no managed Python" | Check UV's download-metadata.json; wait or pin |
| Stale UV cache | Same error but version is in manifest | `bakery clean cache-registry ghcr.io/posit-dev` |
| Goss test timeout | Container exits before goss probes | Increase `wait:` in the image's `options` block in `bakery.yaml` |
| Registry auth | Login step fails | Check `DOCKER_HUB_ACCESS_TOKEN` (Docker Hub) or `AWS_ROLE` + `id-token: write` (Amazon ECR) |
| ARM64 runner unavailable | `build-arm64` job queued but never starts | Re-run the job; capacity usually clears |
| Empty matrix after dispatch | `bakery ci matrix` returns `[]` | Dispatched version format didn't match bakery normalization; inspect `image-version` input |
| Dev build pushed without `-preview` | Release version matches current daily dev-channel version | Known issue ([#553](https://github.com/posit-dev/images-shared/issues/553)); check `bakery ci merge` inputs |

For the shared workflow reference (inputs, secrets, flow diagrams), see
[CI.md](https://github.com/posit-dev/images-shared/blob/main/CI.md). For the
cross-repo dispatch chain, see
[CI_CROSS_REPO_WORKFLOWS.md](https://github.com/posit-dev/images-shared/blob/main/CI_CROSS_REPO_WORKFLOWS.md).
