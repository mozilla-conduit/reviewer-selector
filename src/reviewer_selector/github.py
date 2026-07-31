from abc import ABCMeta
import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps
import logging
from typing import Any, Callable, final, override

import requests
import re

from simple_github import AppAuth, AppInstallationAuth
from reviewer_selector.patch import PatchSource
from reviewer_selector.review import (
    MappingUserResolver,
    Reviewer,
    Reviewable,
    UserResolver,
)
from reviewer_selector.rules import Rules
from reviewer_selector.utils import instance_cache

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
    """Abstract class providing authentication utilities to make requests to arbitrary
        GitHub API objects.

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
            f"{self._repo_api_url}/pulls/{self.pr_number}{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
            },
            json=json,
        )
        try:
            resp.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 422:
                logger.error(
                    f"422 error from GitHub: {exc}, with payload {exc.request.body}: {exc.response.text}"
                )
            raise exc
        return resp.json()

    @authenticated
    def authenticated_api_request(self, *args, **kwargs) -> dict[str, Any]:
        return self.api_request(*args, **kwargs)


@dataclass
class GitHubPatchSource(PatchSource):
    _pr: "GitHubPR"

    @override
    def fetch_patch(self) -> str:
        resp = self._pr.fetch(self._pr.patch_url)
        resp.raise_for_status()
        return resp.text


@dataclass
class GitHubReviewable(Reviewable):
    _pr: "GitHubPR"

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        requested_reviewers = {
            "reviewers": [],
            "team_reviewers": [],
        }
        for r in reviewers:
            if r.is_group:
                requested_reviewers["team_reviewers"].append(r.name)
            else:
                requested_reviewers["reviewers"].append(r.name)

        self._pr.authenticated_api_request(
            "/requested_reviewers", "POST", requested_reviewers
        )


@final
class GitHubPR(GitHubApiObject):
    URL_RE = re.compile(
        r"https://github.com/(?P<owner>[-A-Za-z0-9]+)/(?P<repository>[^/]+?)/pull/(?P<pr_number>\d+)"
    )

    pr_url: str

    pr_number: int

    # Use the rule @property to access those.
    _rules: Rules | None = None

    # We need default rules if they exist, so we can apply default user-mapping.
    _default_rules: Rules

    # Will be populated on first access to _metadata
    _metadata_json: dict[str, Any] | None = None

    _patch_source: PatchSource | None = None
    _reviewable: Reviewable | None = None
    _user_resolver: UserResolver | None = None

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

    @property
    @instance_cache("_rules")
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

    @property
    @instance_cache("_patch_source")
    def patch_source(self) -> PatchSource:
        return GitHubPatchSource(self)

    @property
    def patch_url(self) -> str:
        return self.pr_url + ".patch"

    def fetch(self, url: str) -> requests.Response:
        resp = self._session.get(url)
        return resp

    @property
    @instance_cache("_user_resolver")
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

    @property
    @instance_cache("_reviewable")
    def reviewable(self) -> Reviewable:
        return GitHubReviewable(self)

    @property
    def repo_url(self):
        return f"https://github.com/{self.owner}/{self.repository}"

    @property
    def target_branch_name(self) -> str:
        return self._metadata["base"]["ref"]

    @property
    @instance_cache("_metadata_json")
    def _metadata(self) -> dict[str, Any]:
        """Return PR metadata, fetching it if needed."""
        return self.api_request()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"
