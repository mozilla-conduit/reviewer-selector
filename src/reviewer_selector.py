#!/usr/bin/env python3
"""Select reviewers based on Herald rules and git diff."""

import argparse
import json
import logging
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Self

import rs_parsepatch

RulesData = Mapping[str, Any]
Rule = Mapping[str, Any]
Reviewer = tuple[str, bool]  # (target, is_group)

UserMap = Mapping[str, Mapping[str, str]]

logger = logging.getLogger(__name__)


class Patch:
    _patch: str
    _parsed_diffs: Sequence[Mapping[str, Any]]

    def __init__(self, diff: str):
        self._patch = diff
        self._parse_patch()

    def _parse_patch(self):
        self._parsed_diffs = rs_parsepatch.get_diffs(self._patch)

    def get_patch(self):
        return self._patch

    def get_changed_files(self):
        """Extract file paths from git diff."""
        filenames = [d["filename"] for d in self._parsed_diffs]

        logger.info(f"Considering filenames: {', '.join(filenames)} ...")

        return filenames


class Rules:
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

        for rule in self._rules["rules"]:
            if repos and not self.rule_matches_repos(rule, repos):
                logger.debug(
                    f"Rule {rule['id']} ({rule["name"]}) doesn't match repositories"
                )
                continue
            if self.rule_matches_files(rule, changed_files):
                logger.info(f"Rule {rule['id']} ({rule["name"]}) matches files")
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
                action_reviewer_set: set[str] = set()
                for reviewer in action.get("reviewers", []):
                    result.add((reviewer["target"], reviewer.get("is_group", False)))
                    action_reviewer_set.add(reviewer["target"])
                logger.info(f"Adding reviewers from rule {rule['id']}: " + (", ".join(action_reviewer_set)))
        return result


class UserResolver:
    _user_map: UserMap
    _group_prefix: str

    def __init__(self, user_map: UserMap, group_prefix: str = "@"):
        self._user_map = user_map
        self._group_prefix = group_prefix

    def resolve_reviewers(self, reviewers: Iterable[Reviewer]) -> Iterable[str]:
        """Convert to GitHub usernames, prefix groups.

        Each entry is unique."""
        result: set[str] = set()
        for target, is_group in reviewers:
            if is_group:
                if target.startswith("/ent:"):
                    # GitHub enterprise teams are not org-scoped.
                    result.add(target)
                else:
                    mapped_group = f"{self._group_prefix}{target}"
                    logger.debug(f"Rewrote {target} group to {mapped_group}")
                    result.add(mapped_group)
            elif target in self._user_map:
                mapped_user = self._user_map[target]["username"]
                logger.debug(f"Resolved {target} to {mapped_user}")
                result.add(mapped_user)
        return result


def main() -> None:
    args: argparse.Namespace = parse_args()

    # Honour the highest verbosity level requested.
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)


    rules = Rules.from_file(args.rules_file)


    reviewers: Iterable[Reviewer] = rules.collect_reviewers(patch, args.repo)

    resolver = UserResolver(
        rules.get_rules().get("github_users", {}), args.group_prefix
    )

    resolved: Iterable[str] = resolver.resolve_reviewers(reviewers)

    print(args.reviewer_separator.join(sorted(resolved)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select reviewers from Herald rules and git diff",
        epilog="""Example:
            curl https://github.com/mozilla-firefox/infra-testing/pull/30.diff | %(prog)s herald_rules.json""",
    )
    parser.add_argument("rules_file", help="Path to JSON rules file")
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Log details of the reviewer selection",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Log debug message of the reviewer selection",
    )
    parser.add_argument(
        "--repo", action="append", default=[], help="Filter by repository (repeatable)"
    )
    parser.add_argument(
        "--group-prefix", default="#", help="Prefix for group names in output"
    )
    parser.add_argument(
        "--reviewer-separator",
        default=" ",
        help="Separator for reviewer names in output",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
