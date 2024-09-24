CONTAINER_FILE_TPL = """FROM {{ base_image }}:{% raw %}{{ base_image_version }}{% endraw %}

### ARG declarations ###
ARG SCRIPTS_DIR=/opt/posit/scripts
# Declare your arguments here...

### ENV declarations ###
# Declare your environment variables here...

### Copy scripts ###
COPY --chmod=0755 common/scripts $SCRIPTS_DIR

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

DOCKER_BAKE_TPL = """variable os {
  default = "{{ base_image }}"
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

function get_tags {
  params = [version, type, mark_latest]
  result = concat(
    [
      "${registry}/${namespace}/${image_name}:${os}{replace(version, ".", "")}${get_suffix(type)}"
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
  name = "${get_tag(builds.version, "std")}"
  tags = [
    "${registry}/${namespace}/${image_name}:${get_tag(builds.version, "std")}"
  ]
  labels = {
    "co.posit.image.type" = "std"
    "co.posit.image.os" = "${os}"
    "co.posit.image.version" = "${builds.version}"
    "co.posit.internal.goss.test.wait" = "0"
    "co.posit.internal.goss.test.path" = "${os}/${builds.version}/test"
    "co.posit.internal.goss.test.deps" = "${os}/${builds.version}/deps"
  }
  dockerfile = "${os}/${builds.version}/Containerfile.std"
}

target "min" {
  inherits = ["_"]
  matrix = build_matrix
  name = "${get_tag(builds.version, "min")}"
  tags = [
    "${registry}/${namespace}/${image_name}:${get_tag(builds.version, "min")}"
  ]
  labels = {
    "co.posit.image.type" = "min"
    "co.posit.image.os" = "${os}"
    "co.posit.image.version" = "${builds.version}"
    "co.posit.internal.goss.test.wait" = "0"
    "co.posit.internal.goss.test.path" = "${os}/${builds.version}/test"
    "co.posit.internal.goss.test.deps" = "${os}/${builds.version}/deps"
  }
  dockerfile = "${os}/${builds.version}/Containerfile.min"
}

"""

MATRIX_TPL = """variable build_matrix {
  default = {
    builds = [
    ]
  }
}

"""
