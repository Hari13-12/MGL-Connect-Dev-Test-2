#!/usr/bin/env bash
set -euo pipefail

# Use only the isolated PostgreSQL URL supplied by CI or local test harnesses.
# It deliberately does not read a .env file or application production settings.
: "${ALEMBIC_DATABASE_URL:?Set ALEMBIC_DATABASE_URL to the isolated test PostgreSQL database}"

alembic upgrade head
alembic check
