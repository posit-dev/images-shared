#!/bin/bash

set -e

FULLPATH=$(readlink -f "$2")

if [ -z "$3" ]; then
  opts=""
else
  opts="--option $3"
fi

if [ -z "$4" ]; then
  image_name=""
else
  image_name="--image-name $4"
fi

/app/.venv/bin/bakery $1 --context $FULLPATH $opts $image_name
