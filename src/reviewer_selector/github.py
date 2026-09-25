import asyncio
import logging
import re
from abc import ABCMeta
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from enum import Enum
from functools import cached_property, wraps
from typing import Any, final, override

import requests
from requests.exceptions import HTTPError
from simple_github import AppAuth, AppInstallationAuth

from reviewer_selector.patch import PatchSource
from reviewer_selector.review import (
    MappingUserResolver,
    Reviewable,
    Reviewer,
    UserResolver,
)
from reviewer_selector.rules import Rules
from reviewer_selector.taskcluster import tc_task_url

logger = logging.getLogger(__name__)

GITHUB_CHECK_NAME = "reviewer-selector"


@dataclass
class GitHubApp:
    """Wrapper providing GitHub authentication via a GitHub app."""

    app_id: str
    app_privkey: str
    gh_owner: str
    gh_repo: str

    def generate_token(
        self,
    ) -> str:
        """Generate a GitHub token using an application credentials."""
        return asyncio.run(
            self.async_generate_github_token(
                self.app_id, self.app_privkey, self.gh_owner, self.gh_repo
            )
        )

    @staticmethod
    async def async_generate_github_token(
        app_id: str, app_privkey: str, gh_owner: str, gh_repo: str
    ) -> str:
        """Sync wrapper around simple_github to generate a token."""
        # app_id can be an int OR an str, but the current release of simple_github is
        # lacking the second annotation.
        app_auth = AppAuth(app_id, app_privkey)  # pyright: ignore[reportArgumentType]
        inst_auth = AppInstallationAuth(app_auth, gh_owner, repositories=[gh_repo])
        token = await inst_auth.get_token()
        await inst_auth.close()
        return token


class RequestScope(Enum):
    """Specify the scope of request to make for the PR.

    This is used by GitHubApiObject.api_request, to decide which base endpoint to use when building a
    full URL.
    """

    REPO = 0
    ORG = 1


class GitHubApiObject(metaclass=ABCMeta):
    """Abstract class providing utilities for requests to arbitrary GitHub API objects.

    `owner` and `repository` need to be set by the inheriting class prior to using those
    methods.
    """

    owner: str
    repository: str

    _session: requests.Session
    _gh_app: GitHubApp | None = None
    _gh_token: str | None = None

    def __init__(self, owner: str, repository: str):
        self.owner = owner
        self.repository = repository
        self._session = requests.Session()

    def set_app_credentials(
        self, *, app_id: str = "", app_privkey: str = "", gh_token: str = ""
    ):
        """Configure the GitHub application credentials."""
        self._gh_token = gh_token
        if app_id and app_privkey:
            self._gh_app = GitHubApp(app_id, app_privkey, self.owner, self.repository)

    @staticmethod
    def authenticated(fn: Callable) -> Callable:
        """Decorator to generate a GitHub token for the Requests session."""

        @wraps(fn)
        def wrapped(*args, **kwargs):
            self: GitHubPR = args[0]

            # create token
            if not self._gh_token:
                if not self._gh_app:
                    raise ValueError(
                        "Missing GitHub app credentials, cannot set reviewers"
                    )
                self._gh_token = self._gh_app.generate_token()

            self._session.headers["Authorization"] = f"Bearer {self._gh_token}"

            return fn(*args, **kwargs)

        return wrapped

    def api_request(
        self,
        path: str = "",
        method: str = "GET",
        json: dict[Any, Any] | None = None,
        *,
        request_scope: RequestScope = RequestScope.REPO,
    ) -> dict[str, Any]:

        match request_scope:
            case RequestScope.REPO:
                url = f"{self._repo_api_url}{path}"
            case RequestScope.ORG:
                url = f"{self._org_api_url}{path}"

        resp = self._session.request(
            method,
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            json=json,
        )
        try:
            resp.raise_for_status()
        except HTTPError as exc:
            if exc.response.status_code >= 400 and exc.response.status_code < 500:
                logger.exception(
                    f"{exc.response.status_code} error from GitHub, with payload {exc.request.body}: {exc.response.text}"
                )
            raise
        return resp.json()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"

    @property
    def _org_api_url(self) -> str:
        return f"https://api.github.com/orgs/{self.owner}"

    @authenticated
    def authenticated_api_request(self, *args, **kwargs) -> dict[str, Any]:
        return self.api_request(*args, **kwargs)


@dataclass
class GitHubPatchSource(PatchSource):
    _pr: "GitHubPR"

    @property
    @override
    def patch(self) -> str:
        resp = self._pr.fetch(self._pr.patch_url)
        resp.raise_for_status()
        return resp.text

    @override
    def get_patch_subject(self) -> str:
        return self._pr.metadata.get("title", "")


class GitHubReviewerAdditionException(Exception):
    """Exception thrown when not all requested reviewers were added.

    The GitHub REST API silently ignores non-existent users in POST
    /requested_reviewers request, and returns apparently unconditional 201.

    To be sure reviewers were added, we inspect the response. If they are found missing,
    we throw this exception to trigger the same fallback as if an HTTPError had occured.
    """


@dataclass
class GitHubReviewable(Reviewable):
    _pr: "GitHubPR"

    @cached_property
    @override  # From Reviewable.
    def reviewers(self) -> Iterable[Reviewer]:
        """Return PR requested_reviewers, fetching it if needed."""
        requested_reviewers_json = self._pr.authenticated_api_request(
            "/requested_reviewers"
        )
        reviewers = []
        for r in requested_reviewers_json.get("users", []):
            reviewers.append(Reviewer(r["login"], False))
        for t in requested_reviewers_json.get("teams", []):
            reviewers.append(Reviewer(t["slug"], True))

        return reviewers

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]) -> int:
        """Set reviewers on the target.

        If an error from the server occurs, we retry to add one reviewer at a time.
        If no reviewers were added after this retry, the exception is re-raised for
        processing in the caller.
        """
        reviewers = set(reviewers)

        new_reviewers_count = len(reviewers)
        if new_reviewers_count == 0:
            return 0

        requested_reviewers = self._build_request_reviewers_payload(reviewers)
        expected_reviewers_count = len(set(self.reviewers) | reviewers)

        added = []
        failed = []
        try:
            resp = self._pr.authenticated_api_request(
                "/requested_reviewers", "POST", requested_reviewers
            )
            if (
                all_reviewers_count := len(resp.get("requested_reviewers", []))
                + len(resp.get("requested_teams", []))
            ) != expected_reviewers_count:
                # The REST API happily returns 201 in some cases where it could not
                # resolve some of the reviewers. Catch this, and try to add them one-by-one
                # for proper error handling.
                raise GitHubReviewerAdditionException(
                    f"Expected a total of {expected_reviewers_count} reviewers after adding, but only found {all_reviewers_count}."
                )
            added = reviewers
        except (HTTPError, GitHubReviewerAdditionException) as exc:
            if isinstance(exc, HTTPError) and (
                exc.response.status_code < 400 or exc.response.status_code >= 500
            ):
                raise
            # We let the caller report the raised exception above. But if we continue
            # here, we take care of it ourselves.
            logger.exception("Error while adding all reviewers at once")

            logger.info("Adding one reviewer at a time ...")

            for r in reviewers:
                try:
                    resp = self._pr.authenticated_api_request(
                        "/requested_reviewers",
                        "POST",
                        self._build_request_reviewers_payload([r]),
                    )
                    if (
                        r.is_group
                        and r.name
                        in [r.get("slug") for r in resp.get("requested_teams", [])]
                        or r.name
                        in [r.get("login") for r in resp.get("requested_reviewers", [])]
                    ):
                        added.append(r)
                    else:
                        raise GitHubReviewerAdditionException(
                            "Reviewer not found after adding individually ..."
                        )
                except (HTTPError, GitHubReviewerAdditionException) as exc2:
                    logger.warning(f"Failed to add reviewer {r.name}: {exc2}")
                    failed.append(r)

            if not added:
                raise

        # Invalidate cached_property.
        try:
            del self.reviewers
        except AttributeError:
            # There was no cache.
            pass

        if teams := requested_reviewers.get("team_reviewers", []):
            self._report_empty_teams(teams)

        if failed:
            # We don't prefix usernames with @, as they could be unmapped Phabricator
            # names that may not be the same person in GitHub.
            failed_reviewers_string = ", ".join(f"`{r.name}`" for r in failed)
            self.report_info(
                f"> [!WARNING]\n> Failed to request reviews from the following reviewers: {failed_reviewers_string}"
            )

        return len(added)

    @staticmethod
    def _build_request_reviewers_payload(
        reviewers: Collection[Reviewer],
    ) -> dict[str, Any]:
        requested_reviewers = {
            "reviewers": [],
            "team_reviewers": [],
        }
        for r in reviewers:
            if r.is_group:
                requested_reviewers["team_reviewers"].append(r.name)
            else:
                requested_reviewers["reviewers"].append(r.name)

        return requested_reviewers

    def _report_empty_teams(self, teams: list[str]):
        empty_teams = []

        for team in teams:
            try:
                members = self._pr.authenticated_api_request(
                    f"/teams/{team}/members?per_page=1", request_type=RequestType.TEAMS
                )
            except HTTPError:
                logger.exception(f"Failed to check members of team {team}")
                continue

            if len(members) < 1:
                empty_teams.append(team)

        if empty_teams:
            empty_teams_names = ", ".join(f"`{t}`" for t in empty_teams)
            self.report_info(
                f"> [!WARNING]\n> The following requested teams have no members: {empty_teams_names}"
            )

    @override
    def report_error(self, message: str, **kwargs):
        """Record an error check to the PR."""
        super().report_error(message)
        self._report_check("failure", message)

    @override
    def report_info(self, message: str, **kwargs):
        """Add a comment to the PR."""
        super().report_info(message)
        try:
            self._pr.authenticated_api_request(
                "/comments",
                "POST",
                {"body": message},
                request_type=RequestType.ISSUES,
            )
        except Exception:
            logger.exception(f"Failed to report info `{message}` on PR")

    @override
    def report_success(self, message: str, **kwargs):
        """Record a successful check to the PR."""
        super().report_success(message)
        self._report_check("success", message)

    @override
    def report_warning(self, message: str, **kwargs):
        """Record a warning check to the PR."""
        super().report_warning(message)
        self._report_check("action_required", message)

    def _report_check(self, conclusion: str, message: str):
        """Record a check to the PR.

        This method is guaranteed not to raise exceptions, so as not to interrupt the
        main flow of the application.
        """
        try:
            check_data = {
                "name": GITHUB_CHECK_NAME,
                "head_sha": self._pr.head_sha,
                "status": "completed",
                "output": {
                    "title": "Reviewer selection",
                    "summary": message,
                },
                "conclusion": conclusion,
            }
            if task_url := tc_task_url():
                check_data["details_url"] = task_url

            if check_id := self._find_existing_check(GITHUB_CHECK_NAME):
                self._pr.authenticated_api_request(
                    f"/{check_id}",
                    "PATCH",
                    json=check_data,
                    request_type=RequestType.CHECK_RUNS,
                )
            else:
                self._pr.authenticated_api_request(
                    "", "POST", json=check_data, request_type=RequestType.CHECK_RUNS
                )
        except Exception:
            logger.exception(f"Failed to report {conclusion} `{message}` on PR")

    def _find_existing_check(self, check_name: str) -> int | None:
        checks = self._pr.authenticated_api_request(
            f"/{self._pr.head_sha}/check-runs?check_name={check_name}&filter=latest",
            request_type=RequestType.COMMITS,
        )
        if checks and (check_runs := checks.get("check_runs")):
            return check_runs[0].get("id")


class RequestType(Enum):
    """Specify the type of request to make for the PR.

    This is used by GitHubPR.api_request, to decide which endpoint to use when building a
    full URL.
    """

    CHECK_RUNS = 0
    COMMITS = 1
    ISSUES = 2
    PULL_REQUEST = 3
    TEAMS = 4


@final
class GitHubPR(GitHubApiObject):
    URL_RE = re.compile(
        r"https://github.com/(?P<owner>[-A-Za-z0-9]+)/(?P<repository>[^/]+?)/pull/(?P<pr_number>\d+)"
    )

    pr_url: str

    pr_number: int

    # We need default rules if they exist, so we can apply default user-mapping.
    _default_rules: Rules

    def __init__(self, pr_url: str, default_rules: Rules | None = None):
        match = self.URL_RE.match(pr_url)
        if not match:
            raise ValueError(f"Can't parse GitHub PR URL from {pr_url}")

        GitHubApiObject.__init__(
            self, owner=match["owner"], repository=match["repository"]
        )

        self.pr_number = int(match["pr_number"])

        self.pr_url = pr_url

        self._default_rules = default_rules or Rules({})

    @cached_property
    def rules(self) -> Rules:
        r: requests.Response = self.fetch_rules()

        if r.status_code == 200:
            logger.info("Using in-tree rules ...")
            return Rules(r.json())

        if r.status_code == 404:
            logger.debug("No in-tree rules found, using default ...")

        else:
            logger.warning(
                f"Error fetching in-tree rules, using default; {r.status_code=} {r.text=}"
            )

        return self._default_rules

    def fetch_rules(self) -> requests.Response:
        rules_url = self._blob_url("herald_rules.json")
        logger.debug(f"Fetching in-tree rules from {rules_url} ...")
        return self.fetch(rules_url)

    def _blob_url(self, path: str) -> str:
        return f"{self.repo_url}/raw/refs/heads/{self.target_branch_name}/{path}"

    @cached_property
    def patch_source(self) -> PatchSource:
        return GitHubPatchSource(self)

    @property
    def patch_url(self) -> str:
        return self.pr_url + ".patch"

    def fetch(self, url: str) -> requests.Response:
        resp = self._session.get(url)
        return resp

    @cached_property
    def user_resolver(self) -> UserResolver:
        return MappingUserResolver(
            group_prefix="",
            user_map=self.rules.get_rules().get("github_users", {}),
            custom_map=self._custom_map,
        )

    @staticmethod
    def _custom_map(r: Reviewer) -> Reviewer | None:
        """Custom reviewer mapping function preventing enterprise teams from being prefixed."""
        if r.name.startswith("/ent:"):
            # Workaround oddities in naming/display of enterprise team slugs.
            r = r.mutate(name=r.name.removeprefix("/"))
        if r.name.startswith("ent:"):
            return r

        return None

    @cached_property
    def reviewable(self) -> Reviewable:
        return GitHubReviewable(self)

    @property
    def repo_url(self):
        return f"https://github.com/{self.owner}/{self.repository}"

    @property
    def target_branch_name(self) -> str:
        return self.metadata["base"]["ref"]

    @property
    def head_sha(self) -> str:
        return self.metadata["head"]["sha"]

    @cached_property
    def metadata(self) -> dict[str, Any]:
        """Return PR metadata."""
        return self.api_request()

    @override
    def api_request(
        self,
        path: str = "",
        method: str = "GET",
        json: dict[Any, Any] | None = None,
        *,
        request_type: RequestType = RequestType.PULL_REQUEST,
    ) -> dict[str, Any]:
        """Make a request about this PR to the GitHub REST API.

        Some PR interactions (comments, checks, ...) are done via non pull-scoped
        endpoints. This can be specified with the `request_type` parameter.

        """
        match request_type:
            case RequestType.CHECK_RUNS:
                request_scope = RequestScope.REPO
                qualified_path = f"/check-runs{path}"
            case RequestType.COMMITS:
                request_scope = RequestScope.REPO
                qualified_path = f"/commits{path}"
            case RequestType.ISSUES:
                request_scope = RequestScope.REPO
                qualified_path = f"/issues/{self.pr_number}{path}"
            case RequestType.PULL_REQUEST:
                request_scope = RequestScope.REPO
                qualified_path = f"/pulls/{self.pr_number}{path}"
            case RequestType.TEAMS:
                request_scope = RequestScope.ORG
                qualified_path = path

        return super().api_request(
            qualified_path, method, json, request_scope=request_scope
        )
