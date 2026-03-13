#!/usr/bin/env python3
"""Select reviewers based on Herald rules and git diff."""

import argparse
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from rs_parsepatch import get_diffs

RulesData = Mapping[str, Any]
Rule = Mapping[str, Any]
Reviewer = tuple[str, bool]  # (target, is_group)


def main() -> None:
    args: argparse.Namespace = parse_args()
    with open(args.rules_file) as f:
        rules_data: RulesData = json.load(f)
    changed_files: Sequence[str] = parse_diff(sys.stdin.read())
    reviewers: Iterable[Reviewer] = collect_reviewers(
        rules_data, changed_files, args.repo
    )
    resolved: Iterable[str] = resolve_reviewers(
        reviewers, rules_data, args.group_prefix
    )
    print(args.reviewer_separator.join(sorted(resolved)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select reviewers from Herald rules and git diff"
    )
    parser.epilog = f"Example:\n\tcurl https://github.com/mozilla-firefox/infra-testing/pull/30.diff | {parser.prog} herald_rules.json"
    parser.add_argument("rules_file", help="Path to JSON rules file")
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


def parse_diff(diff_text: str) -> Sequence[str]:
    """Extract file paths from git diff."""
    if not diff_text:
        return []
    diffs = get_diffs(diff_text)
    return [d["filename"] for d in diffs]


def collect_reviewers(
    rules_data: RulesData, changed_files: Iterable[str], repos: Iterable[str]
) -> Iterable[Reviewer]:
    """Return set of (target, is_group) tuples from matching rules."""
    reviewers: set[Reviewer] = set()
    for rule in rules_data["rules"]:
        if not matches_repo_filter(rule, repos):
            continue
        if matches_files(rule, changed_files):
            reviewers.update(get_rule_reviewers(rule))
    return reviewers


def matches_repo_filter(rule: Rule, repos: Iterable[str]) -> bool:
    """Check if rule passes repository filter."""
    repos_list = list(repos)
    if not repos_list:
        return True
    for cond in rule.get("conditions", []):
        if cond.get("type") == "repository":
            rule_repos = cond.get("value", [])
            return any(r in rule_repos for r in repos_list)
    return True


def matches_files(rule: Rule, changed_files: Iterable[str]) -> bool:
    """Check if any changed file matches rule's regex."""
    for cond in rule.get("conditions", []):
        if cond.get("type") == "differential-affected-files":
            pattern = cond.get("value", "")
            regex = re.compile(pattern)
            return any(regex.search(f) for f in changed_files)
    return False


def get_rule_reviewers(rule: Rule) -> Iterable[Reviewer]:
    """Extract reviewers from rule's add-reviewers action."""
    result: list[Reviewer] = []
    for action in rule.get("actions", []):
        if action.get("type") == "add-reviewers":
            for reviewer in action.get("reviewers", []):
                result.append((reviewer["target"], reviewer.get("is_group", False)))
    return result


def resolve_reviewers(
    reviewers: Iterable[Reviewer], rules_data: RulesData, group_prefix: str
) -> Iterable[str]:
    """Convert to GitHub usernames, prefix groups."""
    github_users = rules_data.get("github_users", {})
    result: set[str] = set()
    for target, is_group in reviewers:
        if is_group:
            result.add(f"{group_prefix}{target}")
        elif target in github_users:
            result.add(github_users[target]["username"])
    return result


if __name__ == "__main__":
    main()
