from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence
import logging
import re
import sys
from typing import Any, override

import rs_parsepatch

from reviewer_selector.review import Reviewer

logger = logging.getLogger(__name__)

# Note that we only allows a subset of legal IRC-nick characters.
# Specifically, we do not allow [ \ ] ^ ` { | }
# In addition, allow `:` to allow GitHub ent:-prefix enterprise teams.
NICK = r"[a-zA-Z0-9\-\_.]*[a-zA-Z0-9\-\_:]+"
GROUP_MARKER = r"#"
BLOCKING_MARKER = r"!"
REVIEWER = GROUP_MARKER + r"?" + NICK + BLOCKING_MARKER + r"?"
SEPARATOR = r"[;,\/\\]\s*"
REVIEWERS_TAG = r"r[=?](?P<reviewers>((" + SEPARATOR + ")?" + REVIEWER + ")+)"


class Patch:
    """Wrapper around patch data, with optional patch metadata header."""

    _subject: str
    _patch: str
    _parsed_diffs: Sequence[Mapping[str, Any]]

    def __init__(self, diff: str, subject: str = ""):
        self._subject = subject
        self._patch = diff
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

        reviewers = []
        for r in subject_reviewers:
            is_group = GROUP_MARKER in r
            is_blocking = BLOCKING_MARKER in r
            name = r.removeprefix(GROUP_MARKER).removesuffix(BLOCKING_MARKER)
            reviewers.append(
                Reviewer(name=name, is_group=is_group, blocking=is_blocking)
            )

        return reviewers

    @staticmethod
    def parse_subject_reviewers(subject: str) -> Iterable[str]:
        matches = re.search(REVIEWERS_TAG, subject)
        if not matches:
            return []
        return re.split(SEPARATOR, matches.group("reviewers"))


class PatchSource(metaclass=ABCMeta):
    """An interface for something able to produce Patch data."""

    @abstractmethod
    def fetch_patch(self) -> str:
        """Return a patch from this source."""


class StdinPatchSource(PatchSource):
    """A PatchSource implementation reading a diff from STDIN."""

    @override
    def fetch_patch(self) -> str:
        return sys.stdin.read()
