import json
import pathlib
import sys
from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any, TypeVar
from unittest import mock

import pytest
import requests
import requests_mock
import simple_github
from requests.compat import urlsplit
from requests_mock.mocker import Mocker

from team_creator import (
    add_team_members,
    create_teams,
    ensure_team_exists,
    get_team_members,
    main,
    paginated_get,
    remove_team_members,
)


class GitHubDoubleException(Exception):
    pass


class GithubDouble(Mocker):
    org_name: str

    base_url: str
    members_per_team: dict[str, set[str]]

    def __init__(self, org_name: str = "test-org"):
        super().__init__()
        self.org_name = org_name

        self.base_url = f"https://api.github.com/orgs/{self.org_name}"
        self.members_per_team = {}

        def catchall_matcher(request: requests.Request) -> requests.Response:

            if (
                request.url.startswith(f"{self.base_url}/teams")
                and request.method == "POST"
            ):
                payload = request.json()
                assert payload, (
                    "[GithubDouble] missing or non-JSON POST /teams payload."
                )
                self.create_team(payload["name"])
                resp = self._make_response(request, 201)
                return resp

            return self._make_response(
                request, 404, error_reason=f"{request.method} not supported"
            )

        self.adapter.add_matcher(catchall_matcher)

    #
    # TEAMS
    #

    T = TypeVar("T")

    @staticmethod
    def transform_github_double_exception(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except GitHubDoubleException as exc:
                # Request should be the first argument on callbacks.
                request = args[0]

                return GithubDouble._make_response(
                    request, 400, error_reason=f"[GitHubDouble] Exception {exc}"
                )

        return wrapper

    def create_team(self, team_name: str):

        @self.transform_github_double_exception
        def team_matcher(request: requests.Request) -> requests.Response | None:
            """Matcher for the REST subpaths for the new team."""
            if request.url.startswith(f"{self.base_url}/teams/{team_name}"):
                rest_path = urlsplit(request.url)
                split_url = rest_path.path.split("/")
                # /orgs/{organisation}/teams/{team_name}
                if split_url[-1] == team_name and request.method == "GET":
                    if team_name not in self.members_per_team:
                        return self._make_response(request, 404)

                    return self._make_response(request)

                # /orgs/{organisation}/teams/{team_name}/memberships/{user}
                if split_url[-2] == "memberships" and request.method == "PUT":
                    member = split_url[-1]
                    self.add_members(team_name, [member])
                    return self._make_response(request)

                # /orgs/{organisation}/teams/{team_name}/memberships/{user}
                if split_url[-2] == "memberships" and request.method == "DELETE":
                    member = split_url[-1]
                    self.delete_member(team_name, member)
                    return self._make_response(request, 204)

                # /orgs/{organisation}/teams/{team_name}/members
                if split_url[-1] == "members" and request.method == "GET":
                    content = json.dumps(
                        [{"login": u} for u in self.get_team_members(team_name)]
                    ).encode()
                    return self._make_response(request, 200, content=content)

        if team_name not in self.members_per_team:
            self.members_per_team[team_name] = set()
            self.adapter.add_matcher(team_matcher)

    #
    # MEMBERS
    #

    def add_members(self, team_name: str, members: Iterable[str]):
        if team_name not in self.members_per_team:
            raise GitHubDoubleException(
                f"Team {team_name} to add member in doesn't exist"
            )
        self.members_per_team[team_name] |= set(members)

    def delete_member(self, team_name: str, member: str):
        if team_name not in self.members_per_team:
            raise GitHubDoubleException(
                f"Team {team_name} to remove member from doesn't exist"
            )
        if member not in self.members_per_team[team_name]:
            raise GitHubDoubleException(f"User {member} not member of {team_name}")
        self.members_per_team[team_name].remove(member)

    def get_team_members(self, team_name: str) -> set[str]:
        return self.members_per_team[team_name]

    #
    # UTILITIES
    #

    @property
    def adapter(self) -> requests_mock.adapter.Adapter:
        # request_mocks.mocker.Mocker has _adapter.
        return self._adapter

    @staticmethod
    def _make_response(
        request: requests.Request,
        status_code=200,
        *,
        content: bytes = b"{}",
        error_reason: str = "",
    ) -> requests.Response:
        resp = requests.Response()
        resp.request = request
        resp.url = request.url
        resp.status_code = status_code
        resp._content = content

        if error_reason:
            resp.reason = f"[GitHubDouble] {error_reason}"
            if content == b"{}":
                resp._content = (f'{{ "error": {resp.reason} }}').encode()

        return resp


@pytest.fixture
def github_double() -> GithubDouble:
    mock = GithubDouble("test-org")

    return mock


@pytest.fixture
def mocked_github_client() -> simple_github.Client:
    return simple_github.TokenClient("token")


def test_paginated_get(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):

    base_url = f"{github_double.base_url}/test_paginated_url"
    users = ["alice", "bob"]

    def callback(_request: requests.Request, context: requests_mock.response._Context):
        if not users:
            context.status_code = 422
            return "No more pages"

        user = users.pop(0)

        if users:
            # We only have two users. Add a link to the second page, with some ignorable
            # cruft.
            context.headers["link"] = (
                f'<{base_url}?page=whatever>; rel="prev", <{base_url}?page=2>; rel="next", <{base_url}?page=whocares>; rel="last", <{base_url}?page=1>; rel="first"'
            )

        return [user]

    with github_double as mock:
        # add link header
        mock.get(base_url, json=callback)
        response = [
            elt
            for pg in paginated_get(
                mocked_github_client, f"/orgs/{mock.org_name}/test_paginated_url"
            )
            for elt in pg
        ]

        with pytest.raises(requests.exceptions.HTTPError) as exc_info:
            next(
                paginated_get(
                    mocked_github_client, f"/orgs/{mock.org_name}/test_paginated_url"
                )
            )

        assert exc_info.value.response.status_code == 422

    assert response == ["alice", "bob"]
    assert len(github_double.adapter.request_history) == 3, (
        "Unexpected number of requests to paginated endpoint"
    )
    assert [r.url for r in github_double.adapter.request_history] == [
        "https://api.github.com/orgs/test-org/test_paginated_url?per_page=100",
        # We only add the per_page on first call. Subsequent requests are driven by the
        # next link header.
        "https://api.github.com/orgs/test-org/test_paginated_url?page=2",
        # The failing request, same as the first one, but now that we depleted the user
        # list, this raises the 422
        "https://api.github.com/orgs/test-org/test_paginated_url?per_page=100",
    ]


def test_get_team_members(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):
    team_name = "test-team"

    github_double.create_team(team_name)
    github_double.add_members(team_name, ("alice", "bob"))

    with github_double:
        members = get_team_members(
            mocked_github_client, github_double.org_name, team_name, False
        )

    assert members == {"alice", "bob"}

    assert len(github_double.request_history) == 1, (
        "Unexpected number of requests to GitHub"
    )
    assert github_double.adapter.request_history[0].url.startswith(
        f"https://api.github.com/orgs/test-org/teams/{team_name}/members"
    ), "Unexpected request URL"
    assert github_double.adapter.request_history[0].method == "GET", (
        "Unexpected request method"
    )


def test_add_team_members(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):
    team_name = "test-team"

    github_double.create_team(team_name)

    with github_double:
        add_team_members(
            mocked_github_client,
            github_double.org_name,
            team_name,
            {"alice", "bob"},
            False,
        )

    members = github_double.get_team_members(team_name)
    assert members == {"alice", "bob"}

    assert len(github_double.request_history) == 2, (
        "Unexpected number of requests to GitHub"
    )
    assert {request.url for request in github_double.adapter.request_history} == {
        f"https://api.github.com/orgs/test-org/teams/{team_name}/memberships/{member}"
        for member in members
    }
    assert all(
        request.method == "PUT" for request in github_double.adapter.request_history
    )


def test_ensure_team_exists(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):
    team_name = "test-team"
    parent_team_name = "parent-team"

    with github_double:
        ensure_team_exists(
            mocked_github_client,
            github_double.org_name,
            team_name,
            False,
            parent_team=parent_team_name,
            display_name=team_name,
        )

        # Call it a second time.
        ensure_team_exists(
            mocked_github_client,
            github_double.org_name,
            team_name,
            False,
            display_name=team_name,
        )

    assert len(github_double.request_history) == 3, (
        "Unexpected number of requests to GitHub"
    )

    first_get_request = github_double.adapter.request_history[0]
    assert (
        first_get_request.url
        == f"https://api.github.com/orgs/test-org/teams/{team_name}"
    ), "Unexpected request URL"
    assert first_get_request.method == "GET", "Unexpected request method"

    # POST.
    post_request = github_double.adapter.request_history[1]
    assert post_request.url == "https://api.github.com/orgs/test-org/teams", (
        "Unexpected request URL"
    )
    assert post_request.method == "POST", "Unexpected request method"
    payload = post_request.json()
    assert payload["name"] == team_name, "Incorrect team name in team creation payload"
    assert payload["parent_team_slug"] == parent_team_name, (
        "Incorrect parent_team_slug in team creation payload"
    )

    # Second GET.
    second_get_request = github_double.adapter.request_history[2]
    assert (
        second_get_request.url
        == f"https://api.github.com/orgs/test-org/teams/{team_name}"
    ), "Unexpected request URL"
    assert second_get_request.method == "GET", "Unexpected request method"


def test_remove_team_members(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):
    team_name = "test-team"

    github_double.create_team(team_name)
    github_double.add_members(team_name, ("alice", "bob", "carol"))

    with github_double:
        remove_team_members(
            mocked_github_client, github_double.org_name, team_name, {"bob"}, False
        )
        remove_team_members(
            mocked_github_client, github_double.org_name, team_name, {"mallory"}, False
        )

    members = github_double.get_team_members(team_name)

    assert members == {"alice", "carol"}

    # One for bob, one for mallory
    assert len(github_double.request_history) == 2, (
        "Unexpected number of requests to GitHub"
    )
    assert (
        github_double.adapter.request_history[0].url
        == f"https://api.github.com/orgs/test-org/teams/{team_name}/memberships/bob"
    ), "Unexpected request URL"
    assert github_double.adapter.request_history[0].method == "DELETE", (
        "Unexpected request method"
    )


def test_dry_run(
    github_double: GithubDouble, mocked_github_client: simple_github.Client
):
    team_name = "test-team"

    with github_double:
        # Test failure modes.
        ensure_team_exists(
            mocked_github_client,
            github_double.org_name,
            team_name,
            True,
            display_name="team_name",
        )
        get_team_members(mocked_github_client, github_double.org_name, team_name, True)

        # Now create the team so we can check deeper.
        github_double.create_team(team_name)
        github_double.add_members(team_name, {"alice"})

        team = ensure_team_exists(
            mocked_github_client,
            github_double.org_name,
            team_name,
            True,
            display_name="team_name",
        )
        assert team == {}, "Missing data should be shimmed in dry run"

        members = get_team_members(
            mocked_github_client, github_double.org_name, team_name, True
        )
        assert members == {"alice"}, "Existing data should be returned in dry run"

        add_team_members(
            mocked_github_client,
            github_double.org_name,
            team_name,
            {"alice", "bob"},
            True,
        )
        remove_team_members(
            mocked_github_client,
            github_double.org_name,
            team_name,
            {"alice", "bob"},
            True,
        )

    assert len(members) == 1, "Expected correct member list in dry run"
    # 2 (team + members) GETs
    assert len(github_double.request_history) == 4, (
        "Unexpected number of requests to GitHub (only GETs allowed)"
    )

    # /orgs/{organisation}/teams/{team_name}
    team_name = "raises-error"
    with github_double as mock:
        mock.get(
            f"{mock.base_url}/orgs/{mock.org_name}/teams/{team_name}", status_code=418
        )
        ret = ensure_team_exists(
            mocked_github_client,
            github_double.org_name,
            team_name,
            True,
            display_name=team_name,
        )

    # Due to https://github.com/jamielennox/requests-mock/issues/277, we cannot reset
    # the mock to only check the new request.
    expected_requests = 4 + 1
    assert len(github_double.request_history) == expected_requests, (
        "Unexpected number of requests to GitHub (only GETs allowed)"
    )
    assert ret == {}


def test_create_teams(
    github_double: GithubDouble,
    mocked_github_client: simple_github.Client,
    sample_rules_data: dict[str, Any],
):

    with github_double:
        create_teams(
            mocked_github_client,
            sample_rules_data,
            github_double.org_name,
            "all-reviewers",
            False,
        )

    assert_all_rules_teams_up_to_date(github_double, sample_rules_data)


def test_create_teams_missing_mappings(
    github_double: GithubDouble,
    mocked_github_client: simple_github.Client,
    sample_rules_data: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
):
    del sample_rules_data["github_users"]["alice"]
    del sample_rules_data["github_users"]["bob"]["username"]
    sample_rules_data["github_users"]["charlie"]["username"] = ""

    with github_double:
        create_teams(
            mocked_github_client,
            sample_rules_data,
            github_double.org_name,
            "all-reviewers",
            False,
        )

    assert "Unresolved GitHub username for alice" in caplog.text
    assert "Empty or missing GitHub username for bob" in caplog.text
    assert "Empty or missing GitHub username for charlie" in caplog.text


def test_create_teams_user_removal(
    github_double: GithubDouble,
    mocked_github_client: simple_github.Client,
    sample_rules_data: dict[str, Any],
):
    team_name = next(iter(sample_rules_data["groups"]))
    github_double.create_team(team_name)
    # Add an extra user to be removed.
    github_double.add_members(team_name, "mallory")

    with github_double:
        create_teams(
            mocked_github_client,
            sample_rules_data,
            github_double.org_name,
            "all-reviewers",
            False,
        )

    assert_all_rules_teams_up_to_date(github_double, sample_rules_data)


def test_team_creator_no_args(
    tmp_path: pathlib.Path,
    github_double: GithubDouble,
    sample_rules_data: dict[str, Any],
):
    with pytest.raises(SystemExit):
        _run_team_creator(tmp_path, github_double, [], sample_rules_data)


@pytest.mark.parametrize("use_short_env_variable", (True, False))
def test_team_creator_gh_tokens(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    github_double: GithubDouble,
    sample_rules_data: dict[str, Any],
    use_short_env_variable: bool,
):
    env_var = "GH_TOKEN" if use_short_env_variable else "GITHUB_TOKEN"
    unset_var = "GITHUB_TOKEN" if use_short_env_variable else "GH_TOKEN"
    monkeypatch.delenv(unset_var)
    monkeypatch.setenv(env_var, f"env_{env_var}")

    _run_team_creator(tmp_path, github_double, [], sample_rules_data)

    assert_all_rules_teams_up_to_date(github_double, sample_rules_data)


def test_team_creator_most_args(
    tmp_path: pathlib.Path,
    github_double: GithubDouble,
    sample_rules_data: dict[str, Any],
):
    args = [
        "--base-team",
        "all-reviewers",
        "--debug",
        "--dry-run",
        "--github-token",
        "cli_gh_token",
    ]

    _run_team_creator(tmp_path, github_double, args, sample_rules_data)

    # Shallow check that something happened, other tests cover the details.
    assert len(github_double.request_history), "No requests were made"
    assert all(r.method == "GET" for r in github_double.request_history), (
        "Only GET requests should have happened in dry-run"
    )


def _run_team_creator(
    tmp_path: pathlib.Path,
    github_double: GithubDouble,
    args: list[str],
    rules: dict[str, Any],
):
    rules_path = tmp_path / "sample_rules.json"
    rules_path.write_text(json.dumps(rules))

    args += ["--organisation", github_double.org_name, str(rules_path)]

    with mock.patch.object(sys, "argv", ["team_creator"] + args), github_double:
        main()


def assert_all_rules_teams_up_to_date(
    github_double: GithubDouble, rules: dict[str, Any]
):
    for team_name, team in rules["groups"].items():
        assert github_double.get_team_members(team_name) == {
            (rules["github_users"].get(m, {}).get("username") or m)
            for m in team["members"]
        }, f"Unexpected members in team {team_name}"
