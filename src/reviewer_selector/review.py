from abc import ABCMeta, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
import logging
from typing import Callable, Self, override

UserMap = Mapping[str, Mapping[str, str]]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reviewer:
    name: str
    is_group: bool = False

    def mutate(self, **kwargs) -> Self:
        """Return a mutated Reviewer based on the current instance."""
        values = asdict(self)

        values.update(**kwargs)

        return Reviewer(**values)


class Reviewable(metaclass=ABCMeta):
    """An interface for something able to receive a list of reviewers."""

    @property
    @abstractmethod
    def reviewers(self) -> Iterable[Reviewer]:
        """Get all reviewers assigned to this Reviewable."""

    def add_new_reviewers(self, reviewers: Iterable[Reviewer]):
        """Add reviewers from the list, who are not already requested."""
        current_reviewers = set(self.reviewers)
        new_reviewers = [r for r in reviewers if r not in current_reviewers]

        if not new_reviewers:
            logger.info("No new reviewers to add")
            return

        logger.info(f"Adding new reviewers: {new_reviewers} ...")
        self.add_reviewers(new_reviewers)

    @abstractmethod
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """Set reviewers on the target."""


class InMemoryReviewable(Reviewable):
    """A `Reviewable` implementation storing state in memory."""

    _reviewers: set[Reviewer] | None = None

    @property
    @override
    def reviewers(self) -> Iterable[Reviewer]:
        return self._reviewers or set()

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        """Set reviewers on the target."""
        self._reviewers = set(self.reviewers) | set(reviewers)


class StdoutReviewable(InMemoryReviewable):
    """A Reviewable implementation outputting reviewers to STDOUT."""

    reviewer_separator: str

    def __init__(self, reviewer_separator: str = ","):
        self.reviewer_separator = reviewer_separator

    @override
    def add_reviewers(self, reviewers: Iterable[Reviewer]):
        print(self.reviewer_separator.join(sorted(r.name for r in reviewers)))
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

            result.add(Reviewer(mapped, r.is_group))
        return result
