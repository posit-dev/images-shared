CONTAINER_FILE_TPL = """FROM {{ base_image }}:{% raw %}{{ base_image_version }}{% endraw %}

### ARG declarations ###
ARG SCRIPTS_DIR=/opt/posit/scripts
# Declare your arguments here...

### ENV declarations ###
# Declare your environment variables here...

### Install system packages ###
# Typically, we start with updating and installing system dependencies.

### Install dependencies ###
# Install any dependencies not managed by the system, but required for the application.

### Install application ###
# Call or write an inline script to install the application.

### Configure application/image ###
# If necessary, configure the application or image appropriately if not handled by the application installation.

### Copy scripts ###
# Copy any scripts or files needed for the application to run, such as a startup.sh wrapper script or supervisord configurations.

### Finalize image ###
# Perform any final steps to prepare the image for use, such as setting the entrypoint, command, or exposing ports.
ENTRYPOINT ["tini", "--"]

"""

DOCKER_BAKE_TPL = """variable image_name {
  default = "{{ image_name }}"
}

function get_safe_version {
  # Replaces any "+" with "-"
  params = [version]
  result = replace(version, "+", "-")
}

function get_clean_version {
  # Removes any build metadata from the version
  params = [version]
  result = regex_replace(version, "[+|-].*", "")
}

function get_suffix {
  params = [type]
  result = type == "std" ? "" : "-${type}"
}

function get_tags {
  params = [version, os, type, mark_latest]
  result = concat(
    [
      "${registry}/${namespace}/${image_name}:${os}-${get_clean_version(version)}",
      "${registry}/${namespace}/${image_name}:${os}-${get_clean_version(version)}${get_suffix(type)}",
      "${registry}/${namespace}/${image_name}:${os}-${get_safe_version(version)}",
      "${registry}/${namespace}/${image_name}:${os}-${get_safe_version(version)}${get_suffix(type)}",
    ],
      mark_latest ? ["${registry}/${namespace}/${image_name}:latest${get_suffix(type)}", "${registry}/${namespace}/${image_name}:${os}${get_suffix(type)}"] :
      []
  )
}

group "default" {
  targets = [
    "std",
    "min"
  ]
}

target "std" {
  inherits = ["_"]
  matrix = build_matrix
  name = "${builds.os}-${replace(get_clean_version(builds.version), ".", "-")}-std"
  tags = get_tags(builds.version, builds.os, "std", builds.mark_latest)
  dockerfile = "${image_name}/${builds.version}/Containerfile.${builds.os}.std"
  args = {
    "REGISTRY" = registry
  }
}

target "min" {
  inherits = ["_"]
  matrix = build_matrix
  name = "${builds.os}-${replace(get_clean_version(builds.version), ".", "-")}-min"
  tags = get_tags(builds.version, builds.os, "min", builds.mark_latest)
  dockerfile = "${image_name}/${builds.version}/Containerfile.${builds.os}.min"
  args = {
    "REGISTRY" = registry
  }
}
"""

MATRIX_TPL = """variable build_matrix {
  default = {
    builds = [
      {version = "", os = "", mark_latest = true},
    ]
  }
}

"""
