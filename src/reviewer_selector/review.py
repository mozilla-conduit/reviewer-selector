from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
import logging
from typing import override

Reviewer = tuple[str, bool]  # (target, is_group)
UserMap = Mapping[str, Mapping[str, str]]

logger = logging.getLogger(__name__)


class Reviewable(metaclass=ABCMeta):
    """An interface for something able to receive a list of reviewers."""

    @abstractmethod
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """Set reviewers on the target."""


class StdoutReviewable(Reviewable):
    reviewer_separator: str

    def __init__(self, reviewer_separator: str = ","):
        self.reviewer_separator = reviewer_separator

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """A Reviewable implementation outputting reviewers to STDOUT."""
        print(self.reviewer_separator.join(sorted(r[0] for r in reviewers)))


class UserResolver:
    _user_map: UserMap
    _group_prefix: str

    def __init__(self, user_map: UserMap, group_prefix: str = "@"):
        self._user_map = user_map
        self._group_prefix = group_prefix

    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        """Convert to GitHub usernames, prefix groups.

        Each entry is unique."""
        result: set[Reviewer] = set()
        for target, is_group in reviewers:
            mapped: str | None = None
            if is_group:
                if target.startswith("/ent:"):
                    # GitHub enterprise teams are not org-scoped.
                    mapped = target
                    logger.debug(f"Left {target} group unchanged")
                else:
                    mapped = f"{self._group_prefix}{target}"
                    logger.debug(f"Rewrote {target} group to {mapped}")
            elif target in self._user_map:
                mapped = self._user_map[target]["username"]
                logger.debug(f"Resolved {target} to {mapped}")

            if not mapped:
                logger.warning(f"Unresolved {target}, skipping ...")
                continue

            result.add((mapped, is_group))
        return result
