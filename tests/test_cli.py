import io
import sys
import tempfile

import json
from unittest import mock
import pytest

from reviewer_selector import main

MAIN_SCRIPT = "reviewer-selector"


def test_no_arguments(sample_diff: str, capsys: pytest.CaptureFixture):

    with pytest.raises(SystemExit, match="2"):
        _ = _run_cli([], sample_diff, capsys)

    outerr = capsys.readouterr()

    assert "arguments are required: rules_file" in outerr.err


def test_full_flow(
    sample_diff: str, sample_rules_data: dict, capsys: pytest.CaptureFixture
):
    rules_path = _write_rules(sample_rules_data)

    outerr = _run_cli([rules_path], sample_diff, capsys)

    assert "#fluent-reviewers" in outerr.out


def test_cli_verbose(
    sample_diff: str, sample_rules_data: dict, capsys: pytest.CaptureFixture
):
    rules_path = _write_rules(sample_rules_data)

    outerr = _run_cli(["--verbose", rules_path], sample_diff, capsys)

    assert "#fluent-reviewers" in outerr.out


def test_cli_debug(
    sample_diff: str, sample_rules_data: dict, capsys: pytest.CaptureFixture
):
    rules_path = _write_rules(sample_rules_data)

    outerr = _run_cli(["--debug", rules_path], sample_diff, capsys)

    assert "#fluent-reviewers" in outerr.out


def test_repo_filter(
    sample_diff_remote: str, sample_rules_data: dict, capsys: pytest.CaptureFixture
):
    rules_path = _write_rules(sample_rules_data)

    outerr = _run_cli(
        [
            rules_path,
            "--repo",
            "mozilla-central",
        ],
        sample_diff_remote,
        capsys,
    )

    assert "jsmith-gh" in outerr.out


def test_group_prefix(
    sample_diff: str, sample_rules_data: dict, capsys: pytest.CaptureFixture
):
    rules_path = _write_rules(sample_rules_data)

    outerr = _run_cli(
        [rules_path, "--group-prefix", "@"],
        sample_diff,
        capsys,
    )

    assert "@fluent-reviewers" in outerr.out


def _write_rules(rules_data: dict) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(rules_data, f)
        rules_path = f.name

    return rules_path


def _run_cli(args: list[str], stdin: str, capsys: pytest.CaptureFixture):
    """Run the main entry point in the same process to record coverage."""

    with (
        mock.patch.object(sys, "argv", [MAIN_SCRIPT] + args),
        mock.patch.object(sys, "stdin", io.StringIO(stdin)),
    ):
        main()

    return capsys.readouterr()
