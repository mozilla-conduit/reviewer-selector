from collections.abc import Iterable
from typing import Any, final, override

import requests
import re

from reviewer_selector.patch import PatchSource
from reviewer_selector.review import Reviewer, Reviewable


@final
class GitHubPR(PatchSource, Reviewable):
    URL_RE = re.compile(
        r"https://github.com/(?P<owner>[-A-Za-z0-9]+)/(?P<repository>[^/]+?)/pull/(?P<pr_number>\d+)"
    )

    pr_url: str

    _owner: str
    _repository: str
    _pr_number: int

    _session: requests.Session

    def __init__(self, pr_url: str):

        match = self.URL_RE.match(pr_url)
        if not match:
            raise ValueError(f"Can't parse GitHub PR URL from {pr_url}")

        self._owner = match["owner"]
        self._repository = match["repository"]
        self._pr_number = int(match["pr_number"])

        self.pr_url = pr_url

        self._session = requests.Session()

    @override  # From PatchSource.
    def fetch_patch(self) -> str:
        return self.fetch(self.patch_url)

    @property
    def patch_url(self) -> str:
        return self.pr_url + ".patch"

    @override  # From Reviewable.
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        # create token

        # send request
        raise NotImplementedError()

    def fetch_rules(self) -> str:
        return self.fetch(self._blob_url("herald_rules.json"))

    def fetch(self, url: str) -> str:
        resp = self._session.get(url)
        resp.raise_for_status()
        return resp.text

    def _blob_url(self, path: str) -> str:
        return f"{self._repo_url}/raw/refs/heads/{self._target_branch_name}/{path}"

    @property
    def _repo_url(self):
        return f"https://github.com/{self._owner}/{self._repository}"

    @property
    def _target_branch_name(self) -> str:
        return self._pr_metadata["base"]["ref"]

    @property
    def _pr_metadata(self) -> dict[str, Any]:
        return self.api_fetch(f"/pulls/{self._pr_number}")

    def api_fetch(self, path: str) -> dict[str, Any]:
        resp = self._session.get(f"{self._repo_api_url}{path}")
        resp.raise_for_status()
        return resp.json()

    @property
    def _repo_api_url(self) -> str:
        return f"https://api.github.com/repos/{self._owner}/{self._repository}"
