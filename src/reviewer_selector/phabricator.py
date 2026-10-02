import logging
import os
import re
from collections.abc import Collection, Iterable, Mapping
from functools import cached_property
from typing import Any, final, override

import requests

from reviewer_selector.lib.phabricator import PhabricatorClient
from reviewer_selector.patch import PatchSource
from reviewer_selector.review import Reviewable, Reviewer
from reviewer_selector.rules import Rules
from reviewer_selector.utils import get_http_session

logger = logging.getLogger(__name__)


class PhabricatorPatchSource(PatchSource):
    phab: PhabricatorClient

    _rev: "PhabricatorRevision"

    def __init__(self, rev: "PhabricatorRevision"):
        self._rev = rev
        self.phab = rev.phab

    @override
    @property
    def patch(self) -> str:
        diff_phid = self.phab.expect(self._rev.metadata, "fields", "diffPHID")
        diff_data = self.phab.call_conduit(
            "differential.diff.search", constraints={"phids": [diff_phid]}
        )
        diff_id = self.phab.expect(diff_data, "data", 0, "id")
        diff = self.phab.call_conduit("differential.getrawdiff", diffID=diff_id)
        return diff

    @override
    def get_patch_subject(self) -> str:
        """Return a subject line for this patch."""
        return self.phab.expect(self._rev.metadata, "fields", "title")


Phid = str
# Reviewer data returned from Phabricator.
PhabReviewerData = Mapping[str, Any]
# Local metadata about review statuses of users orprojects.
PhabReviewerMetadata = Mapping[str, Any]

# @dataclass
# class ReviewerMetadata:
#     phid: str
#     blocking: bool
#     status: str


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

        resolved_reviewers = self._resolve_reviewers(
            phids=reviewers_by_phid.keys()
        ).values()
        reviewers = self._build_reviewers(reviewers_by_phid, resolved_reviewers)

        return reviewers

    def _build_reviewers(
        self,
        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata],
        phab_data: Iterable[PhabReviewerData],
    ) -> list[Reviewer]:
        """Build a list of reviewers of a given type.

        Parameters:

        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata]

            Additional metadata to copy into the Reviewer objects, keyed by PHID.

        phab_data: PhabReviewerData

            List of Phabricator data about reviewers of a given type.
        """
        return [
            self._build_reviewer(reviewers_by_phid, reviewer_data)
            for reviewer_data in phab_data
        ]

    def _build_reviewer(
        self,
        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata],
        phab_data: PhabReviewerData,
    ) -> Reviewer:
        """Build a single Reviewer based on Phabricator data.

        Parameters:

        reviewers_by_phid: Mapping[Phid, PhabReviewerMetadata]

            Additional metadata to copy into the Reviewer object, keyed by PHID.

        phab_data: PhabReviewerData

            Phabricator data about a single reviewer.
        """
        phid = self.phab.expect(phab_data, "phid")
        rtype = self.phab.expect(phab_data, "type")
        if rtype not in ["USER", "PROJ"]:
            raise ValueError(f"Incorrect type {rtype} for reviewer PHID {phid}")

        is_group = rtype == "PROJ"

        name_attribute = "slug" if is_group else "username"

        name = self.phab.expect(phab_data, "fields", name_attribute)

        metadata = reviewers_by_phid.get(phid, {})

        blocking = metadata.get("blocking", False)

        return Reviewer(
            name=name, blocking=blocking, is_group=is_group, metadata=metadata
        )

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]) -> int:
        reviewers = list(reviewers)
        reviewers = self._resolve_reviewers_names(reviewers)

        # Some reviewers may be dropped here if unresolved.
        new_phids = [
            r.metadata["phid"]
            for r in reviewers
            if r.metadata.get("phid") and not r.blocking
        ] + [
            f"blocking({r.metadata['phid']})"
            for r in reviewers
            if r.metadata.get("phid") and r.blocking
        ]
        if not new_phids:
            return 0

        # XXX: Reuse one-by-one retry from GitHub adapter.
        _add_reviewers_status = self._rev.edit_transaction("reviewers.add", new_phids)

        self.invalidate_reviewers_cache()

        # XXX: We don't know if those have all been correctly added.
        return len(new_phids)

    def _resolve_reviewers_names(self, reviewers: Iterable[Reviewer]) -> list[Reviewer]:
        """Resolve reviewers by name, and update the Reviewer objects."""
        no_phids_users = [
            r for r in reviewers if not r.is_group and not r.metadata.get("phid")
        ]
        no_phids_projects = [
            r for r in reviewers if r.is_group and not r.metadata.get("phid")
        ]

        reviewers_by_phid = self._resolve_reviewers(
            usernames=[u.name for u in no_phids_users],
            slugs=[u.name for u in no_phids_projects],
        )

        phids_by_names = {}
        for phid, phab_data in reviewers_by_phid.items():
            field = self.phab.expect(phab_data, "fields")
            name = field.get("username") or field.get("slug")
            if not name:
                self.report_warning(f"Missing name or slug for reviewer with PHID {phid}")
                continue

            phids_by_names[name] = phid

        for rev in reviewers:
            phid = phids_by_names.get(rev.name)
            if not phid:
                self.report_warning(
                    f"Missing phid for reviewer {rev.name} after phid resolution attempt"
                )

            rev.metadata["phid"] = phid

        return reviewers

    def _resolve_reviewers(
        self,
        *,
        phids: Collection[str] | None = None,
        slugs: Collection[str] | None = None,
        usernames: Collection[str] | None = None,
    ) -> dict[str, PhabReviewerMetadata]:
        """Query the Phabricator Conduit API to resolve users and/or project.

        Parameters:

        phids: Collection[str]

            list of phids (either PHID-USER or PHID-PROJ-) to resolve

        slugs: Collection[str]

            list of project slugs to resolve

        usernames: Collection[str]

            list of user names to resolve

        return: dict[str, PhabReviewerData]

            All the Phabricator data for the requested users, indexed by their PHID.
        """
        phids = phids or []
        slugs = slugs or []
        usernames = usernames or []

        resolved = []

        if user_phids := [phid for phid in phids if phid.startswith("PHID-USER-")]:
            phab_users = self.phab.call_conduit(
                "user.search",
                constraints={"phids": user_phids},
            )
            resolved.extend(self.phab.expect(phab_users, "data"))
        if group_phids := [phid for phid in phids if phid.startswith("PHID-PROJ-")]:
            phab_projects = self.phab.call_conduit(
                "project.search",
                constraints={"phids": group_phids},
            )
            resolved.extend(self.phab.expect(phab_projects, "data"))

        if slugs:
            phab_projects = self.phab.call_conduit(
                "project.search",
                constraints={"slugs": slugs},
            )
            resolved.extend(self.phab.expect(phab_projects, "data"))

        if usernames:
            phab_users = self.phab.call_conduit(
                "user.search",
                constraints={"usernames": usernames},
            )
            resolved.extend(self.phab.expect(phab_users, "data"))

        return {r["phid"]: r for r in resolved}

    def invalidate_reviewers_cache(self):
        self._rev.invalidate_metadata()

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

        self._session = get_http_session()
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
            attachments={"reviewers": True, "reviewers-extra": True, "projects": True},
        )
        return self.phab.expect(result, "data", 0)

    def invalidate_metadata(self):
        try:
            del self.metadata
        except AttributeError:
            # There was no cache.
            pass

    @property
    def int_rev_id(self):
        return int(self.revision_id.removeprefix("D"))

    def edit_transaction(
        self, ttype: str, value: list[dict[str, Any]] | str
    ) -> dict[str, Any]:
        return self.phab.call_conduit(
            "differential.revision.edit",
            objectIdentifier=self.metadata["phid"],
            transactions=[
                {
                    "type": ttype,
                    "value": value,
                },
            ],
        )
