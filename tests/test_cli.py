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


#
# GitHub CLI tests
#


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

        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/test-branch/herald_rules.json"
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

    assert "fluent-reviewers" in outerr.out
    assert "ent:fluent-reviewers" in outerr.out
    assert "/ent:fluent-reviewers" not in outerr.out, (
        "Enterprise team name should have been normalised"
    )


@mock.patch("reviewer_selector.GitHubPR.fetch_rules")
@mock.patch("reviewer_selector.github.GitHubPatchSource.fetch_patch")
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


@mock.patch("reviewer_selector.GitHubPR.fetch_rules")
@mock.patch("reviewer_selector.github.GitHubPatchSource.fetch_patch")
@mock.patch("reviewer_selector.Rules.collect_reviewers")
@mock.patch("reviewer_selector.github.GitHubApp")
@mock.patch("reviewer_selector.taskcluster.TaskclusterConfig")
@mock.patch("reviewer_selector.taskcluster.load_secrets")
@pytest.mark.parametrize(
    "env_github_token,env_gh_token,env_app_id,env_app_privkey,env_tc_secret_id,tc_app_id,tc_app_privkey,expected_app_credentials,needs_tc_secrets",
    (
        ("", "", "", "", "", "", "", ("", ""), False),
        ("", "", "", "", "", "TC_APP_ID", "TC_APP_PRIVKEY", ("", ""), False),
        # Support immediate GitHub tokens.
        ("GITHUB_TOKEN", "", "", "", "", "", "", ("", "", "GITHUB_TOKEN"), False),
        ("", "GH_TOKEN", "", "", "", "", "", ("", "", "GH_TOKEN"), False),
        # TC secrets are used only if env missing.
        (
            "",
            "",
            "ENV_APP_ID",
            "ENV_APP_PRIVKEY",
            "ENV_TC_SECRET_ID",
            "TC_APP_ID",
            "TC_APP_PRIVKEY",
            ("ENV_APP_ID", "ENV_APP_PRIVKEY"),
            False,
        ),
        (
            "",
            "",
            "",
            "",
            "ENV_TC_SECRET_ID",
            "TC_APP_ID",
            "TC_APP_PRIVKEY",
            ("TC_APP_ID", "TC_APP_PRIVKEY"),
            True,
        ),
        # Some env takes priority over TC secrets.
        (
            "",
            "",
            "ENV_APP_ID",
            "",
            "ENV_TC_SECRET_ID",
            "TC_APP_ID",
            "TC_APP_PRIVKEY",
            ("ENV_APP_ID", "TC_APP_PRIVKEY"),
            True,
        ),
        (
            "",
            "",
            "",
            "ENV_APP_PRIVKEY",
            "ENV_TC_SECRET_ID",
            "TC_APP_ID",
            "TC_APP_PRIVKEY",
            ("TC_APP_ID", "ENV_APP_PRIVKEY"),
            True,
        ),
    ),
)
def test_github_env(
    mock_tc_load_secrets: mock.Mock,
    _mock_tc_taskclusterconfig: mock.Mock,
    mock_github_app: mock.Mock,
    _mock_collect_reviewers: mock.Mock,
    mock_fetch_patch: mock.Mock,
    mock_fetch_rules: mock.Mock,
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mocked_github_request: Mocker,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    env_github_token: str,
    env_gh_token: str,
    env_app_id: str,
    env_app_privkey: str,
    env_tc_secret_id: str,
    tc_app_id: str,
    tc_app_privkey: str,
    expected_app_credentials: tuple[str, str],
    needs_tc_secrets: bool,
):
    """Test precedence between environment and TC secrets, including for incomplete data."""
    rules_path = _write_rules(tmp_path / "rules.json", {})

    monkeypatch.setenv("GITHUB_TOKEN", env_github_token)
    monkeypatch.setenv("GH_TOKEN", env_gh_token)
    monkeypatch.setenv("GITHUB_APP_ID", env_app_id)
    monkeypatch.setenv("GITHUB_APP_PRIVKEY", env_app_privkey)
    monkeypatch.setenv("TC_SECRET_ID", env_tc_secret_id)
    mock_tc_load_secrets.return_value = {
        "GITHUB_APP_ID": tc_app_id,
        "GITHUB_APP_PRIVKEY": tc_app_privkey,
    }

    rules_resp = requests.Response()
    rules_resp.status_code = 404
    mock_fetch_rules.return_value = rules_resp

    mock_fetch_patch.return_value = sample_diff

    with mocked_github_request as mock:
        requested_reviewers_url = "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers"
        mock_requested_reviewers = mock.post(requested_reviewers_url, text="{}")
        _run_cli(
            [
                rules_path,
                "--pr-url",
                "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
            ],
            "",
            capsys,
        )

    if all(expected_app_credentials):
        mock_github_app.assert_called_with(
            *expected_app_credentials, "mozilla-conduit", "reviewer-selector"
        )
        assert mock_requested_reviewers.call_count == 1, (
            "Incorrect number of requests to the requested reviewers endpoint (app credentials)"
        )
    elif any([env_github_token, env_gh_token]):
        assert mock_requested_reviewers.call_count == 1, (
            "Incorrect number of requests to the requested reviewers endpoint (gh tokens)"
        )
    else:
        assert mock_github_app.call_count == 0, (
            "The GitHubApp was unexpectedly initialised"
        )
        assert mock_requested_reviewers.call_count == 0, (
            "Unexpected requests to the requested reviewers endpoint were made"
        )

    assert needs_tc_secrets == mock_tc_load_secrets.called, (
        "Use of load_secrets doesn't match expectation"
    )


#
# Phabricator CLI tests
#


@pytest.mark.xfail()
def test_phabricator(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture,
    sample_diff: str,
    sample_rules_data: dict[str, Any],
):
    # Empty rules. The real ones should be coming from in-tree.
    rules_path = _write_rules(tmp_path / "rules.json", {})

    outerr = _run_cli(
        [
            rules_path,
            "--phabricator-revision-url",
            # "https://phabricator.test/D1",
            "https://phabricator.services.mozilla.com/D315228",
            # "https://phabricator.services.mozilla.com/D315229"
        ],
        "",
        capsys,
    )

    assert "fluent-reviewers" in outerr.out
    assert "ent:fluent-reviewers" in outerr.out
    assert "/ent:fluent-reviewers" not in outerr.out, (
        "Enterprise team name should have been normalised"
    )


#
# Test utilities
#


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
