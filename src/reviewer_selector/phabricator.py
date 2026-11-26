import logging
import os
import re
from collections.abc import Collection, Iterable, Mapping
from functools import cached_property, lru_cache
from typing import Any, Self, final, override

from reviewer_selector.lib.phabricator import (
    PhabricatorClient,
    PhabricatorRevisionStatus,
)
from reviewer_selector.patch import PatchSource
from reviewer_selector.review import Reviewable, Reviewer
from reviewer_selector.utils import get_http_session

logger = logging.getLogger(__name__)


class PhabricatorPatchSource(PatchSource):
    """A PatchSource to provide Patch data from a Phabricator revision."""

    phab: PhabricatorClient

    _rev: PhabricatorRevision

    def __init__(self, rev: PhabricatorRevision):
        self._rev = rev
        self.phab = rev.phab

    @override
    @property
    def patch(self) -> str:
        """Return a patch from this source."""
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
# Local metadata about review statuses of users or projects.
PhabReviewerMetadata = Mapping[str, Any]


class PhabricatorReviewable(Reviewable):
    """Implement the Reviewable interface for a PhabricatorRevision."""

    phab: PhabricatorClient

    _rev: PhabricatorRevision

    def __init__(self, rev: PhabricatorRevision):
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
        """Add reviewers to the revision.

        The metadata of each Reviewer is updated to record their PHID.
        """
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

        self._rev.edit_transaction("reviewers.add", new_phids)
        self.invalidate_reviewers_cache()

        # XXX: We haven't checked if those have been correctly added.
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
                self.report_warning(
                    f"Missing name or slug for reviewer with PHID {phid}"
                )
                continue

            phids_by_names[name] = phid

        for rev in reviewers:
            if rev.metadata.get("phid"):
                continue
            phid = phids_by_names.get(rev.name)
            if not phid:
                self.report_info(
                    f"Missing PHID for reviewer `{rev.name}` after resolution attempt."
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

    @override
    def ready_for_review(self) -> bool:
        """Allows to skip reviewer selection.

        Criteria:
        - only needs-review
        """
        return self._rev.status == PhabricatorRevision.Status.NEEDS_REVIEW

    def invalidate_reviewers_cache(self):
        self._rev.invalidate_metadata()

    def report_error(self, message: str, **kwargs):
        """Report errors."""
        super().report_error(message)
        self._report_comment(f"(IMPORTANT) {message}")

    def report_info(self, message: str, **kwargs):
        """Report info."""
        super().report_info(message)
        self._report_comment(f"(NOTE) {message}")

    def report_success(self, message: str, **kwargs):
        """Report success."""
        super().report_success(message)
        # We don't report this one, to avoid being too noisy.

    def report_warning(self, message: str, **kwargs):
        """Report warnings."""
        super().report_warning(message)
        self._report_comment(f"(WARNING) {message}")

    def _report_comment(self, message: str):
        self._rev.edit_transaction("comment", message)


@final
class PhabricatorRevision:
    PHAB_URL_RE = re.compile(r"(?P<base_url>https?://[^/]+)/(?P<revision>D\d+)")

    Status = PhabricatorRevisionStatus

    revision_url: str

    base_url: str
    rev_monogram: str
    _cache_phid: str | None  # Used to reuse memoised metadata requests.

    phab: PhabricatorClient

    def __init__(
        self,
        revision_url: str,
        *,
        api_token: str | None = None,
        phab: PhabricatorClient | None = None,
        phid: str | None = None,
    ):
        """A Phabricator revision with an associated Phabricator client.

        Params:

        revision_url: str
        api_token: str

            Ignored if a PhabricatorClient is provided.

        phab: PhabricatorClient
        phid: str | None

            If known, leverage memoisation and avoid re-requesting revision metadata.

        """
        self.revision_url = revision_url
        try:
            self.base_url, self.rev_monogram = re.match(
                self.PHAB_URL_RE, self.revision_url
            ).groups()
        except AttributeError:
            raise ValueError(f"Not a valid Phabricator revision URL: {revision_url}")

        self.phab = phab or self._build_phab_client(self.base_url, api_token)
        self._cache_phid = phid

    @classmethod
    def from_phid(
        cls, base_url: str, revision_phid: str, api_token: str | None = None
    ) -> Self:

        phab = cls._build_phab_client(base_url, api_token)
        revision_data = _fetch_revision_data(phab, phid=revision_phid)
        revision_url = phab.expect(revision_data, "data", 0, "fields", "uri")

        return cls(revision_url, api_token=api_token, phab=phab, phid=revision_phid)

    @classmethod
    def _build_phab_client(
        cls, base_url: str, api_token: str | None = None
    ) -> PhabricatorClient:
        api_token = api_token or cls.get_token_from_env()
        session = get_http_session()
        session.headers.update({"Accept": "application/json"})
        return PhabricatorClient(base_url, api_token, session=session)

    @staticmethod
    def get_token_from_env() -> str:
        logger.debug("Using PHABRICATOR_API_TOKEN from environment")
        if api_token := os.environ.get("PHABRICATOR_API_TOKEN"):
            return api_token

        raise ValueError("Missing PHABRICATOR_API_TOKEN.")

    @property
    def repository(self) -> str:
        return self.phab.expect(self._repository_data, "fields", "shortName")

    @cached_property
    def _repository_data(self) -> dict[str, Any]:
        phid = self.phab.expect(self.metadata, "fields", "repositoryPHID")
        result = self.phab.call_conduit(
            "diffusion.repository.search",
            constraints={"phids": [phid]},
        )
        repo_data = self.phab.single(result, "data", none_when_empty=True)
        if repo_data is None:
            raise ValueError(f"Cannot fetch repository data for {phid}")

        return repo_data

    @cached_property
    def patch_source(self) -> PatchSource:
        return PhabricatorPatchSource(self)

    # TODO: implement in-tree rules fetching.

    @cached_property
    def reviewable(self) -> Reviewable:
        return PhabricatorReviewable(self)

    @cached_property
    def status(self) -> Status:
        status = self.phab.expect(self.metadata, "fields", "status", "value")
        if status in self.Status:
            return self.Status(status)

        return self.Status.UNEXPECTED_STATUS

    @cached_property
    def metadata(self):
        if self._cache_phid:
            result = _fetch_revision_data(self.phab, phid=self._cache_phid)
        else:
            result = _fetch_revision_data(self.phab, rev_id=self.rev_id)

        revision_data = self.phab.single(result, "data", none_when_empty=True)
        if revision_data is None:
            raise ValueError(f"Cannot fetch revision data for D{self.rev_id}")

        return revision_data

    def invalidate_metadata(self):
        try:
            del self.metadata
        except AttributeError:
            # There was no cache.
            pass

    @property
    def rev_id(self) -> int:
        return int(self.rev_monogram.removeprefix("D"))

    def edit_transaction(
        self, ttype: str, value: list[dict[str, Any]] | str
    ) -> dict[str, Any]:
        tx = self.phab.call_conduit(
            "differential.revision.edit",
            objectIdentifier=self.metadata["phid"],
            transactions=[
                {
                    "type": ttype,
                    "value": value,
                },
            ],
        )
        return tx


@lru_cache
def _fetch_revision_data(
    phab: PhabricatorClient, *, phid: str | None = None, rev_id: int | None = None
) -> dict[str, Any]:
    """A memoised metadata request to resolve revision data by PHID or ID.

    Not a method, to avoid memory leaks as per [0].

    [0] https://docs.astral.sh/ruff/rules/cached-instance-method/
    """
    REVISION_ATTACHMENTS = {
        "reviewers": True,
        "reviewers-extra": True,
        "projects": True,
    }

    if phid and rev_id:
        raise ValueError("Only one of phid or rev_id should be provided")

    if phid:
        return phab.call_conduit(
            "differential.revision.search",
            constraints={"phids": [phid]},
            attachments=REVISION_ATTACHMENTS,
        )
    elif rev_id:
        return phab.call_conduit(
            "differential.revision.search",
            constraints={"ids": [rev_id]},
            attachments=REVISION_ATTACHMENTS,
        )

    raise ValueError("Both rev_id and phid are missing")
