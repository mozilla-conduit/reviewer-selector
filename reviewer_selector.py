#!/usr/bin/env python3
"""Select reviewers based on Herald rules and git diff."""

import argparse
import json
import re
import sys

from rs_parsepatch import get_diffs


def main():
    args = parse_args()
    rules_data = json.load(open(args.rules_file))
    changed_files = parse_diff(sys.stdin.read())
    reviewers = collect_reviewers(rules_data, changed_files, args.repo)
    resolved = resolve_reviewers(reviewers, rules_data, args.group_prefix)
    print(" ".join(sorted(resolved)))


def parse_args():
    parser = argparse.ArgumentParser(description="Select reviewers from Herald rules and git diff")
    parser.add_argument("rules_file", help="Path to JSON rules file")
    parser.add_argument("--repo", action="append", default=[], help="Filter by repository (repeatable)")
    parser.add_argument("--group-prefix", default="#", help="Prefix for group names in output")
    return parser.parse_args()


def parse_diff(diff_text):
    """Extract file paths from git diff. Returns list of file paths."""
    pass


def collect_reviewers(rules_data, changed_files, repos):
    """Return set of (target, is_group) tuples from matching rules."""
    reviewers = set()
    for rule in rules_data["rules"]:
        if not matches_repo_filter(rule, repos):
            continue
        if matches_files(rule, changed_files):
            reviewers.update(get_rule_reviewers(rule))
    return reviewers


def matches_repo_filter(rule, repos):
    """Check if rule passes repository filter. Returns bool."""
    pass


def matches_files(rule, changed_files):
    """Check if any changed file matches rule's regex. Returns bool."""
    pass


def get_rule_reviewers(rule):
    """Extract reviewers from rule's add-reviewers action. Returns set of (target, is_group) tuples."""
    pass


def resolve_reviewers(reviewers, rules_data, group_prefix):
    """Convert to GitHub usernames, prefix groups. Returns set of strings."""
    pass


if __name__ == "__main__":
    main()
