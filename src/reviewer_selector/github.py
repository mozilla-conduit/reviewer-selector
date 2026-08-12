import asyncio
import logging
import re
from abc import ABCMeta
from collections.abc import Callable, Iterable
from dataclasses import dataclass
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

logger = logging.getLogger(__name__)


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
        self, path: str = "", method: str = "GET", json: dict[Any, Any] | None = None
    ) -> dict[str, Any]:
        resp = self._session.request(
            method,
            f"{self._repo_api_url}{path}",
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
                    f"{exc.response.status_code} error from GitHub: {exc}, with payload {exc.request.body}: {exc.response.text}"
                )
            raise
        return resp.json()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"

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


@dataclass
class GitHubReviewable(Reviewable):
    _pr: "GitHubPR"

    @cached_property
    @override  # From Reviewable.
    def reviewers(self) -> Iterable[Reviewer]:
        """Return PR requested_reviewers, fetching it if needed."""
        # As of 2026-07-09, the basic GitHub PR metadata does contain
        # `requested_reviewers` and `requested_teams` properties, but the latter is
        # always empty. This is not the case ftor the /requested_reviewers endpoint
        # we use here.
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
        reviewers = list(reviewers)
        requested_reviewers = self._build_request_reviewers_payload(reviewers)

        added = len(requested_reviewers["team_reviewers"]) + len(
            requested_reviewers["reviewers"]
        )
        if not added:
            return 0

        try:
            self._pr.authenticated_api_request(
                "/requested_reviewers", "POST", requested_reviewers
            )
        except HTTPError as exc:
            added = 0
            if exc.response.status_code >= 400 and exc.response.status_code < 500:
                logger.warning("Adding one reviewer at a time ...")

                for r in reviewers:
                    try:
                        self._pr.authenticated_api_request(
                            "/requested_reviewers",
                            "POST",
                            self._build_request_reviewers_payload([r]),
                        )
                        added += 1
                    except HTTPError as exc2:
                        logger.warning(f"Failed to add reviewer {r.name}: {exc2}")

            if added == 0:
                raise

        # Invalidate cached_property.
        try:
            del self.reviewers
        except AttributeError:
            # There was no cache.
            pass

        return added

    @staticmethod
    def _build_request_reviewers_payload(
        reviewers: list[Reviewer],
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

    @cached_property
    def metadata(self) -> dict[str, Any]:
        """Return PR metadata, fetching it if needed."""
        return self.api_request()

    @override
    def api_request(
        self, path: str = "", method: str = "GET", json: dict[Any, Any] | None = None
    ) -> dict[str, Any]:
        return super().api_request(f"/pulls/{self.pr_number}{path}", method, json)
