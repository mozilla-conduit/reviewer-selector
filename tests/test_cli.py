import io
import logging
import pathlib
import sys

import json
from typing import Any
from unittest import mock
import pytest
import requests
from requests_mock import Mocker

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
    sample_rules_data: dict[str, Any],
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
    sample_rules_data: dict[str, Any],
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
    sample_rules_data: dict[str, Any],
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
    sample_rules_data: dict[str, Any],
):
    rules_path = _write_rules(tmp_path / "rules.json", sample_rules_data)

    outerr = _run_cli(
        [rules_path, "--group-prefix", "@"],
        sample_diff,
        capsys,
    )

    assert "@fluent-reviewers" in outerr.out


def test_github(
    tmp_path: pathlib.Path,
    mocked_github_request: Mocker,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict[str, Any],
):
    # Empty rules. The real ones should be coming from in-tree.
    rules_path = _write_rules(tmp_path / "rules.json", {})

    with mocked_github_request as mock:
        patch_url = "https://github.com/mozilla-conduit/reviewer-selector/pull/18.patch"
        mock.get(patch_url, text=sample_diff)

        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/main/herald_rules.json"
        mock.get(rules_url, text=json.dumps(sample_rules_data))

        outerr = _run_cli(
            [
                rules_path,
                "--pr-url",
                "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
            ],
            "",
            capsys,
        )

    assert "@fluent-reviewers" in outerr.out
    assert "/ent:fluent-reviewers" in outerr.out


@mock.patch("reviewer_selector.GitHubPR.fetch_rules")
@mock.patch("reviewer_selector.GitHubPR.fetch_patch")
@mock.patch("reviewer_selector.Rules.collect_reviewers")
def test_github_repo_added(
    mock_collect_reviewers: mock.Mock,
    mock_fetch_patch: mock.Mock,
    mock_fetch_rules: mock.Mock,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict[str, Any],
):
    # Empty rules. The real ones should be coming from in-tree.
    rules_path = _write_rules(tmp_path / "rules.json", {})

    rules_resp = requests.Response()
    rules_resp.status_code = 404
    mock_fetch_rules.return_value = rules_resp
    mock_fetch_patch.return_value = sample_diff

    _run_cli(
        [
            rules_path,
            "--pr-url",
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        ],
        "",
        capsys,
    )

    assert "reviewer-selector-main" in mock_collect_reviewers.call_args[0][1], (
        "The GitHub repo name was not passed to the Rules.collect_reviewers method"
    )


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
