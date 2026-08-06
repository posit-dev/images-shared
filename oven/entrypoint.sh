#!/usr/bin/env bash
set -euo pipefail

: "${BAKERY_REPO_PATH:?BAKERY_REPO_PATH must be set to the images-shared checkout path}"

uv sync --directory "${BAKERY_REPO_PATH}/posit-bakery"

cat > /opt/oven/bin/bakery <<EOF
#!/usr/bin/env bash
exec uv run --directory "${BAKERY_REPO_PATH}/posit-bakery" bakery "\$@"
EOF
chmod +x /opt/oven/bin/bakery

exec "$@"
