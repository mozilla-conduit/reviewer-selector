from collections.abc import Iterable, Mapping
from functools import cached_property
import os
import re
from typing import Any, final, override

import requests

from reviewer_selector.patch import PatchSource
from reviewer_selector.lib.phabricator import PhabricatorClient
from reviewer_selector.review import Reviewable, Reviewer
from reviewer_selector.rules import Rules


class PhabricatorPatchSource(PatchSource):
    phab: PhabricatorClient

    _rev: "PhabricatorRevision"

    def __init__(self, rev: "PhabricatorRevision"):
        self._rev = rev
        self.phab = rev.phab

    @override
    def fetch_patch(self) -> str:
        diff_phid = self.phab.expect(self._rev.metadata, "fields", "diffPHID")
        diff_data = self.phab.call_conduit(
            "differential.diff.search", constraints={"phids": [diff_phid]}
        )
        diff_id = self.phab.expect(diff_data, "data", 0, "id")
        diff = self.phab.call_conduit("differential.getrawdiff", diffID=diff_id)
        return diff


Phid = str
PhabReviewerData = Mapping[str, Any]
PhabReviewerMetadata = Mapping[str, Any]


class PhabricatorReviewable(Reviewable):
    phab: PhabricatorClient

    _rev: "PhabricatorRevision"

    def __init__(self, rev: "PhabricatorRevision"):
        self._rev = rev
        self.phab = rev.phab

    @property
    @override
    def reviewers(self) -> Iterable[Reviewer]:
        rev_reviewers = self.phab.expect(
            self._rev.metadata, "attachments", "reviewers", "reviewers"
        )
        reviewers_by_phid = {
            r["reviewerPHID"]: {
                "phid": r["reviewerPHID"],
                "blocking": r["isBlocking"],
                "status": r["status"],
            }
            for r in rev_reviewers
        }

        phab_users = self.phab.call_conduit(
            "user.search",
            constraints={
                "phids": [
                    phid for phid in reviewers_by_phid if phid.startswith("PHID-USER-")
                ]
            },
        )
        phab_projects = self.phab.call_conduit(
            "project.search",
            constraints={
                "phids": [
                    phid for phid in reviewers_by_phid if phid.startswith("PHID-PROJ-")
                ]
            },
        )

        return self._build_reviewers(
            reviewers_by_phid, self.phab.expect(phab_users, "data"), False
        ) + self._build_reviewers(
            reviewers_by_phid, self.phab.expect(phab_projects, "data"), True
        )

    def _build_reviewers(
        self,
        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata],
        phab_data: Iterable[PhabReviewerData],
        is_group: bool,
    ) -> list[Reviewer]:
        """Build a list of reviewers of a given type.

        Parameters:

        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata]

            Additional metadata to copy into the Reviewer objects, keyed by PHID.

        phab_data: PhabReviewerData

            List of Phabricator data about reviewers of a given type.

        is_group: bool

            Whether the reviewers in the phab_data are groups.
        """
        return [
            self._build_reviewer(reviewers_by_phid, reviewer_data, is_group)
            for reviewer_data in phab_data
        ]

    def _build_reviewer(
        self,
        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata],
        phab_data: PhabReviewerData,
        is_group: bool,
    ) -> Reviewer:
        """Build a single Reviewer based on Phabricator data.

        Parameters:

        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata]

            Additional metadata to copy into the Reviewer object, keyed by PHID.

        phab_data: PhabReviewerData

            Phabricator data about a single reviewer.

        is_group: bool

            Whether this reviewer is a group.
        """

        name_attribute = "slug" if is_group else "username"

        phid = self.phab.expect(phab_data, "phid")
        name = self.phab.expect(phab_data, "fields", name_attribute)
        metadata = reviewers_by_phid.get(phid, {})
        return Reviewer(name=name, is_group=is_group, metadata=metadata)

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        r = self.reviewers
        print(r)
        # TODO: actually add reviewers as needed
        raise NotImplementedError("PhabricatorReviewable.add_reviewers")


@final
class PhabricatorRevision:
    PHAB_URL_RE = re.compile(r"(?P<base_url>https://[^/]+)/(?P<revision>D\d+)")

    revision_url: str

    base_url: str
    revision_id: str

    phab: PhabricatorClient

    _api_token: str
    _session: requests.Session

    def __init__(self, revision_url: str, api_token: str | None = None):
        self.revision_url = revision_url
        try:
            self.base_url, self.revision_id = re.match(
                self.PHAB_URL_RE, self.revision_url
            ).groups()
        except AttributeError:
            raise ValueError(f"Not a valid Phabricator revision URL: {revision_url}")

        self._api_token = api_token or self.get_token_from_env()

        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})

        self.phab = PhabricatorClient(
            self.base_url, self._api_token, session=self._session
        )

    @staticmethod
    def get_token_from_env() -> str:
        if api_token := os.environ.get("PHABRICATOR_API_TOKEN"):
            return api_token

        raise ValueError("Missing PHABRICATOR_API_TOKEN.")

    @property
    def repository(self) -> str:
        return self.phab.expect(self._repository_data, "fields", "shortName")

    @cached_property
    def _repository_data(self) -> str:
        phid = self.phab.expect(self.metadata, "fields", "repositoryPHID")
        result = self.phab.call_conduit(
            "diffusion.repository.search",
            constraints={"phids": [phid]},
        )
        return self.phab.expect(result, "data", 0)

    @cached_property
    def patch_source(self) -> PatchSource:
        return PhabricatorPatchSource(self)

    @cached_property
    def rules(self) -> Rules:
        # Determine source repo (maybe GitHub)
        # Fetch from there
        return Rules({})

    @cached_property
    def reviewable(self) -> Reviewable:
        return PhabricatorReviewable(self)

    @cached_property
    def metadata(self):
        result = self.phab.call_conduit(
            "differential.revision.search",
            constraints={"ids": [self.int_rev_id]},
            attachments={"reviewers": True},
        )
        return self.phab.expect(result, "data", 0)

    @property
    def int_rev_id(self):
        return int(self.revision_id.removeprefix("D"))
