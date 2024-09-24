#!/bin/bash

set -e

FULLPATH=$(readlink -f "$2")

if [ -z "$3" ]; then
  build_opts=""
else
  build_opts="--build-option $3"
fi

if [ -z "$4" ]; then
  image_name=""
else
  image_name="--image-name $4"
fi

/app/.venv/bin/bakery $1 --context $FULLPATH $build_opts $image_name
