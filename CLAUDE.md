# CLAUDE.md

## Project

This repository is an AI Agent development sandbox.

Before making changes:

1. Read `README.md`.
2. Read `AGENTS.md`.
3. Follow the versions defined in `mise.toml`.

## Claude Code Rules

- Treat `README.md` as the primary project specification.
- Follow the common development rules in `AGENTS.md`.
- Do not modify files outside this repository.
- Do not expose secrets or credentials.
- Ask for approval before destructive or security-sensitive operations.
- Prefer small, reviewable changes.
- Use `uv` for Python dependency management.
- Use `pnpm` for Node.js dependency management.
- Run relevant tests, lint, and validation after changes.
- Summarize changed files, commands executed, and validation results.

## Tool Usage

- Prefer read-only inspection before modifying files.
- Do not install packages globally for project dependencies.
- Do not change OS-level configuration unless explicitly requested.
- Do not use `sudo` unless explicitly approved.

