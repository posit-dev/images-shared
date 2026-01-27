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
      - `templating/` - Jinja2 template definitions and macros
    - `image/` - Image building and management
  - `test/` - Test suite
- `setup-bakery/` - Bakery setup utilities
- `setup-goss/` - Goss testing setup utilities
- `presentations/` - Project presentations

## Key Commands

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
