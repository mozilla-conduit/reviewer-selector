import logging
from abc import ABCMeta, abstractmethod
from collections.abc import Iterable
from random import randrange

from reviewer_selector.review import Reviewer

logger = logging.getLogger(__name__)


class Strategy(metaclass=ABCMeta):
    """Base class for strategies transforming lists of reviewers."""

    def applicable_to_group(self, group: Reviewer):
        """Override to apply to a subset of groups."""
        return group.is_group

    @abstractmethod
    def apply(self, reviewers: Iterable[Reviewer]) -> set[Reviewer]:
        """Apply the strategy to the supplied reviewers.

        Params:

        reviewers: Iterable[Reviewer]

            Group members should have been populated with, e.g., Rules.populate_members.

        Returns: set[Reviewers]
        """

    @classmethod
    def _split_groups(
        cls, reviewers: Iterable[Reviewer]
    ) -> tuple[set[Reviewer], set[Reviewer]]:
        new_reviewers = set()
        groups = set()

        for rev in reviewers:
            if not rev.is_group:
                new_reviewers.add(rev)
            else:
                groups.add(rev)

        return (new_reviewers, groups)


class RoundRobinStrategy(Strategy):
    """Strategy selecting one of the members of each gorup with equal probability."""

    def applicable_to_group(self, group: Reviewer):
        return super().applicable_to_group(group) and group.name.endswith("-rotation")

    def apply(self, reviewers: Iterable[Reviewer]) -> set[Reviewer]:
        reviewers = list(reviewers)

        new_reviewers, groups = self._split_groups(reviewers)

        for grp in groups:
            if not self.applicable_to_group(grp):
                logger.debug(
                    f"{self.__class__.__name__}: Group {grp.name} is not applicable, keeping as is"
                )
                new_reviewers.add(grp)
                continue

            if not grp.members:
                logger.warning(
                    f"{self.__class__.__name__}: Group {grp.name} has no members, leaving as is"
                )
                new_reviewers.add(grp)
                continue

            rnd = randrange(0, len(grp.members))

            rev = list(grp.members)[rnd]

            logger.debug(
                f"{self.__class__.__name__}: Selected {rev.name} for group {grp.name}."
            )

            if rev not in new_reviewers:
                new_reviewers.add(rev)

        return new_reviewers
