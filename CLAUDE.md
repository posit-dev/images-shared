# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Posit Bakery is a command-line tool for building, testing, and managing containerized images. It provides a structured approach to create, build, and test Docker images with variant support (e.g., Standard vs Minimal), version management, OS variants, and dependency constraints.

The tool uses a YAML configuration file (`bakery.yaml`) and Jinja2 templates to define image builds, with support for parallel building via Docker Buildx Bake.

## Development Environment Setup

Run these commands from the `posit-bakery/` directory:

```bash
# Install dependencies
pipx install 'poetry>=2'
just setup

# Install the project locally
just install

# Run tests (skipping slow tests)
just test

# Run all tests
just test-all
```

## Repository Structure

This is a monorepo containing multiple projects:

- `posit-bakery/` - The main Posit Bakery CLI tool
  - `posit_bakery/` - Core Python package
    - `cli/` - Command-line interface implementation
    - `config/` - Configuration handling and validation
      - `dependencies/` - Dependency management (Python, R, Quarto versions)
      - `image/` - Image configuration models (variants, versions, matrices)
      - `templating/` - Jinja2 template definitions and macros
      - `tools/` - Tool configurations (goss)
    - `image/` - Image building and management
      - `bake/` - Docker Buildx Bake integration
      - `goss/` - Goss testing integration
    - `registry_management/` - Registry APIs (DockerHub, GHCR)
    - `services/` - Registry container services
  - `test/` - Test suite
- `setup-bakery/` - Bakery setup utilities
- `setup-goss/` - Goss testing setup utilities
- `presentations/` - Project presentations

## Key Commands

Commands support aliases for convenience:
- `build` → `b`, `bake`
- `create` → `c`, `new`
- `run` → `r`
- `update` → `u`, `up`
- `remove` → `rm`

### Creating a New Project

```bash
# Initialize a new bakery project
bakery create project
```

### Creating a New Image

```bash
# Create a new image template
bakery create image <image-name>
```

This creates:
- A directory for the image with the specified name
- A `template/` subdirectory with Jinja2 templates
- Default templates for Containerfile, package list, and tests
- Updates the `bakery.yaml` file with the new image

### Creating a New Image Version

```bash
# Create a new version of an existing image
bakery create version <image-name> <version>
```

This creates:
- A versioned directory under the image directory
- Renders templates with version-specific values
- Updates `bakery.yaml` with the new version

### Building Images

```bash
# Preview the bake plan without building
bakery build --plan

# Build all images in the project
bakery build

# Build a specific image
bakery build --image-name <image-name>

# Build a specific version
bakery build --image-version <version>

# Build a specific variant
bakery build --image-variant <variant>

# Build a specific OS
bakery build --image-os <os>
```

The build command supports two strategies:
- `--strategy bake` (default): Uses Docker Buildx Bake for parallel building
- `--strategy build`: Sequential builds with Docker, Podman, or nerdctl

### Running Tests

```bash
# Run dgoss tests against all images
bakery run dgoss

# Run dgoss tests against a specific image
bakery run dgoss --image-name <image-name>
```

### Updating Files and Versions

```bash
# Re-render templates to version files
bakery update files

# Re-render templates for a specific image/version
bakery update files --image-name <image-name> --image-version <version>

# Patch an existing version to a new version (preserves config)
bakery update version patch <image-name> <old-version> <new-version>
```

### Removing Images and Versions

```bash
# Remove an entire image and its configuration
bakery remove image <image-name>

# Remove a specific version from an image
bakery remove version <image-name> <version>
```

### CI/CD Operations

```bash
# Generate a JSON matrix for CI workflows
bakery ci matrix

# Generate matrix for a specific image
bakery ci matrix <image-name>

# Merge multi-platform build metadata files
bakery ci merge <metadata-file1> <metadata-file2> ...
```

### Registry Cleanup

```bash
# Clean dangling build caches in GHCR
bakery clean cache-registry <registry>

# Clean temporary images in GHCR
bakery clean temp-registry <registry>

# Dry run to preview what would be deleted
bakery clean cache-registry <registry> --dry-run
```

### Creating a Matrix-Based Image

```bash
# Create a matrix configuration for multi-dimensional builds
bakery create matrix <image-name> \
  --dependency-constraint '{"dependency": "R", "latest": true, "count": 2}' \
  --dependency-constraint '{"dependency": "Python", "latest": true, "count": 2}'
```

## Architecture Concepts

### Project Structure

```
.
├── bakery.yaml          # Main configuration file
├── image-name/          # Directory for each image
│   ├── 2024.12.0/       # Directory for each version
│   ├── 2025.01.0/
│   └── template/        # Jinja2 templates for the image
└── another-image/
    ├── 2025.02.0/
    └── template/
```

### Configuration Schema

The `bakery.yaml` file defines:
- Repository metadata
- Registry configuration
- Image definitions with:
- Variants (e.g., Standard, Minimal)
- Versions with OS support
- Dependency constraints

### Image Templating System

Bakery uses Jinja2 for templating with specialized macros for:
- APT/DNF package management
- Python installation and package management
- R installation and package management
- Quarto installation and management

Template variables available:
- `Image`: Information about the current image, version, variant, and OS
- `Path`: Directory paths in the build context
- `Dependencies`: Versions of dependencies like Python, R, and Quarto

Custom Jinja2 filters:
- `tagSafe`: Make strings safe for image tags (replaces invalid characters)
- `stripMetadata`: Remove version metadata (e.g., `1.0.0+build` → `1.0.0`)
- `condense`: Remove spaces, dots, and dashes
- `regexReplace`: Regex-based string replacement
- `quote`: Wrap string in double quotes
- `split`: Split string by separator

## Build Process

1. `bakery build` reads the `bakery.yaml` configuration
2. Generates a Docker Buildx Bake plan (`.docker-bake.json`)
3. Invokes Docker Buildx to build images in parallel
4. Optionally loads images into Docker or pushes to registries

## Testing Process

1. `bakery run dgoss` finds images to test based on configuration
2. Executes dgoss tests against each image with appropriate test files
3. Collects and reports test results

## Image Tagging

Bakery automatically applies tag patterns based on:
- Version (`<version>-<os>-<type>`)
- Latest version markers (`<os>-<type>`, `latest`)
- Primary OS and variant combinations

## Advanced Usage

### Adding Dependencies

Define dependency constraints in the `bakery.yaml` file:

```yaml
dependencyConstraints:
  - dependency: python
    constraint:
      latest: true
      count: 2
  - dependency: R
    constraint:
      max: "4.4"
      count: 1
```

### Custom Templates

Create custom Jinja2 templates in the image's `template/` directory with the `.jinja2` extension.

### Custom Tag Patterns

Define custom tag patterns in the `bakery.yaml` file:

```yaml
tagPatterns:
  - patterns: ["{{ Version }}-{{ OS }}"]
    only:
      - "primaryVariant"
```

### Image Matrices

For images that need multiple dependency combinations (e.g., different R and Python versions), use image matrices instead of individual versions:

```yaml
images:
  - name: my-image
    matrix:
      namePattern: "r{{ R }}-py{{ Python }}"
      subpath: matrix
      dependencies:
        - dependency: R
          versions: ["4.3.3", "4.4.1"]
        - dependency: Python
          versions: ["3.11", "3.12"]
```

This generates versions for each combination of dependencies.

### Multi-Platform Builds

For CI workflows using native builders (instead of QEMU emulation):

1. Build for each platform separately with `--temp-registry`:
   ```bash
   bakery build --strategy build --platform linux/amd64 --metadata-file amd64.json --temp-registry ghcr.io/org
   bakery build --strategy build --platform linux/arm64 --metadata-file arm64.json --temp-registry ghcr.io/org
   ```

2. Merge the metadata files into multi-platform manifests:
   ```bash
   bakery ci merge amd64.json arm64.json
   ```
