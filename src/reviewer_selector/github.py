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

logger = logging.getLogger(__name__)


@dataclass
class GitHubApp:
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


def github_authenticated(fn: Callable) -> Callable:
    """Decorator to generate a GitHub token for the Requests session.

    Requires the decorated method to be on a class which the following attributes:
        * _gh_app: GitHubApp attribute
        * _session: Requests.Session
    """

    @wraps(fn)
    def wrapped(*args, **kwargs):
        self: GitHubPR = args[0]

        if not self._gh_app:
            raise ValueError("Missing GitHub app credentials, cannot set reviewers")

        # create token
        gh_token = self._gh_app.generate_token()
        self._session.headers["Authorization"] = f"Bearer {gh_token}"

        return fn(*args, **kwargs)

    return wrapped


@final
class GitHubPR(PatchSource, Reviewable, UserResolver):
    URL_RE = re.compile(
        r"https://github.com/(?P<owner>[-A-Za-z0-9]+)/(?P<repository>[^/]+?)/pull/(?P<pr_number>\d+)"
    )

    pr_url: str

    owner: str
    repository: str
    pr_number: int

    _session: requests.Session
    _gh_app: GitHubApp | None = None

    # Use the rule @property to access those.
    _rules: Rules
    _remote_rules_checked: bool = False

    # Will be populated on first access to _metadata
    _metadata_json: dict[str, Any] = {}

    def __init__(self, pr_url: str, default_rules: Rules | None = None):

        match = self.URL_RE.match(pr_url)
        if not match:
            raise ValueError(f"Can't parse GitHub PR URL from {pr_url}")

        self.owner = match["owner"]
        self.repository = match["repository"]
        self.pr_number = int(match["pr_number"])

        self.pr_url = pr_url

        self._session = requests.Session()

        self._rules = default_rules or Rules({})

    @property
    def rules(self) -> Rules:
        if self._remote_rules_checked:
            return self._rules

        r: requests.Response = self.fetch_rules()

        if r.status_code == 404:
            logger.debug("No in-tree rules found ...")
            self._remote_rules_checked = True

        elif r.status_code == 200:
            logger.info("Using in-tree rules ...")
            self._remote_rules_checked = True
            self._rules = Rules(r.json())

        else:
            logger.warning(
                f"Error fetching in-tree rules, using default; {r.status_code=} {r.text=}"
            )

        return self._rules

    def fetch_rules(self) -> requests.Response:
        rules_url = self._blob_url("herald_rules.json")
        logger.debug(f"Fetching in-tree rules from {rules_url} ...")
        return self.fetch(rules_url)

    def _blob_url(self, path: str) -> str:
        return f"{self.repo_url}/raw/refs/heads/{self.target_branch_name}/{path}"

    @override  # From PatchSource.
    def fetch_patch(self) -> str:
        resp = self.fetch(self.patch_url)
        resp.raise_for_status()
        return resp.text

    @property
    def patch_url(self) -> str:
        return self.pr_url + ".patch"

    def fetch(self, url: str) -> requests.Response:
        resp = self._session.get(url)
        return resp

    @override  # From UserResolver.
    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        user_resolver = MappingUserResolver(
            group_prefix="@",
            user_map=self.rules.get_rules().get("github_users", {}),
            custom_map=self.custom_map,
        )
        return user_resolver.resolve_reviewers(reviewers)

    @staticmethod
    def custom_map(r: Reviewer) -> Reviewer | None:
        """Custom reviewer mapping function preventing enterprise teams from being prefixed."""
        if r.name.startswith("/ent:"):
            return r

        return None

    def set_app_credentials(self, app_id: str, app_privkey: str):
        """Configure the GitHub application credentials."""
        self._gh_app = GitHubApp(app_id, app_privkey, self.owner, self.repository)

    @override  # From Reviewable.
    @github_authenticated
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

        self.api_request("/requested_reviewers", "POST", requested_reviewers)

    @property
    def repo_url(self):
        return f"https://github.com/{self.owner}/{self.repository}"

    @property
    def target_branch_name(self) -> str:
        return self._metadata["base"]["ref"]

    @property
    def _metadata(self) -> dict[str, Any]:
        """Return PR metadata, fetching it if needed."""
        if not self._metadata_json:
            self._metadata_json = self.api_request()
        return self._metadata_json

        return self._metadata_json

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
        resp.raise_for_status()
        return resp.json()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"
