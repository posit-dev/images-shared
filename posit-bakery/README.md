# Bakery

## Project

## Image

### Versions

### Targets

#### Minimal Image

#### Standard Image

### Image Tags

Bakery adds the following default tags for all versions of the image:

| Standard Image | Minimal Image | Structure |
|:---------|:--------|:------|
| `2025.01.0-ubuntu-22.04-std` | `2025.01.0-ubuntu-22.04-min` | `<version>-<os>-<type>` |
| `2025.01.0-ubuntu-22.04` | ❌ | `<version>-<os>`|
| *Added if `os == primary_os`* | | |
| `2025.01.0-std` | `2025.01.0-min` | `<version>-<type>` |
| `2025.01.0` | ❌ | `<version>` |

Bakery also adds the following tags to the latest image version:

| Standard Image | Minimal Image | Structure |
|:---------|:--------|:------|
| `ubuntu-22.04-std` | `ubuntu-22.04-min` | `<os>-<type>` |
| `ubuntu-22.04` | ❌ | `<os>` |
| *Added if `os == primary_os`* | | |
| `std` | `min` | `<type>` |
| `latest` | ❌ | `latest` |
