#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
CHECK_ONLY=false
STAGE=preflight
log() { printf '[%s] [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" >&2; }
trap 'code=$?; log ERROR "Setup failed: stage=${STAGE} exit=${code}"; exit "$code"' ERR
usage() {
    printf '%s\n' 'Usage: ./scripts/setup.sh [--check]' \
        'Installs mise project tools, syncs frozen dependencies and runs offline validation.' \
        '--check: prerequisites only; no installation, sync or file creation.'
}
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) CHECK_ONLY=true ;;
        -h|--help) usage; exit 0 ;;
        *) log ERROR 'Unknown setup option.'; usage; exit 2 ;;
    esac
    shift
done
cd "${PROJECT_ROOT}"
for name in git mise; do
    if ! command -v "$name" >/dev/null 2>&1; then
        log ERROR "Missing prerequisite: ${name}. See docs/bootstrap.md."
        exit 1
    fi
done
for name in README.md mise.toml pyproject.toml uv.lock .env.example scripts/validate.sh; do
    if [[ ! -f "$name" ]]; then
        log ERROR "Required file missing: ${name}. Restore it from Git."
        exit 1
    fi
done
# Check before creating any secret-bearing file. Tracked .env also fails this check.
if ! git check-ignore -q .env; then
    log ERROR '.env must be untracked and ignored by Git.'
    exit 1
fi
if [[ -L .env || ( -e .env && ! -f .env ) ]]; then
    log ERROR '.env must be a regular file, not a symlink or directory.'
    exit 1
fi
if grep -Eq '^[[:space:]]*(OPENAI_API_KEY|ANTHROPIC_API_KEY)[[:space:]]*=[[:space:]]*[^[:space:]#]+' .env.example; then
    log ERROR '.env.example must contain empty API key values.'
    exit 1
fi
if [[ "$CHECK_ONLY" == true ]]; then
    log INFO 'Prerequisites OK. Installed runtime versions and dependencies were not checked.'
    exit 0
fi
# Do not inherit pytest options that could enable live tests or external tracing.
unset PYTEST_ADDOPTS
export OPENAI_AGENTS_DISABLE_TRACING=1
STAGE=install
log INFO 'Installing tools defined in mise.toml...'
mise install
mise current
STAGE=sync
log INFO 'Synchronizing dependencies from uv.lock...'
mise exec -- uv sync --frozen
STAGE=environment
if [[ ! -e .env ]]; then
    # noclobber protects a file created concurrently; umask applies at creation time.
    (umask 077; set -o noclobber; cat .env.example > .env)
    log INFO 'Created .env with mode 600. No API credentials are needed for validation.'
else
    log INFO 'Existing .env preserved; contents are never loaded.'
    if [[ "$(stat -c '%a' .env)" != 600 ]]; then
        log WARN 'Existing .env permissions are not 600; review with stat and chmod 600 .env.'
    fi
fi
STAGE=validation
log INFO 'Running API-free validation...'
"${SCRIPT_DIR}/validate.sh"
log INFO 'Setup completed. See docs/bootstrap.md for offline CLI examples and optional live tests.'
