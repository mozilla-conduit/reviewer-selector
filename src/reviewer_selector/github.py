from collections.abc import Iterable
import logging
from typing import Any, final, override

import requests
import re

from reviewer_selector.patch import PatchSource
from reviewer_selector.review import (
    MappingUserResolver,
    Reviewer,
    Reviewable,
    UserResolver,
)
from reviewer_selector.rules import Rules

logger = logging.getLogger(__name__)


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

    # Use the rule @property to access those.
    _rules: Rules
    _remote_rules_checked: bool = False

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
        return f"{self.repo_url}/raw/refs/heads/{self._target_branch_name}/{path}"

    @override
    def fetch_patch(self) -> str:
        """Return a patch from this source.

        From the PatchSource interface.
        """
        resp = self.fetch(self.patch_url)
        resp.raise_for_status()
        return resp.text

    @property
    def patch_url(self) -> str:
        return self.pr_url + ".patch"

    @override
    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        """Update the content of the reviewers based on arbitrary criteria.

        From the UserResolver interface.
        """
        user_resolver = MappingUserResolver(
            group_prefix="@",
            user_map=self.rules.get_rules().get("github_users", {}),
            custom_map=self.custom_map,
        )
        return user_resolver.resolve_reviewers(reviewers)

    @staticmethod
    def custom_map(reviewer: Reviewer) -> Reviewer | None:
        """Custom reviewer mapping function preventing enterprise teams from being prefixed."""
        if reviewer.name.startswith("/ent:"):
            return reviewer

        return None

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """Set reviewers on the target.

        From the Reviewable interface.
        """
        # create token

        # send request
        raise NotImplementedError()

    def fetch(self, url: str) -> requests.Response:
        resp = self._session.get(url)
        return resp

    @property
    def repo_url(self):
        return f"https://github.com/{self.owner}/{self.repository}"

    @property
    def _target_branch_name(self) -> str:
        return self._pr_metadata["base"]["ref"]

    @property
    def _pr_metadata(self) -> dict[str, Any]:
        return self.api_fetch(f"/pulls/{self.pr_number}")

    def api_fetch(self, path: str) -> dict[str, Any]:
        resp = self._session.get(f"{self._repo_api_url}{path}")
        resp.raise_for_status()
        return resp.json()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self.owner}/{self.repository}"
