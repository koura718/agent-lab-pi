"""Exercise the real pytest gate in isolated runs, without a model or API."""

from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "provider,key_name",
    [
        ("openai", "OPENAI_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
        ("cerebras", "CEREBRAS_API_KEY"),
    ],
)
@pytest.mark.parametrize(
    "enabled,key,model,expected",
    [
        (False, False, False, "skipped"),
        (False, True, True, "skipped"),
        (True, False, True, "usage"),
        (True, True, False, "usage"),
        (True, True, True, "passed"),
    ],
)
def test_live_gate(
    pytester, monkeypatch, enabled, key, model, expected, provider, key_name
):
    monkeypatch.setenv("AGENT_PROVIDER", provider)
    pytester.makeconftest(Path(__file__).parents[1].joinpath("conftest.py").read_text())
    pytester.makeini("[pytest]\nmarkers = live: opt-in real model")
    pytester.makepyfile(
        test_offline='import os\nimport socket\nimport pytest\n\ndef test_remains_offline():\n    assert "OPENAI_API_KEY" not in os.environ\n    with pytest.raises(AssertionError, match="Network access is forbidden"):\n        socket.getaddrinfo("example.invalid", 443)\n'
    )
    live = pytester.path / "live"
    live.mkdir()
    # Intentionally omit the marker: directory classification must protect this.
    (live / "test_probe.py").write_text(
        "import os\ndef test_probe():\n"
        f'    assert os.environ["{key_name}"] == "dummy-key"\n'
        '    assert os.environ["AGENT_MODEL"] == "dummy-model"\n'
    )
    for name, value, present in [
        (key_name, "dummy-key", key),
        ("AGENT_MODEL", "dummy-model", model),
    ]:
        if present:
            monkeypatch.setenv(name, value)
        else:
            monkeypatch.delenv(name, raising=False)
    result = pytester.runpytest_subprocess(
        *(["--run-live"] if enabled else []), timeout=30
    )
    if expected == "usage":
        assert result.ret == pytest.ExitCode.USAGE_ERROR
        result.stderr.fnmatch_lines(["*--run-live requires:*"])
    else:
        result.assert_outcomes(
            passed=2 if expected == "passed" else 1,
            skipped=1 if expected == "skipped" else 0,
        )
