from typing import Any
from unittest.mock import Mock, patch

import pytest
from requests_mock.mocker import Mocker

from reviewer_selector.github import GitHubPR
from reviewer_selector.review import Reviewer
from reviewer_selector.rules import Rules


def test_github_url_handling():
    gh = GitHubPR("https://github.com/mozilla-conduit/reviewer-selector/pull/18")
    assert gh.owner == "mozilla-conduit"
    assert gh.repository == "reviewer-selector"
    assert gh.repo_url == "https://github.com/mozilla-conduit/reviewer-selector"
    assert gh.pr_number == 18
    assert (
        gh.patch_url
        == "https://github.com/mozilla-conduit/reviewer-selector/pull/18.patch"
    )


def test_github_url_handling_invalid():
    with pytest.raises(ValueError, match="Can't parse GitHub PR URL.*"):
        _ = GitHubPR("https://example.com")


def test_github__target_branch_name(mocked_github_request: Mocker):
    with mocked_github_request:
        gh = GitHubPR("https://github.com/mozilla-conduit/reviewer-selector/pull/18")

    assert gh.target_branch_name == "main"


def test_github_patch_source(mocked_github_request: Mocker):
    """fetch_patch"""
    patch_text = "Imaa patch!"
    with mocked_github_request as mock:
        patch_url = "https://github.com/mozilla-conduit/reviewer-selector/pull/18.patch"
        mock.get(patch_url, text=patch_text)
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )

        assert gh.fetch_patch() == patch_text, "Unexpected patch text"


def test_github_rules_caching(mocked_github_request: Mocker, sample_rules_data: dict):
    with mocked_github_request as mock:
        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/main/herald_rules.json"
        mock.get(
            rules_url,
            json=sample_rules_data,
        )
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
            Rules({"github_users": {"jsmith": {"username": "jsmith-default"}}}),
        )

        _ = gh.rules
        request_count = mock.call_count
        _ = gh.rules

        assert mock.call_count == request_count, (
            "A second access to rules triggered a new requests"
        )


@pytest.mark.parametrize("in_tree_status", (200, 404, 500))
def test_github_user_resolver(
    mocked_github_request: Mocker, sample_rules_data: dict, in_tree_status
):
    with mocked_github_request as mock:
        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/main/herald_rules.json"
        if in_tree_status == 200:
            mock.get(
                rules_url,
                json=sample_rules_data,
            )
        else:
            mock._adapter.register_uri("GET", rules_url, status_code=in_tree_status)

        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
            Rules({"github_users": {"jsmith": {"username": "jsmith-default"}}}),
        )
        reviewers = {
            Reviewer("jsmith", False),
            Reviewer("fluent-reviewers", True),
            Reviewer("/ent:fluent-reviewers", True),
        }

        resolved = gh.resolve_reviewers(reviewers)

    if in_tree_status == 200:
        assert Reviewer("jsmith-gh", False) in resolved, "GitHub user should be mapped"
    else:
        assert Reviewer("jsmith-default", False) in resolved, (
            "GitHub user should be mapped to the default rules"
        )
    assert Reviewer("@fluent-reviewers", True) in resolved, (
        "Review group should be prefixed"
    )
    assert Reviewer("/ent:fluent-reviewers", True) in resolved, (
        "Enterprise teams should be unchanged"
    )


@patch("reviewer_selector.github.GitHubApp.generate_token")
def test_github_reviewable(mock_gh_generate_token: Mock, mocked_github_request: Mocker):
    """add_reviewers"""

    def echo_callback(request, context) -> dict[str, Any]:
        """Callback method which echos bits of the request back.

        This is useful to inspect that the request was properly formatted.
        """
        return {"headers": dict(request.headers), "json": request.json()}

    with mocked_github_request as mock:
        mock.post(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            json=echo_callback,
        )
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        mock_gh_generate_token.return_value = "THE_TOKEN"
        gh.set_app_credentials("THE_APP_ID", "THE_APP_PRIVKEY")
        reviewers = {
            Reviewer("jsmith", False),
            Reviewer("fluent-reviewers", True),
            Reviewer("/ent:fluent-reviewers", True),
        }

        echo_json = gh.add_reviewers(reviewers)

        assert "headers" in echo_json, "Missing headers in echo response"
        assert "json" in echo_json, "Missing json in echo response"

        assert "application/vnd.github+json" == echo_json["headers"]["Accept"], (
            "Incorrect Accept header in request"
        )
        assert "Bearer THE_TOKEN" == echo_json["headers"]["Authorization"], (
            "Incorrect Authorization header in request"
        )
        assert "2026-03-10" == echo_json["headers"]["X-GitHub-Api-Version"], (
            "Incorrect X-GitHub-Api-Version header in request"
        )

        assert "jsmith" in echo_json["json"]["reviewers"], "Missing reviewer in request"
        assert "fluent-reviewers" in echo_json["json"]["team_reviewers"], (
            "Missing reviewer group in request"
        )
        assert "/ent:fluent-reviewers" in echo_json["json"]["team_reviewers"], (
            "Missing reviewer group in request"
        )
