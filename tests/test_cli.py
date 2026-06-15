import io
import logging
import pathlib
import sys

import json
from unittest import mock
import pytest

from reviewer_selector import cli

MAIN_SCRIPT = "reviewer-selector"


def test_no_arguments(sample_diff: str, capsys: pytest.CaptureFixture):

    with pytest.raises(SystemExit, match="2"):
        _ = _run_cli([], sample_diff, capsys)

    outerr = capsys.readouterr()

    assert "arguments are required: rules_file" in outerr.err


def test_full_flow(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict,
):
    rules_path = _write_rules(tmp_path / "rules.json", sample_rules_data)

    outerr = _run_cli([rules_path], sample_diff, capsys)

    assert "#fluent-reviewers" in outerr.out


@pytest.mark.parametrize(
    "logging_arg,expected_log_level",
    (
        ("--verbose", logging.INFO),
        ("--debug", logging.DEBUG),
    ),
)
def test_cli_log_level(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict,
    logging_arg: str,
    expected_log_level: int,
):
    rules_path = _write_rules(tmp_path / "rules.json", sample_rules_data)

    with mock.patch("logging.basicConfig") as lbc:
        _run_cli([logging_arg, rules_path], sample_diff, capsys)
        lbc.assert_called_once_with(level=expected_log_level)


def test_repo_filter(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff_remote: str,
    sample_rules_data: dict,
):
    rules_path = _write_rules(tmp_path / "rules.json", sample_rules_data)

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
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict,
):
    rules_path = _write_rules(tmp_path / "rules.json", sample_rules_data)

    outerr = _run_cli(
        [rules_path, "--group-prefix", "@"],
        sample_diff,
        capsys,
    )

    assert "@fluent-reviewers" in outerr.out


def _write_rules(rules_path: pathlib.Path, rules_data: dict) -> str:
    with rules_path.open(mode="w") as f:
        json.dump(rules_data, f)

    return str(rules_path)


def _run_cli(args: list[str], stdin: str, capsys: pytest.CaptureFixture):
    """Run the cli entry point in the same process to record coverage."""

    with (
        mock.patch.object(sys, "argv", [MAIN_SCRIPT] + args),
        mock.patch.object(sys, "stdin", io.StringIO(stdin)),
    ):
        cli()

    return capsys.readouterr()
