#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Environment setup is explicit; preserve the existing template-rename interface.
if [[ "${1:-}" == "--setup" ]]; then
    shift
    exec "${SCRIPT_DIR}/setup.sh" "$@"
fi

TEMPLATE_PROJECT_NAME="agent-lab"
TEMPLATE_PACKAGE_NAME="agent_lab"

PROJECT_NAME=""
PACKAGE_NAME=""
DRY_RUN=false
FORCE=false

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
    log_error "Bootstrap failed (exit=${exit_code})."
    exit "${exit_code}"
}

trap on_error ERR

usage() {
    cat <<'EOF'
Usage:
  ./scripts/bootstrap.sh --setup [--check]
  ./scripts/bootstrap.sh
  ./scripts/bootstrap.sh --project-name PROJECT_NAME
  ./scripts/bootstrap.sh --project-name PROJECT_NAME --package-name PACKAGE_NAME
  ./scripts/bootstrap.sh --dry-run
  ./scripts/bootstrap.sh --force

Options:
  --setup [--check]
      Set up this checkout without renaming it. Must be the first option.

  --project-name NAME
      New project/repository name.

      If omitted, the current repository directory name is used.

      Example:
        mcp-file-agent

  --package-name NAME
      New Python package name.

      If omitted, it is generated automatically from the project name.

      Example:
        mcp_file_agent

  --dry-run
      Show planned changes without modifying files.

  --force
      Allow execution even when the Git working tree has uncommitted changes.

  -h, --help
      Show this help.

Examples:

  # Infer project name from current directory
  ./scripts/bootstrap.sh

  # Explicit project name
  ./scripts/bootstrap.sh --project-name mcp-file-agent

  # Explicit project and package names
  ./scripts/bootstrap.sh \
      --project-name mcp-file-agent \
      --package-name mcp_file_agent

  # Preview only
  ./scripts/bootstrap.sh \
      --project-name mcp-file-agent \
      --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-name)
            if [[ $# -lt 2 ]]; then
                log_error "--project-name requires a value."
                exit 2
            fi

            PROJECT_NAME="$2"
            shift 2
            ;;

        --package-name)
            if [[ $# -lt 2 ]]; then
                log_error "--package-name requires a value."
                exit 2
            fi

            PACKAGE_NAME="$2"
            shift 2
            ;;

        --dry-run)
            DRY_RUN=true
            shift
            ;;

        --force)
            FORCE=true
            shift
            ;;

        -h|--help)
            usage
            exit 0
            ;;

        *)
            log_error "Unknown option: $1"
            usage
            exit 2
            ;;
    esac
done

cd "${PROJECT_ROOT}"

# -----------------------------------------------------------------------------
# 1. Prerequisite checks
# -----------------------------------------------------------------------------

required_commands=(
    git
    python3
)

for command_name in "${required_commands[@]}"; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        log_error "Required command not found: ${command_name}"
        exit 1
    fi

    log_info "Found: ${command_name} ($(command -v "${command_name}"))"
done

if [[ ! -d "${PROJECT_ROOT}/.git" ]]; then
    log_error "This directory is not a Git repository:"
    log_error "${PROJECT_ROOT}"
    exit 1
fi

if [[ ! -f "${PROJECT_ROOT}/pyproject.toml" ]]; then
    log_error "pyproject.toml not found."
    exit 1
fi

if [[ ! -d "${PROJECT_ROOT}/src/${TEMPLATE_PACKAGE_NAME}" ]]; then
    log_error "Template package directory not found:"
    log_error "src/${TEMPLATE_PACKAGE_NAME}"
    log_error "This repository may already have been bootstrapped."
    exit 1
fi

# -----------------------------------------------------------------------------
# 2. Resolve new project name
# -----------------------------------------------------------------------------

if [[ -z "${PROJECT_NAME}" ]]; then
    PROJECT_NAME="$(basename "${PROJECT_ROOT}")"
    log_info "Project name inferred from directory: ${PROJECT_NAME}"
fi

# Validate project name.
if [[ ! "${PROJECT_NAME}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    log_error "Invalid project name: ${PROJECT_NAME}"
    log_error "Allowed characters: letters, numbers, dot, underscore, hyphen."
    exit 1
fi

# -----------------------------------------------------------------------------
# 3. Resolve Python package name
# -----------------------------------------------------------------------------

if [[ -z "${PACKAGE_NAME}" ]]; then
    PACKAGE_NAME="$(
        python3 - "${PROJECT_NAME}" <<'PY'
import re
import sys

name = sys.argv[1].strip().lower()

# Python package-friendly name:
#   mcp-file-agent -> mcp_file_agent
name = re.sub(r"[^a-z0-9_]+", "_", name)
name = re.sub(r"_+", "_", name)
name = name.strip("_")

if name and name[0].isdigit():
    name = "_" + name

print(name)
PY
    )"

    log_info "Python package name generated: ${PACKAGE_NAME}"
fi

if [[ -z "${PACKAGE_NAME}" ]]; then
    log_error "Python package name resolved to an empty value."
    exit 1
fi

if [[ ! "${PACKAGE_NAME}" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    log_error "Invalid Python package name: ${PACKAGE_NAME}"
    log_error "Expected a valid Python identifier."
    exit 1
fi

# -----------------------------------------------------------------------------
# 4. Safety checks
# -----------------------------------------------------------------------------

if [[ "${PROJECT_NAME}" == "${TEMPLATE_PROJECT_NAME}" &&
      "${PACKAGE_NAME}" == "${TEMPLATE_PACKAGE_NAME}" ]]; then
    log_warn "Project and package names are unchanged."
    log_warn "Nothing needs to be bootstrapped."
    exit 0
fi

# Dry-run never modifies files, so a dirty working tree is allowed.
if [[ "${DRY_RUN}" != true && "${FORCE}" != true ]]; then
    if [[ -n "$(git status --porcelain)" ]]; then
        log_error "Git working tree contains uncommitted changes."
        log_error "Commit or stash the changes before running bootstrap."
        log_error ""
        log_error "To override this safety check:"
        log_error "  ./scripts/bootstrap.sh --force"
        exit 1
    fi
fi

SOURCE_PACKAGE_DIR="${PROJECT_ROOT}/src/${TEMPLATE_PACKAGE_NAME}"
TARGET_PACKAGE_DIR="${PROJECT_ROOT}/src/${PACKAGE_NAME}"

if [[ "${SOURCE_PACKAGE_DIR}" != "${TARGET_PACKAGE_DIR}" &&
      -e "${TARGET_PACKAGE_DIR}" ]]; then
    log_error "Target package directory already exists:"
    log_error "${TARGET_PACKAGE_DIR}"
    exit 1
fi

# -----------------------------------------------------------------------------
# 5. Show plan
# -----------------------------------------------------------------------------

cat <<EOF

Bootstrap plan
--------------

Project root:
  ${PROJECT_ROOT}

Template project name:
  ${TEMPLATE_PROJECT_NAME}

New project name:
  ${PROJECT_NAME}

Template Python package:
  ${TEMPLATE_PACKAGE_NAME}

New Python package:
  ${PACKAGE_NAME}

Package rename:
  src/${TEMPLATE_PACKAGE_NAME}/
    ->
  src/${PACKAGE_NAME}/

Dry run:
  ${DRY_RUN}

EOF

# -----------------------------------------------------------------------------
# 6. Find files that will be modified
# -----------------------------------------------------------------------------

mapfile -t CANDIDATE_FILES < <(
    find "${PROJECT_ROOT}" \
        -type f \
        \( \
            -name '*.py' \
            -o -name '*.toml' \
            -o -name '*.md' \
            -o -name '*.sh' \
            -o -name '*.yml' \
            -o -name '*.yaml' \
            -o -name '*.json' \
            -o -name '*.txt' \
            -o -name '*.example' \
        \) \
        -not -path "${PROJECT_ROOT}/.git/*" \
        -not -path "${PROJECT_ROOT}/.venv/*" \
        -not -path "${PROJECT_ROOT}/node_modules/*" \
        -not -path "${PROJECT_ROOT}/.pytest_cache/*" \
        -not -path "${PROJECT_ROOT}/.ruff_cache/*" \
	-not -path "${PROJECT_ROOT}/scripts/bootstrap.sh" \
        -print
)

FILES_TO_UPDATE=()

for file_path in "${CANDIDATE_FILES[@]}"; do
    if grep -Iq . "${file_path}" 2>/dev/null &&
       grep -Eq \
           "${TEMPLATE_PROJECT_NAME}|${TEMPLATE_PACKAGE_NAME}" \
           "${file_path}"; then
        FILES_TO_UPDATE+=("${file_path}")
    fi
done

log_info "Files containing template references: ${#FILES_TO_UPDATE[@]}"

for file_path in "${FILES_TO_UPDATE[@]}"; do
    printf '  %s\n' "${file_path#${PROJECT_ROOT}/}"
done

# -----------------------------------------------------------------------------
# 7. Dry-run mode
# -----------------------------------------------------------------------------

if [[ "${DRY_RUN}" == true ]]; then
    log_info "Dry-run completed."
    log_info "No files were modified."
    exit 0
fi

# -----------------------------------------------------------------------------
# 8. Rename Python package
# -----------------------------------------------------------------------------

if [[ "${TEMPLATE_PACKAGE_NAME}" != "${PACKAGE_NAME}" ]]; then
    log_info "Renaming Python package..."

    if git ls-files --error-unmatch \
        "src/${TEMPLATE_PACKAGE_NAME}" \
        >/dev/null 2>&1; then

        git mv \
            "src/${TEMPLATE_PACKAGE_NAME}" \
            "src/${PACKAGE_NAME}"
    else
        mv \
            "src/${TEMPLATE_PACKAGE_NAME}" \
            "src/${PACKAGE_NAME}"
    fi
else
    log_info "Python package name unchanged; directory rename skipped."
fi

# -----------------------------------------------------------------------------
# 9. Replace template references
# -----------------------------------------------------------------------------

log_info "Replacing template references..."

export BOOTSTRAP_PROJECT_ROOT="${PROJECT_ROOT}"
export BOOTSTRAP_OLD_PROJECT="${TEMPLATE_PROJECT_NAME}"
export BOOTSTRAP_NEW_PROJECT="${PROJECT_NAME}"
export BOOTSTRAP_OLD_PACKAGE="${TEMPLATE_PACKAGE_NAME}"
export BOOTSTRAP_NEW_PACKAGE="${PACKAGE_NAME}"

python3 <<'PY'
from __future__ import annotations

import os
from pathlib import Path

root = Path(os.environ["BOOTSTRAP_PROJECT_ROOT"])

old_project = os.environ["BOOTSTRAP_OLD_PROJECT"]
new_project = os.environ["BOOTSTRAP_NEW_PROJECT"]

old_package = os.environ["BOOTSTRAP_OLD_PACKAGE"]
new_package = os.environ["BOOTSTRAP_NEW_PACKAGE"]

extensions = {
    ".py",
    ".toml",
    ".md",
    ".sh",
    ".yml",
    ".yaml",
    ".json",
    ".txt",
    ".example",
}

excluded_dirs = {
    ".git",
    ".venv",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
}

changed_files: list[Path] = []

for path in root.rglob("*"):
    if not path.is_file():
        continue

    if path == root / "scripts" / "bootstrap.sh":
        continue

    if any(part in excluded_dirs for part in path.parts):
        continue

    if path.suffix not in extensions and path.name != ".env.example":
        continue

    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    updated = original

    # Python package references first.
    updated = updated.replace(old_package, new_package)

    # Repository/project name references.
    updated = updated.replace(old_project, new_project)

    if updated == original:
        continue

    path.write_text(updated, encoding="utf-8")
    changed_files.append(path)

print(f"[INFO] Updated {len(changed_files)} text file(s).")

for path in changed_files:
    print(f"  {path.relative_to(root)}")
PY

# -----------------------------------------------------------------------------
# 10. Remove exported bootstrap variables
# -----------------------------------------------------------------------------

unset BOOTSTRAP_PROJECT_ROOT
unset BOOTSTRAP_OLD_PROJECT
unset BOOTSTRAP_NEW_PROJECT
unset BOOTSTRAP_OLD_PACKAGE
unset BOOTSTRAP_NEW_PACKAGE

# -----------------------------------------------------------------------------
# 11. Verify old references
# -----------------------------------------------------------------------------

log_info "Checking for remaining template references..."

remaining_matches="$(
    grep -RInE \
        "${TEMPLATE_PROJECT_NAME}|${TEMPLATE_PACKAGE_NAME}" \
        README.md \
        AGENTS.md \
        CLAUDE.md \
        pyproject.toml \
        mise.toml \
        src \
        tests \
        scripts \
        docs \
        2>/dev/null || true
)"

if [[ -n "${remaining_matches}" ]]; then
    log_warn "Some template references remain:"
    printf '%s\n' "${remaining_matches}"
else
    log_info "No template references found in primary project files."
fi

# -----------------------------------------------------------------------------
# 12. Basic Python package verification
# -----------------------------------------------------------------------------

if [[ ! -f "${TARGET_PACKAGE_DIR}/__init__.py" ]]; then
    log_warn "Package __init__.py not found:"
    log_warn "src/${PACKAGE_NAME}/__init__.py"
fi

# -----------------------------------------------------------------------------
# 13. Git diff safety check
# -----------------------------------------------------------------------------

log_info "Checking Git whitespace..."

git diff --check

# -----------------------------------------------------------------------------
# 14. Summary
# -----------------------------------------------------------------------------

cat <<EOF

Bootstrap completed successfully.

Project name:
  ${PROJECT_NAME}

Python package:
  ${PACKAGE_NAME}

Recommended next steps:

  1. Review changes:

       git status
       git diff

  2. Rebuild/synchronize the environment:

       ./scripts/setup.sh

  3. Run validation:

       ./scripts/validate.sh

  4. Test the application:

       set -a
       source .env
       set +a

       uv run python -m ${PACKAGE_NAME}.main

  5. Commit the customization:

       git add .
       git commit -m "chore: customize project from agent-lab template"

EOF
