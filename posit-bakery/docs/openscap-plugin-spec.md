# Spec: `openscap` plugin for Bakery (CIS benchmark reporting)

Issue: posit-dev/images-shared#88. Status: **DRAFT v2**. It includes the review feedback and two spike rounds.
Nothing is implemented yet.

## 1. Goal and scope

Add a built-in Bakery tool plugin, `bakery openscap`, that scans Bakery-managed images against a CIS profile with
OpenSCAP and produces reports. Humans or agents then turn those reports into changes in the image definitions.

- **Report-only (approved).** It scans, writes artifacts and prints a summary. Gating is available but off by
  default. The plugin never modifies images.
- **Internal use only.** It does not run in public CI, which sidesteps the CIS-content licensing concern.
- **v1 OS coverage:** Ubuntu 22.04, 24.04 and 26.04, through a generic OS-to-content mapping that extends to other
  distros (section 5). 26.04 has a caveat: there is no upstream CIS content for it yet (section 2.4).
- **Out of scope:** remediation, publishing reports, a `hardened` image type, and public CI integration.

## 2. Evidence

All spikes ran locally with docker 29.9.2, oscap 1.3.9 (host and `ubuntu:24.04` scanner image), oscap 1.4.6
(Chainguard), and SSG v0.1.82 content.

### 2.1 Plugin model (scout)
- A plugin implements `BakeryToolPlugin` and is registered under the `bakery.plugins` entry point in
  `pyproject.toml`.
- `main.py` calls `register_cli` for each plugin, so the plugin gets a top-level `bakery openscap` group.
- Options are `ToolOptions` subclasses keyed by `tool:` in `bakery.yaml`. Variant values fall back to image values
  through `ImageTarget.get_tool_option()`.
- `plugins/builtin/trivy/` is the template. It writes to `results/<tool>/<image>/<uid>.*`.

### 2.2 Scan strategies compared

Baseline: `ubuntu:22.04`, `cis_level1_server`. The reference is a scan run as root in a scanner container.

| Strategy | Root needed | Results pass/fail/n/a/err | Verdict |
|---|---|---|---|
| Host `oscap`, non-root `docker export \| tar -x`, `OSCAP_PROBE_ROOT` | no | 103/30/264/1 | **Wrong.** 24 false failures from ownership loss, and chroot-based probes error |
| Host `oscap`, root-extracted rootfs, non-root scan | no | 126/8/264/0 | **Wrong, silently.** Unreadable `/etc/shadow` gives a false failure, with no error emitted |
| Host `oscap` with `unshare -r` | no | 125/9 | **Wrong.** gid 42 (shadow) cannot be mapped |
| Host `oscap` with `fakeroot` state file | no | 127/7 | Matches the reference, but the state file breaks if the tree is moved. Too fragile |
| **Scanner container, export into a docker volume, `OSCAP_PROBE_ROOT=/target`** | root inside the container only | **127/7/264/0** | **Reference.** Nothing root-owned lands on the host |
| **Scanner container, `--mount type=image,source=<img>,target=/target`** | root inside the container only | **127/15/256/0** | **Recommended.** No copy. The 8 extra results are correct, because there is no injected `/.dockerenv` (see 2.3) |
| `apt install` oscap inside the target container (live) | yes | broken | **Rejected.** 22.04 only has `libopenscap8` 1.2.17, which produces OVAL errors. It also pollutes the package DB being scanned |
| Bind-mount the host oscap binary and libs into a live target, `docker exec` | no | 129/5 | Works, but it is a 68 MB glibc-tied bundle and fragile. The 2 differences are `root_path_*` rules that read the environment. Not worth it |
| `oscap-docker` / `oscap-podman` | yes | not run | Rejected (see 2.5) |

**Answer to "can we scan inside a live container by mounting in oscap?":** it is feasible (last-but-one row), but
it only changes the result of 2 PATH rules, at a large cost in fragility. The better variant of the same idea flips it
around. Run oscap in its own **scanner container** and mount the **target image** read-only into it with
`--mount type=image`. This needs no export, no root on the host, and no pollution of the target. It also needs no
`oscap` on the host, because the scanner image is the dependency.

### 2.3 Offline-probe coverage (L2 server, 500 rules, 22.04)

| Category | Count | Examples | How v1 handles it |
|---|---|---|---|
| A. Meaningful in a container, works offline | 241 | `package_telnet_removed`, `sshd_disable_root_login`, `accounts_password_pam_unix_enabled` | Reported |
| B. Meaningful but broken offline | 47 | `file_owner_etc_passwd` (fixed by running as root in the scanner), `service_cron_enabled` (systemd probes give `unknown`) | Ownership rules are fixed by the strategy. Systemd results are reported as `unknown`, not as failures |
| C. Host or kernel only | 155 | `sysctl_net_ipv4_ip_forward`, `kernel_module_hfs_disabled`, `audit_rules_immutable`, `partition_for_*`, grub, aide | Removed by a shipped **container tailoring** |
| D. Not applicable by design | 57 | `package_gdm_removed`, `dconf_gnome_*` | Shown as N/A |

Further findings:
- **dpkg package rules read the rootfs and not the host.** Proof: the host has telnet installed, yet the base image
  scan reports `package_telnet_removed` = pass. In a derived image with telnet, rsh, talk, nis, prelink or rsync
  installed, those rules flipped to fail.
- **sysctl rules do not leak the host.** The config-file half reads the rootfs `/etc/sysctl.d`. The runtime half is
  always false.
- **Most `notapplicable` results come from CPE gating, not from missing probes.**
  - `system_with_kernel` is satisfied only when the `linux-base` package is installed. Container images do not have
    it, which accounts for about 289 of 370 N/A results.
  - `machine` and `not_container` are false when `/.dockerenv` exists, and `docker export` injects that file.
- **Host leak.** The `uname` probe reports the host kernel. This affects few rules, and they are covered by the
  category C tailoring.
- **Tailoring works.** `autotailor -p cis_level2_server_container -u <rule>...` produced a tailored profile, and
  `--tailoring-file` reduced the selected rules from 500 to 345. A hand-written XCCDF 1.2 tailoring file also works.
- **Ubuntu 24.04 behaves like 22.04.** L1 server, 408 rules: 97 pass, 40 fail, 270 N/A, 1 error.
- **Known error.** `file_ownerships_var_log` errors in every 22.04 run. It is not yet investigated.

### 2.4 Content (ComplianceAsCode / SCAP Security Guide)

- Repo: <https://github.com/ComplianceAsCode/content> (BSD-3-Clause, active).
- Releases: <https://github.com/ComplianceAsCode/content/releases>. The latest is
  **[v0.1.82](https://github.com/ComplianceAsCode/content/releases/tag/v0.1.82)** (2026-09-01). Recent releases:
  v0.1.81 (2026-06), v0.1.80 (2026-03), v0.1.79 (2025-11). The cadence is roughly quarterly.
- Assets: `scap-security-guide-<ver>.{zip,tar.gz,tar.bz2}`, each with a `.sha512`. Example:
  `https://github.com/ComplianceAsCode/content/releases/download/v0.1.82/scap-security-guide-0.1.82.zip`
  (183 MB, with all `ssg-<product>-ds.xml` built).
- CIS profiles available in v0.1.82:

| Datastream | CIS profiles |
|---|---|
| `ssg-ubuntu2204-ds.xml` | `cis_level{1,2}_{server,workstation}` |
| `ssg-ubuntu2404-ds.xml` | `cis_level{1,2}_{server,workstation}` (plus `stig`) |
| `ssg-ubuntu2604-ds.xml` | **none**. It is a 119 KB stub with 2 rules and no profiles. On upstream master, `products/ubuntu2604/profiles/` has only `default.profile` |
| `ssg-rhel9-ds.xml` | `cis`, `cis_server_l1`, `cis_workstation_l1`, `cis_workstation_l2` |
| also shipped | debian11/12/13, rhel8/10, almalinux9, ol7-10, sle12/15/16, al2023, and others |

**26.04 consequence.** The plugin supports 26.04 structurally: the OS mapping resolves `ssg-ubuntu2604-ds.xml` and
the scan pipeline works. With today's content, a 26.04 target reports **`skipped: no CIS profile in content
v0.1.82`**, not a pass. It starts producing results with no code change once a ComplianceAsCode release ships
26.04 CIS profiles and Renovate bumps the pin.

### 2.5 `oscap-docker` maintenance (decision 2 follow-up)

- **Archived repos you likely found:**
  - [OpenSCAP/openscap-daemon](https://github.com/OpenSCAP/openscap-daemon) (archived, last push 2022)
  - [OpenSCAP/container-compliance](https://github.com/OpenSCAP/container-compliance) (2016)
  - [projectatomic/atomic](https://github.com/projectatomic/atomic) (2020). This is the old `atomic scan`, which
    wrapped OpenSCAP.

  These are separate projects.
- **`oscap-docker` itself** lives in the active [OpenSCAP/openscap](https://github.com/OpenSCAP/openscap) repo
  under `utils/`, on both `main` and `maint-1.3`. OpenSCAP 1.4.6 and 1.3.16 were released in 2026-10. However:
  - The last substantive commit to `utils/oscap-docker` was in **2015**. `oscap-podman` was last touched in 2023.
  - It depends on the Python `docker` SDK and needs root.
  - Open issues: [#2316](https://github.com/OpenSCAP/openscap/issues/2316) (Ubuntu 24.04 image gives 0 results),
    [#2278](https://github.com/OpenSCAP/openscap/issues/2278) (everything `notapplicable`),
    [#2217](https://github.com/OpenSCAP/openscap/issues/2217) (`uname` offline). Python 3.14 breakage was fixed in
    [#2373](https://github.com/OpenSCAP/openscap/issues/2373).
- **Conclusion:** it is shipped but effectively unmaintained, and it is a thin wrapper around the same
  `OSCAP_PROBE_ROOT` mechanism. **Do not depend on it.** The scanner-container approach does the same job with
  Docker primitives that Bakery already uses.

### 2.6 Probe-root / target sanity (risk 1 follow-up)

A min-applicable count is a weak guard. The spike found direct signals that distinguish a correct target scan from a
host scan or a wrong-OS scan:

| Signal | Host or wrong root | Correct target |
|---|---|---|
| Rootfs `/etc/os-release` `ID` / `VERSION_ID` | n/a | matches the datastream product |
| ARF OVAL `<system_info>` `os_name` / `os_version` | host OS (`Pop!_OS 24.04`) | `Ubuntu 22.04.5 LTS` |
| Datastream CPE check `oval:ssg-installed_OS_is_<product>:def:1` | `false` | `true` |
| Canary rule (for example `file_permissions_etc_passwd`) | `notapplicable` | `pass` or `fail` |
| Totals | 0 pass, 0 fail, all N/A | pass + fail > 0 |
| XCCDF `<target>` | host FQDN plus host IPs and MACs | `unknown` and no address facts |

## 3. Commands

```
bakery openscap scan    [FILTERS] [OPTIONS]   # scan built images, write artifacts, print summary
bakery openscap fetch   [OPTIONS]             # download, verify and cache SSG content (CI cache warm-up)
bakery openscap profiles [--image-os ...]     # list profiles available for the resolved datastream(s)
```

`scan` is the core command. `fetch` and `profiles` are thin helpers, because `scan` auto-fetches.

### 3.1 `scan` options
The filters match trivy: `--image-name`, `--image-version`, `--image-variant`, `--image-os`, `--image-platform`,
`--dev-versions`, `--matrix-versions`, `--context`, `--temp-registry`, `--metadata-file`. CLI values override
`bakery.yaml`.

| Option | Default | Meaning |
|---|---|---|
| `--profile` | `cis_level1_server` | Short name or full XCCDF ID |
| `--content-version` | pinned (`0.1.82`) | ComplianceAsCode release |
| `--datastream PATH\|URL` | auto by OS | Override the content mapping |
| `--tailoring PATH\|URL\|builtin:container\|none` | `builtin:container` | Tailoring file. The built-in one removes category C rules (section 2.3) |
| `--skip-rule ID` (repeatable) | none | Rules ignored for gating. They are still reported as `ignored` |
| `--fail-on` | `none` | Gate: `none`, `any`, `high`, `medium` or `low` |
| `--format` | `table,json,html` | Any of `table`, `json`, `markdown`, `html`, `xccdf`, `arf`, `fix` |
| `--output-dir` | `results/openscap` | Output location |
| `--strategy` | `image-mount` | `image-mount` or `export-volume`. The fallback for docker < 28 is auto-selected |
| `--scanner-image` | pinned Bakery scanner image | Image containing `oscap` |
| `--timeout` | 600 | Seconds per target |

## 4. Configuration (`bakery.yaml`)

```yaml
images:
  - name: workbench
    options:
      - tool: openscap
        profile: cis_level1_server
        contentVersion: "0.1.82"   # optional; defaults to the plugin pin
        datastream: null           # optional path or URL override
        tailoring: builtin:container   # or a path or URL (for example from a Security-owned policy repo)
        skipRules: []
        failOn: none
        formats: [table, json, html]
    variants:
      - name: Hardened
        options:
          - tool: openscap
            profile: cis_level2_server
```

`OpenSCAPOptions.update()` merges image-level and variant-level values like the other tool options. A tailoring
file (path or URL) is how the Security team's policy is consumed. Image repos only reference it.

## 5. Generic OS-to-content mapping

The mapping is driven by data, not hard-coded to Ubuntu:

1. Read `ID` and `VERSION_ID` from the target's `/etc/os-release`. With the image-mount strategy this file is read
   from the mounted image itself, not trusted from `bakery.yaml`. The plugin cross-checks it against `Image.OS` and
   warns on mismatch.
2. Derive the product with a small rule table:

   | os-release ID | Product |
   |---|---|
   | ubuntu | `ubuntu` + VERSION_ID without dots (22.04 → `ubuntu2204`) |
   | debian | `debian` + major |
   | rhel, almalinux, ol | `<id>` + major |
   | sles | `sle` + major |
   | amzn | `al2023` |

   Unknown IDs result in `skipped: unsupported OS`.
3. The datastream is `ssg-<product>-ds.xml` from the cached release. A missing file, or a profile missing from the
   datastream (as with 26.04 today), is reported as `skipped` with the reason.
4. Profile aliases cover naming differences. For example, the alias `cis_level1_server` resolves to `cis_server_l1`
   on RHEL 9. The aliases sit in a small dict next to the product rules.

v1 only tests Ubuntu. Other distros work through the same path but are not CI-tested.

## 6. Execution flow (per target)

1. **Resolve content.**
   - Download the pinned release zip once, verify its `.sha512` and extract only the needed `ssg-*-ds.xml` into
     `~/.cache/bakery/openscap/<ver>/`.
   - Resolve the tailoring file (built-in ones are generated per product and profile and shipped as package data).
2. **Pre-flight.** Read `/etc/os-release` from the image (`docker run --rm --mount type=image ... cat`, or read the
   exported tree). Map it to a product, check that the profile exists, and skip with a reason if anything is missing.
3. **Scan.** Run:
   ```
   docker run --rm \
     --mount type=image,source=<ref>,target=/target \
     -v <cache>:/content:ro -v <outdir>:/out \
     -e OSCAP_PROBE_ROOT=/target -e OSCAP_EVALUATION_TARGET=chroot:///target \
     <scanner-image> oscap xccdf eval --profile <id> [--tailoring-file /content/t.xml] \
       --results /out/<uid>.results.xml --results-arf /out/<uid>.arf.xml [--report /out/<uid>.report.html] \
       /content/ssg-<product>-ds.xml
   ```
   The fallback strategy is `docker export` piped into a scanner-side `tar -x` in a throwaway named volume, then the
   same command with the volume mounted at `/target`. The volume is removed afterward. Output files are written as
   the invoking uid (`--user` or a final `chown`), so no root-owned files are left on the host.
4. **Validate** (section 2.6). The target is an **error**, not a pass, if any of these fail:
   - ARF `system_info` `os_name`/`os_version` must match the os-release values.
   - `installed_OS_is_<product>` must be `true`.
   - The canary rule must be pass or fail.
   - pass + fail must be greater than 0.
5. **Parse** the XCCDF `TestResult/rule-result` elements into a typed report:
   - counts for each result type
   - for each failing, error or unknown rule: ID, title, severity, CIS reference IDs, rationale, and the fix text or
     script snippet from the datastream
6. **Write artifacts** and remove temporary volumes. Exit codes 0 and 2 from oscap both mean the scan ran. Exit 1,
   or missing results, means error.

## 7. Output

`results/openscap/<image-name>/<uid>.*`. The directory is wiped at the start of `scan`, as trivy does.

| Format | File | Purpose |
|---|---|---|
| `table` | console | One row per target: Pass, Fail, Unknown, Error, N/A, High, Med, Low, gate |
| `json` | `<uid>.summary.json` | **The primary input for humans and agents.** Target metadata (image, version, variant, OS, digest), content version, profile, tailoring, validation signals, counts, and for each non-pass rule: `{id, title, severity, result, cis_refs[], rationale, fix_bash}` |
| `markdown` | `<uid>.summary.md` | A readable version of the JSON for PRs or issues |
| `html` | `<uid>.report.html` | The native oscap report (about 3 MB) |
| `xccdf` / `arf` | `<uid>.results.xml` / `.arf.xml` | Raw evidence (about 9 MB and 17 MB). The ARF is always produced internally for validation and kept only if requested |
| `fix` | `<uid>.fix.sh` | `oscap xccdf generate fix --fix-type bash` for failing rules. **Reference only.** It targets absolute paths and must never be run on a host |

`fix_bash` in the JSON is what makes the report actionable for agents. It maps each failure to the concrete change
needed in the Containerfile template.

`results()` exits 1 on a validation or scan error or when the gate is breached, and 0 otherwise. `skipped` targets
do not fail the run.

## 8. Packaging and setup

- **Scanner image.** A small Bakery-owned image, `ubuntu:24.04` plus `openscap-scanner` (oscap 1.3.9, about
  264 MB). It is built from a Containerfile in this repo and published to GHCR, pinned by digest.
  - Alternative: `cgr.dev/chainguard/openscap` (oscap 1.4.6). Its free tier is `:latest` only and it is about
    2.5 GB, so it is not preferred.
  - The host needs only docker. **No `oscap` on the host.** This also removes most of the need for a
    `setup-openscap` action.
- **`setup-openscap` (in this monorepo).** It only pre-pulls the scanner image and runs `bakery openscap fetch` with
  `actions/cache` for content. Optional for local use.
- **Renovate pins.**
  - Content: `# renovate: datasource=github-releases depName=ComplianceAsCode/content extractVersion=^v(?<version>.*)$`.
    The `extractVersion` regex is not yet verified against Renovate.
  - Scanner image: digest pinning.

## 9. Code layout

Add `posit_bakery/plugins/builtin/openscap/`:

| File | Contents |
|---|---|
| `__init__.py` | `OpenSCAPPlugin` |
| `options.py` | `OpenSCAPOptions` |
| `content.py` | Release fetch, sha512 check, cache, OS-to-product map, profile aliases |
| `command.py` | `OpenSCAPCommand`, which builds the docker and oscap argv |
| `suite.py` | Per-target pre-flight, scan, validate and cleanup |
| `report.py` | XCCDF and ARF parser, validation, collection, table, JSON and markdown |
| `errors.py` | Error types |
| `tailoring/` | Built-in container tailoring files |
| `scanner/Containerfile` | The scanner image |

Touch:
- `pyproject.toml`: entry point and package data
- `docs/configuration.qmd`, `docs/architecture.qmd`, `README.md`
- Tests: `test/plugins/builtin/openscap/*`, `test/cli/test_openscap.py`, trimmed real `results.xml` and ARF
  fixtures (for 22.04, 24.04, the 26.04 stub, and a host-scan negative case)
- New `setup-openscap/`

## 10. Testing

- **Unit tests** (no docker or oscap): option merging, OS mapping and aliases, content resolution with mocked HTTP
  and sha512 checks, argv building, the parser, all validation guards (with the host-scan fixture as the negative
  case), gate logic, and JSON shape.
- **Suite tests** with `subprocess` mocked, as trivy does.
- **Slow integration tests:**
  - Scan `ubuntu:22.04` and a derived image with `telnet` installed and `chmod 777 /etc/passwd`. Assert the
    `package_telnet_removed` and `file_permissions_etc_passwd` deltas.
  - Assert that 26.04 is `skipped`.

## 11. Remaining open items

1. **Docker version floor.** The `--mount type=image` strategy was verified on docker 29.9. I believe support needs
   Engine 28 or later, but have not verified it. The plugin probes for it and falls back to `export-volume`.
2. **Machine rules and `/.dockerenv`.** The image-mount strategy evaluates `#machine` rules (for example
   `mount_option_dev_shm_*`, `partition_for_tmp`). The built-in tailoring removes them as host-only, so both
   strategies converge.
3. **Systemd `unknown` results.** These are reported as `unknown` with a note, never as pass or fail. A future
   improvement could be a custom check that inspects `*.wants/` symlinks.
4. **`file_ownerships_var_log` error on 22.04.** Not yet investigated. It is reported as an error row and does not
   fail the run unless the gate covers errors.
5. **Built-in tailoring contents.** They come from the spike's regex classification (155 rules for L2 on 22.04) and
   need a human review pass for each product and profile.
6. **Renovate `extractVersion`.** Verify it against the real `v0.1.82` tag.

## 12. Phasing

1. **MVP:** `scan` (image-mount and export-volume), `fetch`, `profiles`, the scanner image, the content cache, the
   built-in container tailoring for ubuntu2204 and ubuntu2404 L1/L2, 26.04 skip handling, validation guards,
   table/JSON/markdown/HTML output, docs, tests and `setup-openscap`.
2. **Later:** an agent workflow that consumes the summary JSON, custom systemd checks, RHEL/Debian testing, and
   baseline/ratchet files.
