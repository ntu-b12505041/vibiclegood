#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
set -o noclobber

postgres_password=$(openssl rand -hex 32)
runtime_password=$(openssl rand -hex 32)
rate_limit_secret=$(openssl rand -hex 32)

cat > .env.deploy.production <<EOF
PUBLIC_ORIGIN=https://vibicle.app
VIBICLE_DOMAIN=vibicle.app
CADDY_TLS_DIRECTIVE=
BIND_ADDRESS=0.0.0.0
HTTP_PORT=80
HTTPS_PORT=443
POSTGRES_DB=vibicle
POSTGRES_USER=vibicle_migrator
POSTGRES_PASSWORD=$postgres_password
RUNTIME_PASSWORD=$runtime_password
RATE_LIMIT_SECRET=$rate_limit_secret
EOF

printf '%s\n' 'Created .env.deploy.production with mode 0600.'
