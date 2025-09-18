# Posit Bakery Template Documentation

This document outlines the available Jinja2 macros in the Posit Bakery templating system for creating Docker images with
package installations.

Macros must be explicitly imported in every file in which they are used.

References:
- [Source Code](./posit_bakery/config/templating/macros)
- [Jinja2 Template Designer Documentation](https://jinja.palletsprojects.com/en/stable/templates/)

## Table of Contents

- [Available Variables](#available-variables)
- [Templating Macros](#templating-macros)
  - [APT Package Management](#apt-package-management)
  - [DNF Package Management](#dnf-package-management)
  - [Python Installation and Package Management](#python-installation-and-package-management)
  - [R Installation and Package Management](#r-installation-and-package-management)
  - [Quarto Installation and Management](#quarto-installation-and-management)

## Available Variables
The following variables are available for use in an image's Jinja2 templates.

Currently, `Containerfile` templates render as a unique file for each variant and OS. Using variant and OS based Jinja2 conditionals outside of `Containerfile` templates is not currently supported and will lead to unexpected results or errors.

- `Image`: A dictionary containing information about the current image, version, variant, and OS.
  - `Image.Name`: The name field of the image, e.g. `package-manager`, `workbench`, `connect`.
  - `Image.DisplayName`: The display name field of the image, e.g. `Package Manager`, `Workbench`, `Connect`.
  - `Image.Version`: The current version being rendered, e.g. `2025.08.0`.
  - `Image.Variant`: The current variant being rendered, e.g. `Standard`, `Minimal`.
  - `Image.OS`: A dictionary containing information about the current OS being rendered.
    - `Image.OS.Name`: The name field of the OS, e.g. `ubuntu`, `debian`, `rhel`.
    - `Image.OS.Family`: The generalized family of the OS, e.g. `debian`, `rhel`.
    - `Image.OS.Version`: The version field of the OS, e.g. `22.04`, `20.04`, `9`, `8`, `8.6`, `7`.
    - `Image.OS.Codename`: The codename of the OS version if defined, e.g. `jammy`, `noble`, `bookworm`.
  - `Image.DownloadURL`: The URL to download a development version artifact for installation. Only defined for development version builds.
- `Path`: A dictionary containing paths relative to the root build context.
  - `Path.Base`: The base path for the build context. Usually the parent directory of `bakery.yaml`.
  - `Path.Image`: The path to the current image's directory.
  - `Path.Version`: The path to the current image version's directory.
- `Dependencies`: A dictionary containing retrieved dependency versions to be used in the image version rendering.
  - `Dependencies.python`: A list of Python versions retrieved based on the version's `dependencies` field (preferred if the version exists) or the image's `dependencyConstraints` field in the `bakery.yaml` configuration. Undefined if no Python version constraints are specified.
  - `Dependencies.R`: A list of R versions retrieved based on the version's `dependencies` field (preferred if the version exists) or the image's `dependencyConstraints` field in the `bakery.yaml` configuration. Undefined if no R version constraints are specified.
  - `Dependencies.quarto`: A list of Quarto versions retrieved based on the version's `dependencies` field (preferred if the version exists) or the image's `dependencyConstraints` field in the `bakery.yaml` configuration. Undefined if no Quarto version constraints are specified.

## Templating Macros

### APT Package Management

#### Importing
To use the APT macros, import the `apt` module in your Jinja2 template:

```jinja2
{%- import "apt.j2" as apt -%}
```

#### Setup Posit Cloudsmith Apt Repositories
Renders commands to set up Posit Cloudsmith apt repositories. Requires `curl` to be installed prior to execution.

```jinja2
{{ apt.setup_posit_cloudsmith() }}
```

To wrap `setup_posit_cloudsmith()` in a Docker RUN statement, use:

```jinja2
{{ apt.run_setup_posit_cloudsmith() }}
```

#### Apt Clean Commands
Renders commands to clean and remove the apt cache to ensure minimal image layers. Clean commands should be run at the end of any RUN
statement that modifies packages, but it is implicitly included in most other macros that modify packages.

```jinja2
{{ apt.clean_command() }}
```

#### Apt Update and Upgrade
Renders commands to update the apt cache, upgrade packages, run dist-upgrade, and remove unneeded packages. Pass `False` to the `clean` argument to skip cleaning the cache if you want to append additional commands. Clean is `True` by default.

```jinja2
{{ apt.update_upgrade(clean = True) }}
```

To wrap `update_upgrade()` in a Docker RUN statement, use:

```jinja2
{{ apt.run_update_upgrade() }}
```

#### Install Packages
Renders commands to install all packages from given list and files.

If `update` is `True`, the apt cache will be updated before installation. If `clean` is `True`, the apt cache will be cleaned after installation. Both are `True` by default.

One of `packages` or `files` must be provided. `packages` can be a list, a comma-separated string, or a single string. `files` can be a list, a comma-separated string, or single string. Positional arguments are accepted for `packages` and `files`, but keyword arguments are recommended for clarity.

```jinja2
COPY {{ Path.Version }}/deps/packages.txt /tmp/packages.txt  # Example copy command
{{ apt.install(packages=["git", "curl"], files=["/tmp/packages.txt"], update=True, clean=True) }}
```

To wrap `install()` in a Docker RUN statement, use:

```jinja2
{{ apt.run_install(packages="git,curl", files="/tmp/packages.txt") }}
```

#### Apt Setup
Performs initial setup, including update, upgrade, installation of essential packages, installation of Posit Cloudsmith repositories, purging removed packages, and cleaning the apt cache.

```jinja2
{{ apt.setup() }}
```

To wrap `setup()` in a Docker RUN statement, use:

```jinja2
{{ apt.run_setup() }}
```

### DNF Package Management

#### Importing
To use the DNF macros, import the `dnf` module in your Jinja2 template:

```jinja2
{%- import "dnf.j2" as dnf -%}
```

#### Setup Posit Cloudsmith DNF Repositories
Renders commands to set up Posit Cloudsmith DNF repositories. Requires `curl` to be installed prior to execution.

```jinja2
{{ dnf.setup_posit_cloudsmith() }}
```

To wrap `setup_posit_cloudsmith()` in a Docker RUN statement, use:

```jinja2
{{ dnf.run_setup_posit_cloudsmith() }}
```

#### DNF Clean Command
Renders commands to clean the dnf package cache. Clean commands should be run at the end of any RUN
statement that modifies packages, but it is implicitly included in most other macros that modify packages.

```jinja2
{{ dnf.clean_command() }}
```

#### DNF Update and Upgrade
Renders commands to upgrade packages, remove unneeded packages, and clean the cache. Pass `False` to the `clean` argument to skip cleaning the cache if you want to append additional commands. Clean is `True` by default.

```jinja2
{{ dnf.update_upgrade(clean = True) }}
```

To wrap `update_upgrade()` in a Docker RUN statement, use:

```jinja2
{{ dnf.run_update_upgrade() }}
```

#### Install Packages
Renders commands to install all packages from given list and files.

If `clean` is `True`, the dnf cache will be cleaned after installation. Clean is `True` by default.

One of `packages` or `files` must be provided. `packages` can be a list, a comma-separated string, or a single string. `files` can be a list, a comma-separated string, or single string. Positional arguments are accepted for `packages` and `files`, but keyword arguments are recommended for clarity.

```jinja2
{{ dnf.install(packages=["git", "curl"], files=["/tmp/packages.txt"], clean=True) }}
```

To wrap `install()` in a Docker RUN statement, use:

```jinja2
{{ dnf.run_install(packages="git,curl", files="/tmp/packages.txt") }}
```

#### DNF Setup
Performs initial setup, including upgrade, installation of essential packages, installation of Posit Cloudsmith repositories, removal of unneeded packages, and cleaning the dnf cache.

```jinja2
{{ dnf.setup() }}
```

To wrap `setup()` in a Docker RUN statement, use:

```jinja2
{{ dnf.run_setup() }}
```

### Python Installation and Package Management

#### Importing
To use the Python macros, import the `python` module in your Jinja2 template:

```jinja2
{%- import "python.j2" as python -%}
```

#### Build and Install Python using UV
Adds a build stage to build Python versions using `uv`. This should only be called prior to the final stage of the build, typically the first call in a Containerfile.

```jinja2
{{ python.build_stage(["3.11", "3.12"]) }}
```

Usually, this should be called with `Dependencies.python` to dynamically specify versions based on the image's `dependencyConstraints` field:

```jinja2
{{ python.build_stage(Dependencies.python) }}
```

To copy the Python installations from the build stage to the current stage, use:

```jinja2
{{ python.copy_from_build_stage() }}
```

#### Get Version Directory
Returns the expected directory for a Python version built with uv.

```jinja2
{{ python.get_version_directory("3.12.11") }}
```

#### Install Packages
Installs packages to a Python version from a list of packages or requirements files.

If `clean` is `True`, requirements files will be removed after they are installed. Clean is `True` by default.

One of `packages` or `requirements_files` must be provided. `packages` can be a list, a comma-separated string, or a single string. `requirements_files` can be a list, a comma-separated string, or single string. Positional arguments are accepted for `packages` and `requirements_files`, but keyword arguments are recommended for clarity.

```jinja2
COPY {{ Path.Version }}/deps/requirements.txt /tmp/requirements.txt  # Example copy command
{{ python.install_packages("3.12.11", packages="numpy,pandas", requirements_files="/tmp/requirements.txt", clean=True) }}
```

To install the same packages to multiple versions and wrap the commands with a `RUN` statement, use:

```jinja2
{{ python.run_install_packages(["3.13.7", "3.12.11"], packages=["numpy", "pandas"], requirements_file="/tmp/requirements.txt") }}
```

Or, to install to all Python versions defined in `Dependencies.python`:

```jinja2
{{ python.run_install_packages(Dependencies.python, packages=["numpy", "pandas"], requirements_file="/tmp/requirements.txt") }}
```

#### Create Symlinks
Render a command to symlink to a Python version directory.

```jinja2
{{ python.symlink_version(version="3.12.11", target="/opt/python/default") }}
```

Render a command to symlink to a Python binary by name.

```jinja2
{{ python.symlink_binary(version="3.12.11", bin_name="python", target="/usr/local/bin/python3.12") }}
```

### R Installation and Package Management

#### Importing
To use the R macros, import the `r` module in your Jinja2 template:

```jinja2
{%- import "r.j2" as r -%}
```

#### Install R
Renders a command to download and runs the Posit `r-install` script for a given version of R. Requires `curl` to be installed prior to execution.

```jinja2
{{ r.install("4.4.3") }}
```

To install multiple R versions and wrap them in `RUN` statements, use:

```jinja2
{{ r.run_install(["4.4.3", "4.5.0"]) }}
```

Usually, this should be called with `Dependencies.R` to dynamically specify versions based on the image's `dependencyConstraints` field:

```jinja2
{{ r.run_install(Dependencies.R) }}
```

#### Get Version Directory
Returns the expected installation directory for an R version.

```jinja2
{{ r.get_version_directory("4.4.3") }}
```

#### Install Packages
Render commands to install R packages from lists and files to the given R version.

One of `packages` or `package_list_files` must be provided. `packages` can be a list, a comma-separated string, or a single string. `package_list_files` can be a list, a comma-separated string, or single string. Positional arguments are accepted for `packages` and `package_list_files`, but keyword arguments are recommended for clarity.

The macro takes a `_os` argument to specify the target OS. The OS information is used to find a suitable p3m.dev repository URL for binary packages. If no OS is provided or does not appear supported, source packages will be used by default. It is suggested to always pass `_os=Image.OS` to reduce build times and image size.

If `clean=True` and `package_list_files` is provided, the files will be removed after installation. Clean is `True` by default.

```jinja2
COPY {{ Path.Version }}/deps/packages.txt /tmp/packages.txt  # Example copy command
{{ r.install_packages("4.4.3", packages="ggplot2,dplyr", package_list_files="/tmp/packages.txt", _os=Image.OS, clean=True) }}
```

To install the same packages to multiple R versions and wrap the commands with a `RUN` statement, use:

```jinja2
{{ r.run_install_packages(["4.4.3", "4.5.0"], packages="ggplot2,dplyr", _os=Image.OS) }}
```

Or, to install to all R versions defined in `Dependencies.R`:

```jinja2
{{ r.run_install_packages(Dependencies.R, packages="ggplot2,dplyr", _os=Image.OS) }}
```

#### Create Symlinks
Render a command to symlink to an R version directory.

```jinja2
{{ r.symlink_version(version="4.4.3", target="/opt/R/default") }}
```

Render a command to symlink to an R binary by name.

```jinja2
{{ r.symlink_binary(version="4.4.3", bin_name="R", target="/usr/local/bin/R") }}
```

### Quarto Installation and Management

#### Importing
To use the Quarto macros, import the `quarto` module in your Jinja2 template:
```jinja2
{%- import "quarto.j2" as quarto -%}
```

#### Install Quarto
Returns the command to download and install a Quarto version. Requires `curl` to be installed prior to execution.

The macro takes an optional `with_tinytex` argument to include the command to install TinyTeX using the installed Quarto binary. Default is `False`.

```jinja2
{{ quarto.install("1.8.24", with_tinytex=True) }}
```

To install multiple Quarto versions and wrap them in `RUN` statements, use:

```jinja2
{{ quarto.run_install(["1.8.24", "1.9.0"], with_tinytex=True) }}
```

Usually, this should be called with `Dependencies.quarto` to dynamically specify versions based on the image's `dependencyConstraints` field:

```jinja2
{{ quarto.run_install(Dependencies.quarto, with_tinytex=True) }}
```

#### Get Version Directory
Returns the expected directory for an installed Quarto version.

```jinja2
{{ quarto.get_version_directory("1.8.24") }}
```

#### Install TinyTeX
Returns the command to install TinyTeX using a given Quarto binary.

This command takes a full path to the Quarto binary, which can be constructed using `quarto.get_version_directory()`. Workbench manages its own installation of Quarto and thus must specify its own full path to the Quarto binary.

```jinja2
{{ quarto.install_tinytex_command(quarto.get_version_directory("1.8.24")) }}
```

#### Create Symlinks
Creates a symlink to a Quarto version directory.

```jinja2
{{ quarto.symlink_version(version="1.8.24", target="/opt/quarto/default") }}
```

Creates a symlink to a Quarto binary by name.

```jinja2
{{ quarto.symlink_binary(version="1.8.24", bin_name="quarto", target="/usr/local/bin/quarto") }}
```
