"""Exercise shell setup in an isolated checkout with a fake mise (no downloads)."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    (root / "scripts").mkdir()
    for name in ("setup.sh", "bootstrap.sh"):
        shutil.copy2(ROOT / "scripts" / name, root / "scripts" / name)
    for name in ("README.md", "mise.toml", "pyproject.toml", "uv.lock"):
        (root / name).write_text("fixture\n")
    (root / ".env.example").write_text("OPENAI_API_KEY=\n")
    (root / ".gitignore").write_text(".env\n")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    validation = root / "scripts/validate.sh"
    validation.write_text(
        "#!/bin/bash\n[[ ! -v PYTEST_ADDOPTS ]] || exit 91\n"
        '[[ "$OPENAI_AGENTS_DISABLE_TRACING" == 1 ]] || exit 92\n'
        'echo validation >> "$SETUP_TEST_CALLS"\nexit "${SETUP_TEST_VALIDATE_EXIT:-0}"\n'
    )
    validation.chmod(0o755)
    binaries = tmp_path / "bin"
    binaries.mkdir()
    mise = binaries / "mise"
    mise.write_text(
        '#!/bin/bash\necho "$*" >> "$SETUP_TEST_CALLS"\n'
        'if [[ "$1" == install ]]; then exit "${SETUP_TEST_INSTALL_EXIT:-0}"; fi\n'
    )
    mise.chmod(0o755)
    env = dict(os.environ)
    env.update(
        PATH=f"{binaries}:{env['PATH']}",
        SETUP_TEST_CALLS=str(tmp_path / "calls"),
        PYTEST_ADDOPTS="--run-live",
    )
    return root, env


def run(checkout, *args):
    root, env = checkout
    return subprocess.run(
        [str(root / "scripts/bootstrap.sh"), "--setup", *args],
        cwd=root.parent,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_setup_and_repeat_preserve_environment(checkout):
    root, env = checkout
    assert run(checkout).returncode == 0
    assert (root / ".env").stat().st_mode & 0o777 == 0o600
    # Would execute if setup accidentally sourced the file.
    contents = 'OPENAI_API_KEY=private-marker\ntouch "SHOULD_NOT_EXIST"\n'
    (root / ".env").write_text(contents)
    result = run(checkout)
    assert result.returncode == 0
    assert (root / ".env").read_text() == contents
    assert not (root / "SHOULD_NOT_EXIST").exists()
    assert "private-marker" not in result.stdout + result.stderr
    assert (
        Path(env["SETUP_TEST_CALLS"]).read_text().splitlines()
        == ["install", "current", "exec -- uv sync --frozen", "validation"] * 2
    )
    assert (root / "uv.lock").read_text() == "fixture\n"


def test_check_is_read_only(checkout):
    root, env = checkout
    assert run(checkout, "--check").returncode == 0
    assert not (root / ".env").exists()
    assert not Path(env["SETUP_TEST_CALLS"]).exists()


@pytest.mark.parametrize(
    "problem", ["lock", "ignore", "symlink", "directory", "secret"]
)
def test_preflight_stops_before_install(checkout, problem):
    root, env = checkout
    if problem == "lock":
        (root / "uv.lock").unlink()
    elif problem == "ignore":
        (root / ".gitignore").write_text("")
    elif problem == "symlink":
        (root / ".env").symlink_to(root / "missing")
    elif problem == "directory":
        (root / ".env").mkdir()
    else:
        (root / ".env.example").write_text("OPENAI_API_KEY=private-marker\n")
    result = run(checkout)
    assert result.returncode == 1
    assert not Path(env["SETUP_TEST_CALLS"]).exists()
    assert "private-marker" not in result.stdout + result.stderr


@pytest.mark.parametrize("stage,code", [("INSTALL", 17), ("VALIDATE", 23)])
def test_failure_propagates(checkout, stage, code):
    root, env = checkout
    env[f"SETUP_TEST_{stage}_EXIT"] = str(code)
    result = run(checkout)
    assert result.returncode == code
    assert "Setup completed" not in result.stderr
    if stage == "INSTALL":
        assert not (root / ".env").exists()


def test_unknown_option_does_not_install(checkout):
    _, env = checkout
    assert run(checkout, "--unknown").returncode == 2
    assert not Path(env["SETUP_TEST_CALLS"]).exists()
