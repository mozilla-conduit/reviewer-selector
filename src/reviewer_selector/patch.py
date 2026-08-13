from functools import cached_property
import logging
import re
import sys
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, override

import rs_parsepatch

from reviewer_selector.review import Reviewer

logger = logging.getLogger(__name__)

# Allow Phabricator usernames.
# In addition, allow `:` to allow GitHub ent:-prefix enterprise teams.
USERNAME = r"[a-zA-Z0-9\-\_.]*[a-zA-Z0-9\-\_:]+"
GROUP_MARKER = r"#"
BLOCKING_MARKER = r"!"
REVIEWER = GROUP_MARKER + r"?" + USERNAME + BLOCKING_MARKER + r"?"
SEPARATOR = r"[;,\/\\]\s*"
REVIEWERS_TAG = r"\Wr[=?](?P<reviewers>((" + SEPARATOR + ")?" + REVIEWER + ")+)"


class Patch:
    """Wrapper around patch or diff data, with optional patch metadata header."""

    _subject: str
    _patch: str
    _parsed_diffs: Sequence[Mapping[str, Any]]

    def __init__(self, patch: str, subject: str = ""):
        self._subject = subject
        self._patch = patch
        self._parse_patch()

    def _parse_patch(self):
        self._parsed_diffs = rs_parsepatch.get_diffs(self._patch)

    def get_changed_files(self):
        """Get the list of modified file patchs."""
        filenames = [d["filename"] for d in self._parsed_diffs]

        logger.info(f"Considering filenames: {', '.join(filenames)} ...")

        return filenames

    def get_subject_reviewers(self) -> Iterable[Reviewer]:
        """Parse the patch subject, looking for r[?=] patterns."""
        subject_reviewers = self.parse_subject_reviewers(self._subject)

        reviewers = set()
        for r in subject_reviewers:
            is_group = GROUP_MARKER in r
            is_blocking = BLOCKING_MARKER in r
            name = r.removeprefix(GROUP_MARKER).removesuffix(BLOCKING_MARKER)
            reviewers.add(Reviewer(name=name, is_group=is_group, blocking=is_blocking))

        if not subject_reviewers:
            logger.debug("No reviewers requested in commit message")
            return reviewers

        logger.info(f"Reviewers from commit message: {', '.join(subject_reviewers)}")

        return reviewers

    @staticmethod
    def parse_subject_reviewers(subject: str) -> Iterable[str]:
        matches = re.search(REVIEWERS_TAG, subject)
        if not matches:
            return []
        return re.split(SEPARATOR, matches.group("reviewers"))


class PatchSource(metaclass=ABCMeta):
    """An interface for something able to produce Patch data."""

    @property
    @abstractmethod
    def patch(self) -> str:
        """Return a patch from this source."""

    @abstractmethod
    def get_patch_subject(self) -> str:
        """Return a subject line for this patch."""


class StdinPatchSource(PatchSource):
    """A PatchSource implementation reading a diff or patch from STDIN.

    The patch is only read once, on the first request to the object's methods.
    """

    SUBJECT: str = "Subject: "

    @cached_property
    @override
    def patch(self) -> str:
        return sys.stdin.read()

    @override
    def get_patch_subject(self) -> str:
        """Return the first `Subject` line from a patch.

        If the patch hasn't been read yet, do it now.
        """
        for line in self.patch.splitlines():
            if line.startswith(self.SUBJECT):
                return line.removeprefix(self.SUBJECT)

        return ""
