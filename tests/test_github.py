from collections.abc import Callable
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
from requests.exceptions import HTTPError
from requests_mock.mocker import Mocker

from reviewer_selector.github import GitHubPR
from reviewer_selector.review import AddReviewersStatus, Reviewer
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

        assert (
            gh.patch_source.get_patch_subject()
            == "reviewer_selector: add GitHub Site support (bug 2030600)"
        ), "Unexpected patch subject"
        assert gh.patch_source.patch == patch_text, "Unexpected patch text"


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

        resolved = gh.user_resolver.resolve_reviewers(iter(reviewers))

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
        with pytest.raises(HTTPError):
            gh.api_request()

        assert "Unprocessable Entity for test" in caplog.text


@pytest.mark.parametrize(
    "initial_reviewers,new_reviewers,expected_post_call_count,expected_get_call_count",
    (
        (
            (),
            (
                Reviewer("test-reviewer", False),
                Reviewer("jsmith", False),
                Reviewer("fluent-reviewers", True),
                Reviewer("ent:fluent-reviewers", True),
            ),
            # Only new reviewers.
            1,
            # One check before adding new reviewers.
            1,
        ),
        (
            (
                Reviewer("test-reviewer", False),
                Reviewer("fluent-reviewers", True),
            ),
            (
                Reviewer("jsmith", False),
                Reviewer("ent:fluent-reviewers", True),
            ),
            # Initial + new reviewers.
            2,
            # One check before adding new reviewers.
            1,
        ),
        (
            (
                Reviewer("test-reviewer", False),
                Reviewer("jsmith", False),
                Reviewer("fluent-reviewers", True),
                Reviewer("ent:fluent-reviewers", True),
            ),
            (),
            # Only initial reviewers.
            1,
            # One check before adding new reviewers.
            1,
        ),
    ),
)
@patch("reviewer_selector.github.GitHubApp.generate_token")
def test_github_reviewable(
    mock_gh_generate_token: Mock,
    configurable_mocked_github_request: Callable,
    initial_reviewers: list[Reviewer],
    new_reviewers: list[Reviewer],
    expected_post_call_count: int,
    expected_get_call_count: int,
):
    with configurable_mocked_github_request() as mock:
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        mock_gh_generate_token.return_value = "THE_TOKEN"
        gh.set_app_credentials(app_id="THE_APP_ID", app_privkey="THE_APP_PRIVKEY")
        all_reviewers = set(initial_reviewers + new_reviewers)

        init_added = gh.reviewable.add_reviewers(iter(initial_reviewers))
        assert init_added == len(initial_reviewers)

        status = gh.reviewable.add_new_reviewers(iter(all_reviewers))

        assert status == AddReviewersStatus(
            len(set(new_reviewers) - set(initial_reviewers)), True
        )
        assert mock.requested_reviewers_post.call_count == expected_post_call_count, (
            "Unexpected number of POST requests to requested_reviewers"
        )
        assert mock.requested_reviewers_get.call_count == expected_get_call_count, (
            "Unexpected number of GET requests to requested_reviewers"
        )

        if expected_post_call_count > 0:
            assert (
                "application/vnd.github+json"
                == mock.requested_reviewers_post.last_request.headers["Accept"]
            ), "Incorrect Accept header in request"
            assert (
                "Bearer THE_TOKEN"
                == mock.requested_reviewers_post.last_request.headers["Authorization"]
            ), "Incorrect Authorization header in request"
            assert (
                "2026-03-10"
                == mock.requested_reviewers_post.last_request.headers[
                    "X-GitHub-Api-Version"
                ]
            ), "Incorrect X-GitHub-Api-Version header in request"

        if expected_post_call_count > 1:
            # Make sure new reviewers were requested.
            for user_name in [r.name for r in new_reviewers if not r.is_group]:
                assert (
                    user_name
                    in mock.requested_reviewers_post.last_request.json()["reviewers"]
                ), f"Missing reviewer in request: {user_name}"
            for group_name in [r.name for r in new_reviewers if r.is_group]:
                assert (
                    group_name
                    in mock.requested_reviewers_post.last_request.json()[
                        "team_reviewers"
                    ]
                ), f"Missing reviewer group in request: {group_name}"

            # Make user existing reviewers weren't re-requested.
            for user_name in [r.name for r in initial_reviewers if not r.is_group]:
                assert (
                    user_name
                    not in mock.requested_reviewers_post.last_request.json()[
                        "reviewers"
                    ]
                ), f"Existing reviewer re-requested: {user_name}"
            for group_name in [r.name for r in initial_reviewers if not r.is_group]:
                assert (
                    group_name
                    not in mock.requested_reviewers_post.last_request.json()[
                        "team_reviewers"
                    ]
                ), f"Existing reviewer re-requested: {group_name}"

        # Make sure all reviewers are now present.
        for user in [r for r in all_reviewers if not r.is_group]:
            assert user in gh.reviewable.reviewers, (
                f"Missing user reviewer: {user.name}"
            )
        for group in [r for r in all_reviewers if r.is_group]:
            assert group in gh.reviewable.reviewers, (
                f"Missing group reviewer: {group.name}"
            )

        # When we run this a second time, no new network requests should happen.
        mock.requested_reviewers_post.reset()
        mock.requested_reviewers_get.reset()

        status = gh.reviewable.add_new_reviewers(iter(all_reviewers))

        assert status == AddReviewersStatus(0, True)
        assert mock.requested_reviewers_post.call_count == 0, (
            "Unexpected new POST requests to requested_reviewers on NOOP request"
        )
        assert mock.requested_reviewers_get.call_count == 0, (
            "Unexpected number of GET requests to requested_reviewers on NOOP request"
        )


@patch("reviewer_selector.github.GitHubApp.generate_token")
def test_github_reviewable_add_reviewers_retry(
    mock_gh_generate_token: Mock,
    configurable_mocked_github_request: Callable,
    caplog: pytest.LogCaptureFixture,
):
    rejected_enterprise_team = Reviewer("ent:fluent-reviewers", True)
    expected_reviewers = [
        Reviewer("test-reviewer", False),
        Reviewer("jsmith", False),
        Reviewer("fluent-reviewers", True),
    ]
    reviewers = expected_reviewers + [rejected_enterprise_team]

    with configurable_mocked_github_request() as mock:
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        mock_gh_generate_token.return_value = "THE_TOKEN"
        gh.set_app_credentials(app_id="THE_APP_ID", app_privkey="THE_APP_PRIVKEY")

        def matcher(request: requests.Request):
            if (
                request.method != "POST"
                or request.url
                != "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers"
            ):
                return None

            payload = request.json()
            # Reject requests with the enterprise team.
            if rejected_enterprise_team.name in payload.get("team_reviewers", []):
                resp = requests.Response()
                resp.request = request
                resp.status_code = 422
                # Insert a recognisable error response.
                resp._content = (
                    b"Rejected in test_github_reviewable_add_reviewers_retry"
                )
                return resp

            # Delegate to pre-existing matchers.
            return None

        mock._adapter.add_matcher(matcher)

        status = gh.reviewable.add_new_reviewers(iter(reviewers))

        assert status == AddReviewersStatus(len(reviewers) - 1, False)
        assert "Adding one reviewer at a time ..." in caplog.text
        assert f"Failed to add reviewer {rejected_enterprise_team.name}" in caplog.text

        with pytest.raises(HTTPError):
            # Requesting only a rejected reviewers should raise an exception.
            gh.reviewable.add_new_reviewers([rejected_enterprise_team])

        # The original mock doesn't see the requests summarily rejected by the matcher we added.
        assert mock.requested_reviewers_post.call_count == len(expected_reviewers)

        # Make sure all reviewers are now present.
        for user in [r for r in expected_reviewers if not r.is_group]:
            assert user in gh.reviewable.reviewers, (
                f"Missing user reviewer: {user.name}"
            )
        for group in [r for r in expected_reviewers if r.is_group]:
            assert group in gh.reviewable.reviewers, (
                f"Missing group reviewer: {group.name}"
            )

        assert rejected_enterprise_team not in gh.reviewable.reviewers, (
            "Test logic error: The rejected group reviewer was added"
        )


@patch("reviewer_selector.github.GitHubApp.generate_token")
def test_github_reviewable_add_reviewers_noretry(
    mock_gh_generate_token: Mock,
    configurable_mocked_github_request: Callable,
    caplog: pytest.LogCaptureFixture,
):
    rejected_enterprise_team = Reviewer("ent:fluent-reviewers", True)
    expected_reviewers = [
        Reviewer("test-reviewer", False),
        Reviewer("jsmith", False),
        Reviewer("fluent-reviewers", True),
    ]
    reviewers = expected_reviewers + [rejected_enterprise_team]

    with configurable_mocked_github_request() as mock:
        gh = GitHubPR(
            "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
        )
        mock_gh_generate_token.return_value = "THE_TOKEN"
        gh.set_app_credentials(app_id="THE_APP_ID", app_privkey="THE_APP_PRIVKEY")

        mock_post = mock.post(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            status_code=500,
        )

        with pytest.raises(HTTPError):
            gh.reviewable.add_new_reviewers(reviewers)

        assert "Adding one reviewer at a time ..." not in caplog.text
        assert mock_post.call_count == 1
