from collections.abc import Iterable, Mapping
import json
import logging
import re
from typing import Any, Self

from reviewer_selector.patch import Patch
from reviewer_selector.review import Reviewer


RulesData = Mapping[str, Any]
Rule = Mapping[str, Any]

logger = logging.getLogger(__name__)


class Rules:
    """Representation of Phabricator Herald Rules."""

    _rules: RulesData

    def __init__(self, rules: RulesData):
        self._rules = rules

    @classmethod
    def from_file(cls, rules_file: str) -> Self:
        with open(rules_file) as f:
            return cls(json.load(f))

    def get_rules(self) -> RulesData:
        return self._rules

    def collect_reviewers(
        self, patch: Patch, repos: Iterable[str]
    ) -> Iterable[Reviewer]:
        """Return set of (target, is_group) tuples from matching rules."""

        changed_files = patch.get_changed_files()
        reviewers: set[Reviewer] = set()

        if not repos:
            logger.info("No repositories specified, ignoring repository filters.")

        for rule in self._rules.get("rules", []):
            if repos and not self.rule_matches_repos(rule, repos):
                logger.debug(
                    f"Rule {rule['id']} ({rule['name']}) doesn't match repositories"
                )
                continue
            if self.rule_matches_files(rule, changed_files):
                logger.info(f"Rule {rule['id']} ({rule['name']}) matches files")
                reviewers.update(self.get_rule_reviewers(rule))
        return reviewers

    @classmethod
    def rule_matches_repos(cls, rule: Rule, repos: Iterable[str]) -> bool:
        """Check if rule passes repository filter."""
        repos_list = list(repos)
        if not repos_list:
            return True
        for cond in rule.get("conditions", []):
            if cond.get("type") == "repository":
                rule_repos = cond.get("value", [])
                return any(r in rule_repos for r in repos_list)
        return True

    @classmethod
    def rule_matches_files(cls, rule: Rule, changed_files: Iterable[str]) -> bool:
        """Check if any changed file matches rule's regex."""
        for cond in rule.get("conditions", []):
            if cond.get("type") == "differential-affected-files":
                pattern = cond.get("value", "")
                regex = re.compile(pattern)
                return any(regex.search(f) for f in changed_files)
        return False

    @classmethod
    def get_rule_reviewers(cls, rule: Rule) -> Iterable[Reviewer]:
        """Extract reviewers from rule's add-reviewers action.

        Each entry is unique."""
        result: set[Reviewer] = set()
        for action in rule.get("actions", []):
            if action.get("type") == "add-reviewers":
                action_reviewers_set: set[str] = set()
                for reviewer in action.get("reviewers", []):
                    result.add(
                        Reviewer(reviewer["target"], reviewer.get("is_group", False))
                    )
                    action_reviewers_set.add(reviewer["target"])
                logger.info(
                    f"Adding reviewers from rule {rule['id']}: "
                    + (", ".join(action_reviewers_set))
                )
        return result
