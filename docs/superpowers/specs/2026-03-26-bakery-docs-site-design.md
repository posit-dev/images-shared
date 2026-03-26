# Bakery Documentation Site Design

## Overview

Turn the four existing Bakery documentation files into a cohesive GitHub Pages site using Quarto with the Posit product-doc-theme. The existing standalone markdown files are migrated into the Quarto project and deleted from their current locations. The `posit-bakery/README.md` is slimmed down to a landing page that links to the full docs.

**Audience:** Internal Posit engineers (primary) and external/community users adopting Bakery.

## Technology

- **Quarto** as the static site generator
- **posit-dev/product-doc-theme** (`posit-docs` project type, v8.1.1+)
- **GitHub Pages** via `gh-pages` branch, deployed by GitHub Actions

## Site Structure

The Quarto project lives at `posit-bakery/docs/`:

```
posit-bakery/docs/
├── _quarto.yml
├── _extensions/posit-docs/     # installed via quarto add posit-dev/product-doc-theme
├── images/                     # Posit logo SVGs for footer (copied from extension assets)
├── index.qmd                   # Getting Started — usage walkthrough, concepts, examples link
├── configuration.qmd           # Full bakery.yaml schema reference
├── templating.qmd              # Jinja2 macros, variables, filters
└── architecture.qmd            # Mermaid process/workflow diagrams
```

## Content Migration

### Pages

| Page | Source | Content |
|---|---|---|
| `index.qmd` | `README.md` | Usage walkthrough (Steps 1-5), Bakery Concepts (project structure, image tags), link to examples repo |
| `configuration.qmd` | `CONFIGURATION.md` | Full `bakery.yaml` schema reference — migrated as-is |
| `templating.qmd` | `TEMPLATING.md` | Jinja2 macro documentation — migrated as-is |
| `architecture.qmd` | `ARCHITECTURE.md` | Mermaid diagrams — migrated as-is, rendered natively by Quarto |

### Deleted Files

After migration, these files are removed from `posit-bakery/`:
- `CONFIGURATION.md`
- `TEMPLATING.md`
- `ARCHITECTURE.md`

### Slimmed-Down README

`posit-bakery/README.md` is rewritten to contain only:
- Project description (1-2 sentences)
- Prerequisites & 3rd party tools table
- Installation instructions
- Link to the full documentation on GitHub Pages
- Link to the examples repo
- Development setup section (contributor-facing)

### Cross-References

Internal links between the docs (e.g., CONFIGURATION.md referencing ARCHITECTURE.md) become relative links between `.qmd` files within the Quarto site.

## Quarto Configuration

`_quarto.yml`:

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

## Deployment

### GitHub Actions Workflow

`.github/workflows/docs.yml`:

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

### One-Time Setup

1. Enable GitHub Pages in repo settings: source = `gh-pages` branch, directory = `/`
2. Enable read/write workflow permissions in repo Settings > Actions
3. Run `quarto publish gh-pages` locally once from `posit-bakery/docs/` to create `_publish.yml`

### .gitignore Additions

Add to `posit-bakery/docs/.gitignore`:
```
_site/
.quarto/
```
