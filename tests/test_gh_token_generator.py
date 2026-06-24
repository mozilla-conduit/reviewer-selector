from unittest.mock import Mock, patch

import pytest

from gh_token_generator import main


def test_no_tc_url():
    with pytest.raises(AssertionError, match="Taskcluster deployment url"):
        main()


def test_no_tc_secret_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TASKCLUSTER_ROOT_URL", "https://localhost:8080")
    with pytest.raises(ValueError, match="TC_SECRET_ID"):
        main()


def test_no_org_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TASKCLUSTER_ROOT_URL", "https://localhost:8080")
    monkeypatch.setenv("TC_SECRET_ID", "THE_TC_SECRET_ID")
    with pytest.raises(ValueError, match="ORG_NAME"):
        main()


def test_no_repo_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TASKCLUSTER_ROOT_URL", "https://localhost:8080")
    monkeypatch.setenv("TC_SECRET_ID", "THE_TC_SECRET_ID")
    monkeypatch.setenv("ORG_NAME", "THE_ORG_NAME")
    with pytest.raises(ValueError, match="REPO_NAME"):
        main()


@patch("reviewer_selector.taskcluster.Taskcluster.fetch_secret")
@patch("gh_token_generator.generate_github_token")
def test_main(
    mock_generate_gh_token: Mock,
    mock_tc_fetch_secret: Mock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    monkeypatch.setenv("TASKCLUSTER_ROOT_URL", "https://localhost:8080")
    monkeypatch.setenv("TC_SECRET_ID", "THE_TC_SECRET_ID")
    monkeypatch.setenv("ORG_NAME", "THE_ORG_NAME")
    monkeypatch.setenv("REPO_NAME", "THE_REPO_NAME")

    mock_tc_fetch_secret.return_value = {
        "GITHUB_APP_ID": "THE_APP_ID",
        "GITHUB_APP_PRIVKEY": "THE_PRIVKEY",
    }
    mock_generate_gh_token.return_value = "THE_TOKEN"

    main()

    mock_tc_fetch_secret.assert_called_once_with("THE_TC_SECRET_ID")
    mock_generate_gh_token.assert_called_once_with(
        "THE_APP_ID", "THE_PRIVKEY", "THE_ORG_NAME", "THE_REPO_NAME"
    )

    outerr = capsys.readouterr()
    assert outerr.out == "THE_TOKEN\n"
