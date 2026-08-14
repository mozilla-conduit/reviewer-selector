from unittest import mock

import pytest

from reviewer_selector.review import Reviewer
from reviewer_selector.rules import Rules, RulesData


@pytest.mark.parametrize(
    "rules",
    (
        ({}),
        (
            {
                "rules": {
                    "id": "test_no_repo_flag_always_matches",
                    "name": "test_no_repo_flag_always_matches",
                    "conditions": [
                        {"type": "repository", "value": ["mozilla-central"]}
                    ],
                }
            }
        ),
    ),
)
def test_rules_length(rules: RulesData):
    assert len(Rules(rules)) == len(rules), (
        "Length of Rules doesn't match underlying data"
    )
    assert bool(Rules(rules)) == bool(rules), (
        "Truthyness of Rules doesn't match underlying data"
    )


# --- Rules.rule_matches_repos tests ---


def test_rule_no_repo_flag_always_matches():
    rule = {
        "id": "test_no_repo_flag_always_matches",
        "name": "test_no_repo_flag_always_matches",
        "conditions": [{"type": "repository", "value": ["mozilla-central"]}],
    }
    assert Rules.rule_matches_repos(rule, []) is True


def test_rule_without_repo_condition_matches():
    rule = {
        "id": "test_rule_without_repo_condition_matches",
        "name": "test_rule_without_repo_condition_matches",
        "conditions": [{"type": "differential-affected-files", "value": ".*"}],
    }
    assert Rules.rule_matches_repos(rule, ["mozilla-central"]) is True


def test_rule_matching_repos():
    rule = {
        "id": "test_matching_repos",
        "name": "test_matching_repos",
        "conditions": [
            {
                "type": "repository",
                "operator": "is-any-of",
                "value": ["mozilla-central"],
            }
        ],
    }
    assert Rules.rule_matches_repos(rule, ["mozilla-central"]) is True


def test_rule_non_matching_repo():
    rule = {
        "id": "test_non_matching_repo",
        "name": "test_non_matching_repo",
        "conditions": [
            {
                "type": "repository",
                "operator": "is-any-of",
                "value": ["comm-central"],
            }
        ],
    }
    assert Rules.rule_matches_repos(rule, ["mozilla-central"]) is False


def test_rule_multiple_repos():
    rule = {
        "id": "test_multiple_repos_in_rule",
        "name": "test_multiple_repos_in_rule",
        "conditions": [
            {
                "type": "repository",
                "operator": "is-any-of",
                "value": ["mozilla-central", "autoland"],
            }
        ],
    }
    assert Rules.rule_matches_repos(rule, ["autoland"]) is True


def test_rule_multiple_repos_in_flag():
    rule = {
        "id": "test_multiple_repos_in_flag",
        "name": "test_multiple_repos_in_flag",
        "conditions": [
            {
                "type": "repository",
                "operator": "is-any-of",
                "value": ["mozilla-central"],
            }
        ],
    }
    assert Rules.rule_matches_repos(rule, ["autoland", "mozilla-central"]) is True


# --- Rules.rule_matches_files tests ---


def test_rule_matching_regex():
    rule = {
        "id": "test_matching_regex",
        "name": "test_matching_regex",
        "conditions": [
            {
                "type": "differential-affected-files",
                "operator": "matches-regexp",
                "value": r"\.py$",
            }
        ],
    }
    assert Rules.rule_matches_files(rule, ["src/main.py"]) is True


def test_rule_non_matching_regex():
    rule = {
        "id": "test_non_matching_regex",
        "name": "test_non_matching_regex",
        "conditions": [
            {
                "type": "differential-affected-files",
                "operator": "matches-regexp",
                "value": r"\.py$",
            }
        ],
    }
    assert Rules.rule_matches_files(rule, ["src/main.js"]) is False


def test_rule_any_file_matches():
    rule = {
        "id": "test_any_file_matches",
        "name": "test_any_file_matches",
        "conditions": [
            {
                "type": "differential-affected-files",
                "operator": "matches-regexp",
                "value": r"\.py$",
            }
        ],
    }
    assert (
        Rules.rule_matches_files(rule, ["README.md", "src/main.py", "config.json"])
        is True
    )


def test_rule_no_affected_files_condition():
    rule = {
        "id": "test_no_affected_files_condition",
        "name": "test_no_affected_files_condition",
        "conditions": [{"type": "repository", "value": ["mozilla-central"]}],
    }
    assert Rules.rule_matches_files(rule, ["anything.txt"]) is False


# --- Rules.get_rule_reviewers tests ---


def test_rule_extracts_reviewers():
    rule = {
        "id": "test_extracts_reviewers",
        "name": "test_extracts_reviewers",
        "actions": [
            {
                "type": "add-reviewers",
                "reviewers": [{"target": "jsmith", "is_group": False}],
            }
        ],
    }
    reviewers = Rules.get_rule_reviewers(rule)
    assert Reviewer("jsmith", False) in reviewers


def test_rule_extracts_groups():
    rule = {
        "id": "test_extracts_groups",
        "name": "test_extracts_groups",
        "actions": [
            {
                "type": "add-reviewers",
                "reviewers": [{"target": "my-group", "is_group": True}],
            }
        ],
    }
    reviewers = Rules.get_rule_reviewers(rule)
    assert Reviewer("my-group", True) in reviewers


def test_rule_multiple_reviewers():
    rule = {
        "id": "test_multiple_reviewers",
        "name": "test_multiple_reviewers",
        "actions": [
            {
                "type": "add-reviewers",
                "reviewers": [
                    {"target": "user1", "is_group": False},
                    {"target": "group1", "is_group": True},
                ],
            }
        ],
    }
    reviewers = Rules.get_rule_reviewers(rule)
    assert len(reviewers) == 2


def test_rule_ignores_non_reviewer_actions():
    rule = {
        "id": "test_ignores_non_reviewer_actions",
        "name": "test_ignores_non_reviewer_actions",
        "actions": [
            {"type": "send-email", "target": "someone"},
            {
                "type": "add-reviewers",
                "reviewers": [{"target": "jsmith", "is_group": False}],
            },
        ],
    }
    reviewers = Rules.get_rule_reviewers(rule)
    assert len(reviewers) == 1


# --- Rules.collect_reviewers tests ---


def test_rule_collects_from_matching_rules(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: ["locales/en/messages.ftl"]

    reviewers = rules.collect_reviewers(patch, [])

    assert Reviewer("fluent-reviewers", True) in reviewers
    assert Reviewer("ent:fluent-reviewers", True) in reviewers


def test_rule_respects_repo_filter(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: ["remote/protocol.js"]

    reviewers = rules.collect_reviewers(patch, ["mozilla-central"])

    assert Reviewer("jsmith", False) in reviewers


def test_rule_excludes_non_matching_repo(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: ["remote/protocol.js"]

    reviewers = rules.collect_reviewers(patch, ["comm-central"])

    assert Reviewer("jsmith", False) not in reviewers


def test_rule_deduplicates_reviewers(sample_rules_data: dict):
    # If same reviewer appears in multiple rules, should only appear once
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: [
        "testing/test.ftl"
    ]  # matches H1 (.ftl) and H3 (testing/)

    reviewers = rules.collect_reviewers(patch, [])

    # Count occurrences
    assert len([r for r in reviewers if r.name == "fluent-reviewers"]) <= 1
