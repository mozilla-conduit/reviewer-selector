from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
import logging
from typing import Callable, override

UserMap = Mapping[str, Mapping[str, str]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reviewer:
    name: str
    is_group: bool = False
    blocking: bool = False

    def mutate(self, **kwargs) -> "Reviewer":
        """Return a mutated Reviewer based on the current instance."""
        values = asdict(self)

        values.update(**kwargs)

        return Reviewer(**values)

    @staticmethod
    def flatten_blocking(reviewers: Iterable["Reviewer"]) -> Iterable["Reviewer"]:
        """Flatten a set of reviewers by only preserving blocking ones in case of
        duplicates."""
        reviewers = set(reviewers)
        reviewers_list = list(reviewers)
        for r in reversed(reviewers_list):
            if r.blocking:
                continue
            if r.mutate(blocking=True) in reviewers:
                reviewers_list.remove(r)

        return set(reviewers_list)


class Reviewable(metaclass=ABCMeta):
    """An interface for something able to receive a list of reviewers."""

    _reviewers: set[Reviewer] | None = None

    @property
    def reviewers(self) -> set[Reviewer]:
        if not self._reviewers:
            return set()
        return self._reviewers

    def add_new_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        """Add reviewers from the list, who are not already requested.

        Return a set of all reviewers, new and pre-existing.
        """
        # Not very performant, but we should only be dealing with short lists.
        new_reviewers = [r for r in reviewers if r not in self.reviewers]

        logger.info(f"Adding new reviewers: {new_reviewers} ...")
        self.add_reviewers(new_reviewers)

        return self.reviewers

    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """Set reviewers on the target."""
        self._reviewers = self.reviewers | set(reviewers)


class StdoutReviewable(Reviewable):
    """A Reviewable implementation outputting reviewers to STDOUT."""

    reviewer_separator: str
    blocking_suffix: str

    def __init__(self, reviewer_separator: str = ",", blocking_suffix: str = "!"):
        self.reviewer_separator = reviewer_separator
        self.blocking_suffix = blocking_suffix

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        print(
            self.reviewer_separator.join(
                sorted(
                    r.name + (self.blocking_suffix if r.blocking else "")
                    for r in reviewers
                )
            )
        )
        super().add_reviewers(reviewers)


class UserResolver(metaclass=ABCMeta):
    """An interface for a transformer to apply to user names."""

    @abstractmethod
    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        """Update the content of the reviewers based on arbitrary criteria."""


class MappingUserResolver(UserResolver):
    """A UserResolver implementation doing group-prefixing and user-mapping."""

    _user_map: UserMap
    _group_prefix: str

    def __init__(
        self,
        group_prefix: str = "#",
        user_map: UserMap | None = None,
        custom_map: Callable[[Reviewer], Reviewer | None] | None = None,
    ):
        """Initialise a MappingUserResolver.

        Parameters:

        group_prefix: str

            string to prepend to group names, defaults to

        user_map: UserMap

            mapping to rewrite username, if present

        custom_map: Callable[[Reviewer], Reviewer | None]

            custom mapping function, which bypass the internal logic if it return a
        value for the current reviewer

        """
        self._group_prefix = group_prefix
        self._user_map = user_map or {}
        self._custom_map = custom_map

    @override
    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[Reviewer]:
        """Prefix groups, and convert usernames if a map was provided.

        Each entry is unique."""
        result: set[Reviewer] = set()
        for r in reviewers:
            if self._custom_map and (mapped_reviewer := self._custom_map(r)):
                result.add(mapped_reviewer)
                continue

            mapped: str = r.name
            if r.is_group:
                mapped = f"{self._group_prefix}{r.name}"
                logger.debug(f"Rewrote {r.name} group to {mapped}")
            elif r.name in self._user_map:
                mapped = self._user_map[r.name]["username"]
                logger.debug(f"Resolved {r.name} to {mapped}")

            result.add(Reviewer(mapped, r.is_group, r.blocking))
        return result
