#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v mise >/dev/null 2>&1; then
    printf 'mise is required; run ./scripts/bootstrap.sh --setup first.\n' >&2
    exit 1
fi
if [[ ! -f uv.lock || ! -f pnpm-lock.yaml ]]; then
    printf 'Lockfiles are missing; restore them from Git.\n' >&2
    exit 1
fi

mise exec -- uv sync --frozen
mise exec -- pnpm install --frozen-lockfile --ignore-scripts
mise exec -- pnpm test:pi
printf 'Pi dependencies and local tests are ready. Add CEREBRAS_API_KEY to .env before starting Pi.\n'
