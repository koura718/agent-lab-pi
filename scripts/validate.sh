#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

START_TIME="$(date +%s)"

log_info() {
    printf '[INFO] %s\n' "$*"
}

log_warn() {
    printf '[WARN] %s\n' "$*" >&2
}

log_error() {
    printf '[ERROR] %s\n' "$*" >&2
}

on_error() {
    local exit_code=$?
    log_error "Validation failed (exit=${exit_code})."
    exit "${exit_code}"
}

trap on_error ERR

cd "${PROJECT_ROOT}"

# Never publish a report left by a previous validation attempt.
mkdir -p reports
rm -f -- reports/pytest.xml

log_info "Project root: ${PROJECT_ROOT}"

# -----------------------------------------------------------------------------
# 1. Basic project checks
# -----------------------------------------------------------------------------

required_files=(
    "README.md"
    "mise.toml"
    "pyproject.toml"
)

for required_file in "${required_files[@]}"; do
    if [[ ! -f "${PROJECT_ROOT}/${required_file}" ]]; then
        log_error "Required file not found: ${required_file}"
        exit 1
    fi
done

# -----------------------------------------------------------------------------
# 2. Required commands
# -----------------------------------------------------------------------------

required_commands=(
    git
    mise
)

missing=0

for command_name in "${required_commands[@]}"; do
    if command -v "${command_name}" >/dev/null 2>&1; then
        command_path="$(command -v "${command_name}")"
        log_info "Found: ${command_name} (${command_path})"
    else
        log_error "Required command not found: ${command_name}"
        missing=1
    fi
done

if [[ "${missing}" -ne 0 ]]; then
    exit 1
fi

# -----------------------------------------------------------------------------
# 3. Resolve project tools
# -----------------------------------------------------------------------------


if ! mise exec -- uv --version >/dev/null 2>&1; then
    log_error "uv could not be executed through mise."
    log_error "Run ./scripts/setup.sh first."
    exit 1
fi

UV_VERSION="$(mise exec -- uv --version)"
log_info "Using ${UV_VERSION}"

log_info "Resolved runtime versions:"
mise current

# -----------------------------------------------------------------------------
# 4. Git whitespace validation
# -----------------------------------------------------------------------------

log_info "Checking Git whitespace errors..."

git diff --check

# Also check staged changes when they exist.
if ! git diff --cached --quiet --; then
    log_info "Checking staged Git whitespace errors..."
    git diff --cached --check
fi

# -----------------------------------------------------------------------------
# 5. Ruff lint
# -----------------------------------------------------------------------------

log_info "Running Ruff lint..."

mise exec -- uv run --frozen ruff check .

# -----------------------------------------------------------------------------
# 6. Ruff formatting
# -----------------------------------------------------------------------------

log_info "Checking Ruff formatting..."

mise exec -- uv run --frozen ruff format --check .

# -----------------------------------------------------------------------------
# 7. Python tests
# -----------------------------------------------------------------------------

log_info "Running Python tests..."

mise exec -- uv run --frozen pytest -v --junitxml=reports/pytest.xml

# -----------------------------------------------------------------------------
# 8. Python compile check
# -----------------------------------------------------------------------------

log_info "Checking Python source compilation..."

compile_targets=()

if [[ -d "${PROJECT_ROOT}/src" ]]; then
    compile_targets+=("src")
fi

if [[ -d "${PROJECT_ROOT}/tests" ]]; then
    compile_targets+=("tests")
fi

if [[ "${#compile_targets[@]}" -gt 0 ]]; then
    mise exec -- uv run --frozen python -m compileall -q "${compile_targets[@]}"
else
    log_warn "No src/ or tests/ directories found; compile check skipped."
fi

# -----------------------------------------------------------------------------
# 9. Secret safety checks
# -----------------------------------------------------------------------------

ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

if [[ -f "${ENV_FILE}" ]]; then
    log_info "Checking .env Git exclusion..."

    if git check-ignore -q "${ENV_FILE}"; then
        log_info ".env is excluded from Git."
    else
        log_error ".env is NOT excluded from Git."
        log_error "Update .gitignore before committing."
        exit 1
    fi
fi

if [[ -f "${ENV_EXAMPLE}" ]]; then
    log_info "Checking .env.example for obvious secret values..."

    if grep -Eq \
        '^[[:space:]]*(OPENAI_API_KEY|ANTHROPIC_API_KEY|CEREBRAS_API_KEY)[[:space:]]*=[[:space:]]*[^[:space:]#]+' \
        "${ENV_EXAMPLE}"; then
        log_error ".env.example appears to contain a non-empty API key value."
        log_error "Keep secret values out of template files."
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# 10. Repository status
# -----------------------------------------------------------------------------

log_info "Git branch:"
git branch --show-current

if [[ -n "$(git status --porcelain)" ]]; then
    log_warn "Working tree contains uncommitted changes."
    git status --short
else
    log_info "Working tree is clean."
fi

# -----------------------------------------------------------------------------
# 11. Summary
# -----------------------------------------------------------------------------

END_TIME="$(date +%s)"
ELAPSED="$((END_TIME - START_TIME))"

log_info "All validation checks passed."
log_info "Elapsed: ${ELAPSED}s"

