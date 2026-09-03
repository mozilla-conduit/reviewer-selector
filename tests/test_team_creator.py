import json
from collections.abc import Callable, Iterable
from functools import wraps
from typing import TypeVar

import pytest
import requests
import requests_mock
import simple_github
from requests.models import HTTPError
from requests_mock.mocker import Mocker

from team_creator import (
    add_team_members,
    ensure_team_exists,
    get_team_members,
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
            resp = requests.Response()

            if (
                request.url.startswith(f"{self.base_url}/teams")
                and request.method == "POST"
            ):
                payload = request.json()
                assert payload, "GithubDouble: missing or non-JSON POST /teams payload."
                self.create_team(payload["name"])
                resp.status_code = 201
                resp._content = b"{}"

            else:
                resp.status_code = 404
                # Insert a recognisable error response.
                resp._content = (
                    f'{{ "error": "GitHubDouble: REST request {request.method} {request.url} not supported." }}'
                ).encode()
            return resp

        self.adapter.add_matcher(catchall_matcher)

    #
    # TEAMS
    #

    T=TypeVar("T")

    @staticmethod
    def transform_github_double_exception(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except GitHubDoubleException as exc:

                resp = requests.Response()
                resp.status_code = 400
                # Insert a recognisable error response.
                resp._content = (
                    f'{{ "error": "GitHubDouble: {exc}." }}'
                ).encode()

                http_error = requests.exceptions.HTTPError()
                http_error.response = resp

                raise http_error from exc

        return wrapper

    def create_team(self, team_name: str):

        @self.transform_github_double_exception
        def team_matcher(request: requests.Request) -> requests.Response | None:
            """Matcher for the REST subpaths for the new team."""
            if request.url.startswith(f"{self.base_url}/teams/{team_name}"):
                resp = requests.Response()

                split_url = request.url.split("/")
                # /orgs/{organisation}/teams/{team_name}
                if split_url[-1] == team_name and request.method == "GET":
                    resp.status_code = 200
                    if team_name not in self.members_per_team:
                        resp.status_code = 404

                    resp._content = b"{}"

                # /orgs/{organisation}/teams/{team_name}/memberships/{user}
                elif split_url[-2] == "memberships" and request.method == "PUT":
                    member = split_url[-1]
                    self.add_members(team_name, [member])
                    resp.status_code = 200
                    resp._content = b"{}"

                # /orgs/{organisation}/teams/{team_name}/memberships/{user}
                elif split_url[-2] == "memberships" and request.method == "DELETE":
                    member = split_url[-1]
                    self.delete_member(team_name, member)
                    resp.status_code = 204

                # /orgs/{organisation}/teams/{team_name}/members
                elif split_url[-1] == "members" and request.method == "GET":
                    resp.status_code = 200
                    resp._content = json.dumps(
                        [{"login": u} for u in self.get_team_members(team_name)]
                    ).encode()

                return resp

        if team_name not in self.members_per_team:
            self.members_per_team[team_name] = set()
            self.adapter.add_matcher(team_matcher)

    #
    # MEMBERS
    #

    def add_members(self, team_name: str, members: Iterable[str]):
        if team_name not in self.members_per_team:
            raise GitHubDoubleException(f"Team {team_name} to add memmber in doesn't exist")
        self.members_per_team[team_name] |= set(members)

    def delete_member(self, team_name: str, member: str):
        if team_name not in self.members_per_team:
            raise GitHubDoubleException(f"Team {team_name} to remove member from doesn't exist")
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


@pytest.fixture
def github_double() -> GithubDouble:
    mock = GithubDouble("test-org")

    return mock


@pytest.fixture
def mocked_github_client() -> simple_github.Client:
    return simple_github.TokenClient("token")


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
    assert (
        github_double.adapter.request_history[0].url
        == f"https://api.github.com/orgs/test-org/teams/{team_name}/members"
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
    for i, m in enumerate(members):
        assert (
            github_double.adapter.request_history[i].url
            == f"https://api.github.com/orgs/test-org/teams/{team_name}/memberships/{m}"
        ), "Unexpected request URL"
        assert github_double.adapter.request_history[i].method == "PUT", (
            "Unexpected request method"
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
        )

        # Call it a second time.
        ensure_team_exists(
            mocked_github_client, github_double.org_name, team_name, False
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
            mocked_github_client, github_double.org_name, team_name, True
        )
        get_team_members(
            mocked_github_client, github_double.org_name, team_name, True
        )

        # Now create the team so we can check deeper.
        github_double.create_team(team_name)
        github_double.add_members(team_name, {"alice"})

        ensure_team_exists(
            mocked_github_client, github_double.org_name, team_name, True
        )

        members = get_team_members(
            mocked_github_client, github_double.org_name, team_name, True
        )
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
