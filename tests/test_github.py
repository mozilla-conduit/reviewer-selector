import json
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
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
    with mocked_github_request as mock:
        gh = GitHubPR("https://github.com/mozilla-conduit/reviewer-selector/pull/18")

        _ = gh.target_branch_name
        request_count = mock.call_count
        assert gh.target_branch_name == "test-branch"

        assert mock.call_count == request_count, (
            "Second access to branch name triggered a new request"
        )


def test_github_patch_source(mocked_github_request: Mocker):
    patch_text = "Imaa patch!"
    with mocked_github_request as mock:
        patch_url = "https://github.com/mozilla-conduit/reviewer-selector/pull/18.patch"
        mock.get(patch_url, text=patch_text)
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )

        assert gh.patch_source.fetch_patch() == patch_text, "Unexpected patch text"


def test_github_rules_caching(mocked_github_request: Mocker, sample_rules_data: dict):
    with mocked_github_request as mock:
        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/test-branch/herald_rules.json"
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
        rules_url = "https://github.com/mozilla-conduit/reviewer-selector/raw/refs/heads/test-branch/herald_rules.json"
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
            Reviewer("ent:fluent-reviewers", True),
            Reviewer("/ent:normalise-this", True),
        }

        resolved = gh.user_resolver.resolve_reviewers(reviewers)

    if in_tree_status == 200:
        assert Reviewer("jsmith-gh", False) in resolved, "GitHub user should be mapped"
    else:
        assert Reviewer("jsmith-default", False) in resolved, (
            "GitHub user should be mapped to the default rules"
        )
    assert Reviewer("fluent-reviewers", True) in resolved, (
        "Review group should not be prefixed"
    )
    assert Reviewer("ent:fluent-reviewers", True) in resolved, (
        "Enterprise teams should be unchanged"
    )
    assert Reviewer("ent:normalise-this", True) in resolved, (
        "Enterprise teams should be normalised"
    )


def test_github_api_request_errors(caplog: pytest.LogCaptureFixture):

    def callback(request: requests.Request, context: requests_mock.response._Context):
        context.status_code = 422
        return "422 Client Error: Unprocessable Entity for test"

    with Mocker() as mock:
        mock.get(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18",
            text=callback,
        )

        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        with pytest.raises(requests.exceptions.HTTPError):
            gh.api_request()

        assert "Unprocessable Entity for test" in caplog.text


@patch("reviewer_selector.github.GitHubApp.generate_token")
def test_github_reviewable(
    mock_gh_generate_token: Mock,
    mocked_github_request: Mocker,
    github_api_response_pull_request_requested_reviewers: str,
):
    # We store this data locally, so the POST callback can modify it, and the changes
    # are reflected in subsequent GET callbacks.
    api_requested_reviewers_data = json.loads(
        github_api_response_pull_request_requested_reviewers
    )

    def add_reviewers_callback(
        request: requests.Request, _context: requests_mock.response._Context
    ) -> dict[str, Any]:
        """Callback implementing side-effects of add_reviewers requests in memory.

        This does not create full user/team objects, but should be enough to satisfy the
        adapter.
        """
        payload = request.json()

        for r in payload["reviewers"]:
            api_requested_reviewers_data["users"].append({"login": r})
        for t in payload["team_reviewers"]:
            # As of 2026-07-29, the GitHub API requires a `/ent:` prefix when adding
            # reviewers, but returns them without a leading `/`. We normalise the
            # data to the latter.
            if t.startswith("/ent:"):
                t = t.removeprefix("/")
            api_requested_reviewers_data["teams"].append({"slug": t})

        return {}

    def get_reviewers_callback(request, context):
        """Callback returning our in-memory set of reviewers."""
        return api_requested_reviewers_data

    with mocked_github_request as mock:
        mock_requested_reviewers_post = mock.post(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            json=add_reviewers_callback,
        )
        mock_requested_reviewers_get = mock.get(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            json=get_reviewers_callback,
        )
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        mock_gh_generate_token.return_value = "THE_TOKEN"
        gh.set_app_credentials(app_id="THE_APP_ID", app_privkey="THE_APP_PRIVKEY")
        test_reviewer = Reviewer("test-reviewer", False)
        jsmith = Reviewer("jsmith", False)
        fluent_reviewers = Reviewer("fluent-reviewers", True)
        ent_fluent_reviewers = Reviewer("ent:fluent-reviewers", True)
        reviewers = {test_reviewer, jsmith, fluent_reviewers, ent_fluent_reviewers}

        gh.reviewable.add_new_reviewers(reviewers)

        assert (
            "application/vnd.github+json"
            == mock_requested_reviewers_post.last_request.headers["Accept"]
        ), "Incorrect Accept header in request"
        assert (
            "Bearer THE_TOKEN"
            == mock_requested_reviewers_post.last_request.headers["Authorization"]
        ), "Incorrect Authorization header in request"
        assert (
            "2026-03-10"
            == mock_requested_reviewers_post.last_request.headers[
                "X-GitHub-Api-Version"
            ]
        ), "Incorrect X-GitHub-Api-Version header in request"

        assert (
            "jsmith" in mock_requested_reviewers_post.last_request.json()["reviewers"]
        ), "Missing reviewer in request"
        assert (
            "fluent-reviewers"
            in mock_requested_reviewers_post.last_request.json()["team_reviewers"]
        ), "Missing reviewer group in request"
        assert (
            "ent:fluent-reviewers"
            in mock_requested_reviewers_post.last_request.json()["team_reviewers"]
        ), "Missing reviewer group in request"

        assert (
            "test-reviewer"
            not in mock_requested_reviewers_post.last_request.json()["reviewers"]
        ), "Existing reviewer re-requested"

        assert jsmith in gh.reviewable.reviewers
        assert fluent_reviewers in gh.reviewable.reviewers
        assert ent_fluent_reviewers in gh.reviewable.reviewers
        assert test_reviewer in gh.reviewable.reviewers

        assert mock_requested_reviewers_post.call_count == 1, (
            "Unexpected number of POST requests to requested_reviewers"
        )
        # Expectations: 1 initial request + 1 refreshed after adding reviewers
        assert mock_requested_reviewers_get.call_count == 2, (
            "Unexpected number of GET requests to requested_reviewers"
        )
