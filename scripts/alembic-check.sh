#!/usr/bin/env bash
set -euo pipefail

# Create an isolated PostgreSQL cluster for schema validation. It deliberately
# does not read a .env file or application production settings.
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)
postgres_bin=$(pg_config --bindir)
database_dir=$(mktemp -d "${TMPDIR:-/tmp}/ag-256-postgres.XXXXXX")
database_port=55432
database_name=registration_test
database_user=$(id -un)
python_bin=${PYTHON_BIN:-python3.11}

cleanup() {
    "$postgres_bin/pg_ctl" -D "$database_dir" -m immediate stop >/dev/null 2>&1 || true
    rm -rf "$database_dir"
}
trap cleanup EXIT

"$postgres_bin/initdb" -D "$database_dir" --auth=trust --username="$database_user" >/dev/null
"$postgres_bin/pg_ctl" -D "$database_dir" -o "-h 127.0.0.1 -p $database_port" -w start >/dev/null
"$postgres_bin/createdb" -h 127.0.0.1 -p "$database_port" "$database_name"

export ALEMBIC_DATABASE_URL="postgresql+psycopg://${database_user}@127.0.0.1:${database_port}/${database_name}"

cd "$repository_dir"
"$python_bin" -m alembic upgrade head
"$python_bin" -m alembic check
