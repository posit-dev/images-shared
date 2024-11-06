# Template for a base image Containerfile
TPL_BASE_CONTAINERFILE = """FROM {{ base_image }}:{% raw %}{{ base_image_version }}{% endraw %}

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

# Template for a product image Containerfile
TPL_PRODUCT_CONTAINERFILE = """FROM {{ base_image }}:{% raw %}{{ base_image_version }}{% endraw %}

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
