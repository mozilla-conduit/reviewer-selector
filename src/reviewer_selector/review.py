from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import logging
from typing import override

UserMap = Mapping[str, Mapping[str, str]]

logger = logging.getLogger(__name__)


@dataclass
class Reviewer:
    name: str
    is_group: bool

    @override
    def __hash__(self):
        """Make this dataclass hashable for use in sets."""
        return (self.name, self.is_group).__hash__()


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
        print(self.reviewer_separator.join(sorted(r.name for r in reviewers)))


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
        for r in reviewers:
            mapped: str | None = None
            if r.is_group:
                if r.name.startswith("/ent:"):
                    # GitHub enterprise teams are not org-scoped.
                    mapped = r.name
                    logger.debug(f"Left {r.name} group unchanged")
                else:
                    mapped = f"{self._group_prefix}{r.name}"
                    logger.debug(f"Rewrote {r.name} group to {mapped}")
            elif r.name in self._user_map:
                mapped = self._user_map[r.name]["username"]
                logger.debug(f"Resolved {r.name} to {mapped}")

            if not mapped:
                logger.warning(f"Unresolved {r.name}, skipping ...")
                continue

            result.add(Reviewer(mapped, r.is_group))
        return result
