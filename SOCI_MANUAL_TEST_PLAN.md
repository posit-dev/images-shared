# SOCI Manual E2E Test Plan — `feature/soci-images`

Goal: end-to-end replicate **applying a SOCI index to a remote image and pushing it
back**, using the personal registry `cripittwood.azurecr.io`.

This plan works from the lowest level (raw `soci`/`oras`, no bakery) up to the full
bakery CI integration. Run the phases in order; each later phase assumes the earlier
ones passed. You can stop after Phase 2 if you only need to confirm the round-trip
mechanics; Phases 4–5 validate the actual bakery code paths.

---

## Background — what the code does

`SociConvertWorkflow` (`posit_bakery/plugins/builtin/soci/soci.py`) has two modes:

| Mode | Steps | Needs containerd? |
|---|---|---|
| **standalone** (`_run_standalone`) | `oras cp --to-oci-layout` (registry→layout) → `soci convert --standalone --format oci-dir` (layout→layout) → read `index.json` digest → `oras cp --from-oci-layout` (layout→registry) | No |
| **containerd** (default) | `ctr image pull` (probing namespaces `default`, `moby`) → `soci convert` → `soci push` | Yes |

In both modes the destination is `f"{source_ref}-soci"` (the `-soci` suffix is appended
to the source ref).

Entry points, lowest → highest:
1. Raw `oras` + `soci` commands (Phase 2 / Phase 3).
2. `bakery soci convert <metadata.json>` — standalone or containerd (Phase 4).
3. `bakery ci publish` — full merge → soci → copy pipeline (Phase 5). SOCI conversion
   is driven by per-image/variant `soci` options (`enabled: true`), not a CLI flag.

---

## Phase 0 — Prerequisites & environment

```bash
# Confirm tooling (all expected present on this machine)
soci --version          # v0.13.0
oras version            # 1.3.0
ctr --version
docker version
az version

# From the posit-bakery dir, confirm the CLI sees the soci plugin
cd posit-bakery
uv run bakery soci --help
uv run bakery soci convert --help
uv run bakery ci publish --help     # SOCI is config-driven; no --enable-soci flag
```

**Auth to ACR** (oras reads docker credentials, so a docker/az login is enough):

```bash
az acr login --name cripittwood
# or: docker login cripittwood.azurecr.io
# verify oras can talk to it:
oras repo ls cripittwood.azurecr.io | head
```

Shell variables used throughout:

```bash
export REG=cripittwood.azurecr.io
export REPO=soci-test/python
export SRC=$REG/$REPO:base          # the "remote image" we apply SOCI to
```

> **SOCI layer-size note:** SOCI only indexes layers larger than `--min-layer-size`
> (default 10 MiB). Use an image with at least one large layer (`python:3.12-slim`
> works) **or** force-index everything with `--min-layer-size 0`. A tiny image like
> `alpine` with defaults will produce an empty/no-op index and the test won't prove
> anything.

---

## Phase 1 — Seed a source image in ACR

Copy a real multi-layer image into your registry so there's a "remote image" to convert.

```bash
oras cp docker.io/library/python:3.12-slim $SRC
# confirm it landed
oras manifest fetch --descriptor $SRC
```

✅ **Pass:** `oras manifest fetch` returns a descriptor for `$SRC`.

---

## Phase 2 — Standalone round-trip with raw commands (mirrors `_run_standalone`)

This reproduces `SociConvertWorkflow._run_standalone` by hand. No containerd, no bakery.

```bash
SCRATCH=$(mktemp -d -t soci-standalone-XXXX)
SRC_LAYOUT=$SCRATCH/src
OUT_LAYOUT=$SCRATCH/out
DEST=$REG/$REPO:base-soci

# 1. registry -> OCI layout
oras cp --to-oci-layout $SRC "$SRC_LAYOUT:image"

# 2. convert layout -> layout (oci-dir so we can read index.json).
#    --min-layer-size 0 forces indexing of every layer for the test.
soci convert --standalone --format oci-dir --all-platforms \
    --min-layer-size 0 \
    "$SRC_LAYOUT" "$OUT_LAYOUT"

# 3. read the converted manifest digest (soci writes it untagged)
DIGEST=$(jq -r '.manifests[0].digest' "$OUT_LAYOUT/index.json")
echo "converted digest: $DIGEST"

# 4. push converted layout -> registry, referenced by digest
oras cp --from-oci-layout "$OUT_LAYOUT@$DIGEST" "$DEST"

rm -rf "$SCRATCH"
```

**Verify the SOCI-enabled image is in the registry:**

```bash
oras manifest fetch --descriptor $DEST                 # must resolve (this is the verify-workflow check)
oras manifest fetch $DEST | jq '.layers[].mediaType'   # inspect converted manifest
# SOCI artifacts/referrers (ACR supports the OCI referrers API):
oras discover $DEST
```

✅ **Pass:** `$DEST` resolves; manifest/referrers show SOCI ztoc/index content.
❌ **Fail to watch for:** step 4 errors on the `@digest` push, or `oras discover`
shows nothing (likely the source had no layer above `min-layer-size`).

---

## Phase 3 — Standalone via the workflow class (exercises bakery code, no CLI scaffolding)

Confirms `SociConvertWorkflow` itself drives the same round-trip. Run from `posit-bakery/`:

```bash
cd posit-bakery
uv run python - <<'PY'
from unittest.mock import MagicMock
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.plugins.builtin.soci.soci import SociConvertWorkflow

REG = "cripittwood.azurecr.io"
src = f"{REG}/soci-test/python:base"

t = MagicMock(spec=ImageTarget)
t.image_name = "python"; t.uid = "python-1"; t.temp_registry = REG

wf = SociConvertWorkflow(
    soci_bin="soci", ctr_bin="ctr", oras_bin="oras",
    image_target=t,
    options=SociOptions(enabled=True, standalone=True, min_layer_size=0),
    source_ref=src,
    standalone=True,
)
# dry run first to see the exact commands:
print(wf.run(dry_run=True))
# then for real:
res = wf.run()
print(res)
assert res.success, res.error
print("destination:", res.destination_ref)
PY
```

✅ **Pass:** `success=True`, `destination_ref == <src>-soci`, and that ref resolves
via `oras manifest fetch --descriptor`.

---

## Phase 4 — `bakery soci convert` CLI

This is the standalone CLI path driven by build-metadata files. It needs a bakery
project context (a `bakery.yaml` with a target that has SOCI enabled) and a metadata
file whose entry references your seeded image.

### 4a. Minimal project + soci config

Pick a sibling product repo (e.g. `../images-package-manager`) **or** a throwaway test
project. The target you convert must resolve `SociOptions.enabled = True`. SOCI options
attach under a target's `tools:` block in `bakery.yaml`:

```yaml
# in the image-version or variant block
tools:
  - tool: soci
    enabled: true
    standalone: true        # for this CLI path
    min_layer_size: 0       # test-only: force indexing
```

> Verify the exact YAML placement against `SociOptions` / `get_soci_options_for_target`
> — options are read from the image-version parent's `options` and/or the variant's
> `options`, variant winning on conflict.

### 4b. Build-metadata file

`bakery soci convert` reads metadata files, picks each target's most-recent
`build_metadata`, and uses its `image_ref` as the source. Create a metadata JSON keyed
by the target UID:

```json
{
  "<TARGET_UID>": {
    "image.name": "cripittwood.azurecr.io/soci-test/python:base",
    "containerimage.digest": "sha256:<digest-of-base>"
  }
}
```

Get `<TARGET_UID>` from `uv run bakery build --plan` (or your matrix), and the digest
from `oras manifest fetch --descriptor $SRC | jq -r .digest`.

### 4c. Run

```bash
cd <project-with-bakery.yaml>
# dry run prints the soci/oras commands without executing:
uv run bakery soci convert ./metadata.json --standalone --dry-run -vv
# real:
uv run bakery soci convert ./metadata.json --standalone -vv
```

✅ **Pass:** logs `SOCI converted '<target>' -> <ref>-soci` and `✅ SOCI conversion(s)
completed`; the `-soci` ref resolves in ACR.

> ⚠️ **Known edge case to confirm:** the CLI sets the source ref to the metadata
> `image_ref`, which is **digest-pinned** (`repo:tag@sha256:…`). The destination is
> `source_ref + "-soci"` → `repo:tag@sha256:…-soci`, which is **not a valid push
> target**. Watch whether the real (non-dry-run) push step fails here. If it does,
> that's a finding: the clean-tag path is Phase 5, and `bakery soci convert` standalone
> may need a tag-only source ref. Note the exact error for the PR.

---

## Phase 5 — `bakery ci publish` (full pipeline, the production path)

This is the real CI flow: **oras index-create → soci convert → oras index-copy →
verify**. Here `source_ref` is the temp-index *tag* (`…/tmp:<uid><hash>`), so the
`-soci` suffix appends cleanly — this is the path that round-trips correctly.

SOCI conversion is config-driven: the convert phase always runs, but only targets
whose resolved `soci` options have `enabled: true` are actually converted. Targets
without SOCI enabled pass through untouched. Ensure the target you're testing has
`soci` options with `enabled: true` on its image or variant.

Requires per-platform build metadata files (as produced by
`bakery build --strategy build --platform <p> --metadata-file … --temp-registry …`).

```bash
cd <project-with-bakery.yaml>

# Produce single-platform builds pushed to your registry as the temp registry:
uv run bakery build --strategy build --platform linux/amd64 \
    --metadata-file ./meta-amd64.json \
    --temp-registry $REG/soci-test --push <target-filter>

# (optional second platform)
# uv run bakery build --strategy build --platform linux/arm64 \
#     --metadata-file ./meta-arm64.json --temp-registry $REG/soci-test --push <target-filter>

# Dry-run the publish first to inspect the create→soci→copy→verify command sequence:
uv run bakery ci publish ./meta-*.json --temp-registry $REG/soci-test \
    --dry-run -vv

# Real run:
uv run bakery ci publish ./meta-*.json --temp-registry $REG/soci-test -vv
```

What to confirm in the logs / registry:
1. **index-create**: a `…/tmp:<uid><hash>` index is created in `$REG/soci-test`.
2. **soci convert**: workflow runs on the temp ref and produces `…<hash>-soci`.
   The publish loop reassigns `temp_refs[uid]` to that `-soci` ref.
3. **index-copy**: the `-soci` ref is copied out to the target's final destination tags.
4. **verify**: each final tag is `oras manifest fetch --descriptor`'d and logged
   `Verified '<target>' -> <tags>`.

```bash
# After the run, confirm a final destination tag carries the SOCI conversion:
oras manifest fetch --descriptor <final-dest-tag>
oras discover <final-dest-tag>
```

✅ **Pass:** publish exits 0; final destination tags resolve and show SOCI content.
Compare against a target that has `soci.enabled: false` (or no `soci` options) to
confirm it passes through the convert phase untouched (logged as skipped) while the
enabled target gains the SOCI index.

---

## Phase 6 — Containerd (non-standalone) mode — optional, validates the production default

The default (non-standalone) workflow uses containerd directly. Only run this if you
want to validate the `ctr pull → soci convert → soci push` path.

```bash
# containerd must be running and the socket accessible (mirrors setup-soci action):
sudo chmod 666 /run/containerd/containerd.sock

# Raw reproduction of the non-standalone workflow:
sudo ctr --namespace default image pull --all-platforms $SRC
sudo soci --namespace default convert --all-platforms --min-layer-size 0 \
    $SRC "$SRC-soci"
sudo soci --namespace default push --all-platforms --existing-index warn "$SRC-soci"

oras manifest fetch --descriptor "$SRC-soci"
```

Then exercise it through bakery by dropping `standalone: true` from the soci config
(and omitting `--standalone`) in Phase 4 / Phase 5. The workflow probes namespaces
`default` then `moby`; confirm it resolves the namespace the image was pulled into
(`resolved_namespace` in the result).

✅ **Pass:** `$SRC-soci` resolves; `resolved_namespace` matches where `ctr pull` placed
the image.

---

## Cleanup

```bash
# Temp indexes are intentionally left in place by publish (clean.yml handles them in CI).
# For manual cleanup of your test repo:
oras repo tags $REG/$REPO
# delete specific tags as needed via the ACR portal/CLI:
az acr repository delete --name cripittwood --image $REPO:base-soci
```

---

## Results checklist

- [ ] Phase 0: `bakery soci`/`ci publish` help renders; ACR auth works.
- [ ] Phase 1: source image seeded.
- [ ] Phase 2: raw standalone round-trip produces a resolvable `-soci` ref with SOCI content.
- [ ] Phase 3: `SociConvertWorkflow` standalone returns `success=True`.
- [ ] Phase 4: `bakery soci convert --standalone` succeeds **or** the digest-ref edge case is documented.
- [ ] Phase 5: `bakery ci publish` runs create→soci→copy→verify; final tags carry SOCI for `soci.enabled: true` targets.
- [ ] Phase 6 (optional): containerd path round-trips.
