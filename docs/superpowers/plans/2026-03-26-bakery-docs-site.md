# Bakery Documentation Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Bakery's four markdown docs into a Quarto GitHub Pages site using the Posit product-doc-theme, slim down the README, and add a CI workflow for deployment.

**Architecture:** A Quarto project at `posit-bakery/docs/` with four `.qmd` pages. The `posit-docs` theme extension provides Posit branding. GitHub Actions renders and deploys to the `gh-pages` branch on push to `main`.

**Tech Stack:** Quarto (>= 1.8.25), posit-dev/product-doc-theme v8.1.1, GitHub Actions (`quarto-dev/quarto-actions`)

---

### Task 1: Scaffold the Quarto project

**Files:**
- Create: `posit-bakery/docs/_quarto.yml`
- Create: `posit-bakery/docs/.gitignore`

- [ ] **Step 1: Create the docs directory**

```bash
mkdir -p posit-bakery/docs
```

- [ ] **Step 2: Install the Posit product-doc-theme extension**

```bash
cd posit-bakery/docs && quarto add posit-dev/product-doc-theme --no-prompt
```

This creates `posit-bakery/docs/_extensions/posit-docs/` with the theme files.

- [ ] **Step 3: Create `_quarto.yml`**

Write `posit-bakery/docs/_quarto.yml`:

```yaml
project:
  type: posit-docs

website:
  title: "Posit Bakery"
  sidebar:
    - title: "Posit Bakery"
      contents:
        - index.qmd
        - configuration.qmd
        - templating.qmd
        - architecture.qmd
        - text: "Examples"
          href: https://github.com/posit-dev/images-examples/tree/main/bakery

  page-footer:
    left:
      - text: <img src="/images/posit-logos-2024_horiz-full-color.svg" alt="Posit" width="65px" class="light-content posit-footer-logo">
        href: "https://posit.co"
      - Copyright &copy; 2000-2026 Posit Software, PBC
    center: "Posit Bakery"
    right:
      - text: "GitHub"
        href: "https://github.com/posit-dev/images-shared"

format:
  html:
    toc: true
```

- [ ] **Step 4: Copy footer logo images from the extension**

```bash
mkdir -p posit-bakery/docs/images
cp posit-bakery/docs/_extensions/posit-docs/assets/images/posit-logos-2024_horiz-full-color.svg posit-bakery/docs/images/
cp posit-bakery/docs/_extensions/posit-docs/assets/images/posit-logo-fullcolor-TM.svg posit-bakery/docs/images/
```

- [ ] **Step 5: Create `posit-bakery/docs/.gitignore`**

Write `posit-bakery/docs/.gitignore`:

```
_site/
.quarto/
```

- [ ] **Step 6: Commit**

```bash
git add posit-bakery/docs/_quarto.yml posit-bakery/docs/.gitignore posit-bakery/docs/_extensions/ posit-bakery/docs/images/
git commit -m "feat: scaffold Quarto docs site with posit-docs theme"
```

---

### Task 2: Migrate CONFIGURATION.md to configuration.qmd

**Files:**
- Create: `posit-bakery/docs/configuration.qmd`
- Delete: `posit-bakery/CONFIGURATION.md`

- [ ] **Step 1: Create `posit-bakery/docs/configuration.qmd`**

Copy the contents of `posit-bakery/CONFIGURATION.md` into `posit-bakery/docs/configuration.qmd`, adding Quarto frontmatter at the top:

```yaml
---
title: "Configuration"
---
```

Remove the `# Configuration Overview` H1 heading (the `title` frontmatter replaces it).

- [ ] **Step 2: Update internal cross-references**

In `configuration.qmd`, replace these links:

| Old | New |
|---|---|
| `./README.md#image-tags` | `index.qmd#image-tags` |
| `./TEMPLATING.md` | `templating.qmd` |
| `./ARCHITECTURE.md` | `architecture.qmd` |

Specifically, update the "See Also" section at the bottom:

```markdown
## See Also

- [Templating Documentation](templating.qmd) — Jinja2 macros and variables available in image templates
- [Architecture Diagrams](architecture.qmd) — Detailed tool behavior and flow diagrams
- [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) — Real-world `bakery.yaml` files and step-by-step tutorials
```

And update the tag patterns reference in the middle of the file:

```markdown
These patterns mirror the behavior noted in the [Image Tags](index.qmd#image-tags) section of the README.
```

- [ ] **Step 3: Delete the original file**

```bash
git rm posit-bakery/CONFIGURATION.md
```

- [ ] **Step 4: Verify the page renders**

```bash
cd posit-bakery/docs && quarto render configuration.qmd
```

Expected: No errors. Output in `_site/configuration.html`.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/docs/configuration.qmd
git commit -m "feat: migrate CONFIGURATION.md to Quarto docs site"
```

---

### Task 3: Migrate TEMPLATING.md to templating.qmd

**Files:**
- Create: `posit-bakery/docs/templating.qmd`
- Delete: `posit-bakery/TEMPLATING.md`

- [ ] **Step 1: Create `posit-bakery/docs/templating.qmd`**

Copy the contents of `posit-bakery/TEMPLATING.md` into `posit-bakery/docs/templating.qmd`, adding Quarto frontmatter at the top:

```yaml
---
title: "Templating"
---
```

Remove the `# Posit Bakery Template Documentation` H1 heading.

- [ ] **Step 2: Update internal cross-references**

In `templating.qmd`, replace these links in the "See Also" section:

```markdown
## See Also

- [Configuration Documentation](configuration.qmd) — `bakery.yaml` schema reference
- [Architecture Diagrams](architecture.qmd) — Detailed tool behavior and flow diagrams
- [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) — Step-by-step tutorials, including the managed dependencies and matrix images examples
```

- [ ] **Step 3: Delete the original file**

```bash
git rm posit-bakery/TEMPLATING.md
```

- [ ] **Step 4: Verify the page renders**

```bash
cd posit-bakery/docs && quarto render templating.qmd
```

Expected: No errors. Output in `_site/templating.html`.

- [ ] **Step 5: Commit**

```bash
git add posit-bakery/docs/templating.qmd
git commit -m "feat: migrate TEMPLATING.md to Quarto docs site"
```

---

### Task 4: Migrate ARCHITECTURE.md to architecture.qmd

**Files:**
- Create: `posit-bakery/docs/architecture.qmd`
- Delete: `posit-bakery/ARCHITECTURE.md`

- [ ] **Step 1: Create `posit-bakery/docs/architecture.qmd`**

Copy the contents of `posit-bakery/ARCHITECTURE.md` into `posit-bakery/docs/architecture.qmd`, adding Quarto frontmatter at the top:

```yaml
---
title: "Architecture"
---
```

Remove the `# Bakery Architecture` H1 heading.

Quarto renders Mermaid diagrams natively from ````mermaid` fenced code blocks, so the existing diagrams should work as-is. However, Quarto uses a different syntax for Mermaid. Convert each Mermaid block from:

````markdown
```mermaid
flowchart TD
    ...
```
````

To Quarto's native syntax:

````markdown
```{mermaid}
flowchart TD
    ...
```
````

There are 7 Mermaid blocks in the file (Legend, Workflow, Create, Build, Run Tests, Run Security Scans, Publish). Convert all of them.

- [ ] **Step 2: Delete the original file**

```bash
git rm posit-bakery/ARCHITECTURE.md
```

- [ ] **Step 3: Verify the page renders with Mermaid diagrams**

```bash
cd posit-bakery/docs && quarto render architecture.qmd
```

Expected: No errors. Output in `_site/architecture.html`. Open in a browser to confirm Mermaid diagrams render correctly.

- [ ] **Step 4: Commit**

```bash
git add posit-bakery/docs/architecture.qmd
git commit -m "feat: migrate ARCHITECTURE.md to Quarto docs site"
```

---

### Task 5: Create index.qmd from README usage content

**Files:**
- Create: `posit-bakery/docs/index.qmd`

- [ ] **Step 1: Create `posit-bakery/docs/index.qmd`**

Write `posit-bakery/docs/index.qmd` with the usage walkthrough, concepts, and examples content extracted from the current README. This is everything from the "Usage" section through "Image Tags", plus the Examples link.

```yaml
---
title: "Getting Started"
---
```

Then include the following content (migrated from README.md sections):

1. An introductory sentence: "Bakery is a CLI tool that binds together various tools to manage a matrixed build of container images."
2. The **Usage** section (Steps 1-5), starting from "Show the commands available in `bakery`."
3. The **Bakery Concepts** section (Project Structure and Image Tags)
4. The **Examples** section

- [ ] **Step 2: Update internal cross-references**

Replace all `./CONFIGURATION.md` references with `configuration.qmd` and `./TEMPLATING.md` with `templating.qmd`. The specific links to update:

| Old | New |
|---|---|
| `./ARCHITECTURE.md` | `architecture.qmd` |
| `./CONFIGURATION.md#repository` | `configuration.qmd#repository` |
| `./CONFIGURATION.md#registry` | `configuration.qmd#registry` |
| `./CONFIGURATION.md#image` | `configuration.qmd#image` |
| `./CONFIGURATION.md#imagevariant` | `configuration.qmd#imagevariant` |
| `./CONFIGURATION.md#dependencyconstraint` | `configuration.qmd#dependencyconstraint` |
| `./TEMPLATING.md#available-variables` | `templating.qmd#available-variables` |
| `./CONFIGURATION.md#imageversion` | `configuration.qmd#imageversion` |
| `./CONFIGURATION.md#dependencyversions` | `configuration.qmd#dependencyversions` |
| `./CONFIGURATION.md#gossoptions` | `configuration.qmd#gossoptions` |

Also convert the GitHub-flavored `>[!TIP]` callout to Quarto's native callout syntax:

```markdown
::: {.callout-tip}
See the [architecture diagrams](architecture.qmd) for detailed tool behavior.
:::
```

- [ ] **Step 3: Verify the page renders**

```bash
cd posit-bakery/docs && quarto render index.qmd
```

Expected: No errors. Output in `_site/index.html`.

- [ ] **Step 4: Commit**

```bash
git add posit-bakery/docs/index.qmd
git commit -m "feat: create index.qmd with usage walkthrough and concepts"
```

---

### Task 6: Slim down posit-bakery/README.md

**Files:**
- Modify: `posit-bakery/README.md`

- [ ] **Step 1: Rewrite the README**

Replace the entire contents of `posit-bakery/README.md` with:

```markdown
# Bakery

The [bakery](./posit_bakery/) command line interface (CLI) binds together various [tools](#3rd-party-tools) to manage a matrixed build of container images.

## Documentation

Full documentation is available at **[posit-dev.github.io/images-shared](https://posit-dev.github.io/images-shared/)**.

## Prerequisites

* [python](https://docs.astral.sh/uv/guides/install-python/)
* [pipx](https://pipx.pypa.io/stable/how-to/install-pipx/)
* [docker buildx bake](https://github.com/docker/buildx#installing)
* [just](https://just.systems/man/en/prerequisites.html)

### 3rd Party Tools

| Tool                                                                                                                                                                      | Used By                         | Purpose                                                            |
|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------|:-------------------------------------------------------------------|
| [docker buildx bake](https://github.com/docker/buildx#installing)                                                                                                         | `bakery build --strategy bake`  | Build containers in parallel                                       |
| [docker](https://github.com/docker/buildx#installing), [podman](https://podman-desktop.io/docs/installation), or [nerdctl](https://github.com/containerd/nerdctl#install) | `bakery build --strategy build` | Build containers in series                                         |
| [dgoss](https://github.com/goss-org/goss#installation)                                                                                                                    | `bakery run dgoss`              | Test container images for expected content & behavior              |
| [hadolint](https://github.com/hadolint/hadolint#install)                                                                                                                  | to be implemented               | Lint Dockerfile/Containerfile                                      |
| [openscap](https://static.open-scap.org/)                                                                                                                                 | to be implemented               | Scan container images for secure configuration and vulnerabilities |
| trivy                                                                                                                                                                      | to be implemented               | Scan container images for vulnerabilities                          |
| wizcli                                                                                                                                                                     | to be implemented               | Scan container images for vulnerabilities                          |

## Installation

Install `bakery` using `pipx`:

```bash
pipx install 'git+https://github.com/posit-dev/images-shared.git@main#subdirectory=posit-bakery&egg=posit-bakery'
```

## Examples

See the [Bakery Examples](https://github.com/posit-dev/images-examples/tree/main/bakery) repository for step-by-step tutorials on creating and managing container image projects with Bakery.

## Development

### Development Prerequisites

- [just](https://just.systems/man/en/)

    ```bash
    # Show all the just recipes
    just
    ```

- [poetry](https://python-poetry.org/docs/#installing-with-pipx)

    ```bash
    pipx install 'poetry>=2'
    ```
```

- [ ] **Step 2: Verify the README renders correctly on GitHub**

Review the markdown for formatting issues. Confirm no broken links remain to deleted files (CONFIGURATION.md, TEMPLATING.md, ARCHITECTURE.md).

```bash
grep -n "CONFIGURATION\|TEMPLATING\|ARCHITECTURE" posit-bakery/README.md
```

Expected: No output (no references to the deleted files).

- [ ] **Step 3: Commit**

```bash
git add posit-bakery/README.md
git commit -m "docs: slim down README, link to GitHub Pages docs"
```

---

### Task 7: Render and verify the full site locally

**Files:** None (verification only)

- [ ] **Step 1: Render the full site**

```bash
cd posit-bakery/docs && quarto render
```

Expected: No errors. Site output in `posit-bakery/docs/_site/`.

- [ ] **Step 2: Preview the site**

```bash
cd posit-bakery/docs && quarto preview
```

Expected: Opens a browser at `http://localhost:XXXX`. Verify:
- Sidebar navigation shows all four pages plus the Examples external link
- Each page renders correctly with proper headings and TOC
- Mermaid diagrams on the Architecture page render as flowcharts
- Cross-references between pages work (clicking links navigates correctly)
- Footer shows Posit logo, copyright, and GitHub link
- Search works

- [ ] **Step 3: Fix any issues found during preview**

If issues are found, fix them and re-render. Commit fixes:

```bash
git add -A posit-bakery/docs/
git commit -m "fix: address docs rendering issues"
```

---

### Task 8: Add GitHub Actions deployment workflow

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: Create the workflow file**

Write `.github/workflows/docs.yml`:

```yaml
on:
  workflow_dispatch:
  push:
    branches: main
    paths:
      - 'posit-bakery/docs/**'

name: Publish Docs

jobs:
  build-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Quarto
        uses: quarto-dev/quarto-actions/setup@v2

      - name: Render and Publish
        uses: quarto-dev/quarto-actions/publish@v2
        with:
          target: gh-pages
          path: posit-bakery/docs
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Add `.superpowers/` to `.gitignore`**

Append to `.gitignore`:

```
.superpowers/
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/docs.yml .gitignore
git commit -m "ci: add GitHub Actions workflow for docs deployment"
```

---

### Task 9: One-time setup and initial publish

**Files:** None (manual setup steps)

This task documents the manual steps needed to complete the deployment. These are performed once by a repository admin.

- [ ] **Step 1: Enable GitHub Pages**

In the repository settings at `https://github.com/posit-dev/images-shared/settings/pages`:
- Set **Source** to "Deploy from a branch"
- Set **Branch** to `gh-pages` and directory to `/ (root)`

- [ ] **Step 2: Enable workflow write permissions**

In the repository settings at `https://github.com/posit-dev/images-shared/settings/actions`:
- Under **Workflow permissions**, select "Read and write permissions"

- [ ] **Step 3: Run initial publish locally**

```bash
cd posit-bakery/docs && quarto publish gh-pages
```

This creates the `gh-pages` branch and the `_publish.yml` file. Follow the interactive prompts to confirm.

- [ ] **Step 4: Commit the `_publish.yml`**

```bash
git add posit-bakery/docs/_publish.yml
git commit -m "ci: add Quarto publish configuration"
```

- [ ] **Step 5: Verify the site is live**

Visit `https://posit-dev.github.io/images-shared/` and confirm the site loads with all four pages.
