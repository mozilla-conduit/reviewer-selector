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
    assert Rules.rule_matches_repos(rule, iter(["mozilla-central"])) is True


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
    assert Rules.rule_matches_repos(rule, iter(["mozilla-central"])) is True


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
    assert Rules.rule_matches_repos(rule, iter(["mozilla-central"])) is False


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
    assert Rules.rule_matches_repos(rule, iter(["autoland"])) is True


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
    assert Rules.rule_matches_repos(rule, iter(["autoland", "mozilla-central"])) is True


# --- Rules.rule_matches_files tests ---

rule_py = {
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

rule_h498 = {
    "id": "H498",
    "name": "Needs review from #layout-reviewers (main)",
    "author": "dkl_admin",
    "status": "active",
    "type": "differential-revision",
    "conditions": [
        {"type": "repository", "operator": "is-any-of", "value": ["firefox-autoland"]},
        {
            "type": "differential-revision-status",
            "operator": "is-not-any-of",
            "value": ["Closed", "Abandoned", "Draft", "Changes Planned"],
        },
        {
            "type": "differential-affected-files",
            "operator": "matches-regexp",
            "value": "^/layout/(?!style/|svg/)",
        },
    ],
    "actions": [
        {
            "type": "add-reviewers",
            "reviewers": [
                {"target": "layout-reviewers", "blocking": False, "is_group": True}
            ],
        }
    ],
}


@pytest.mark.parametrize(
    "rule,files",
    (
        (
            rule_py,
            ["/src/main.py"],
        ),
        (
            rule_h498,
            ["/layout/printing/nsPrintJob.cpp"],
        ),
    ),
)
def test_rule_matching_regex(rule: dict, files: list[str]):
    assert Rules.rule_matches_files(rule, files), (
        f"Rule {rule['id']} should have matched for {files}"
    )


@pytest.mark.parametrize(
    "rule,files",
    (
        (
            rule_py,
            ["/src/main.js"],
        ),
    ),
)
def test_rule_non_matching_regex(rule: dict, files: list[str]):
    assert not Rules.rule_matches_files(rule, files), (
        f"Rule {rule['id']} should NOT have matched for {files}"
    )


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
        Rules.rule_matches_files(rule, iter(["README.md", "src/main.py", "config.json"]))
        is True
    )


def test_rule_no_affected_files_condition():
    rule = {
        "id": "test_no_affected_files_condition",
        "name": "test_no_affected_files_condition",
        "conditions": [{"type": "repository", "value": iter(["mozilla-central"])}],
    }
    assert Rules.rule_matches_files(rule, iter(["anything.txt"])) is False


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
    assert Reviewer("jsmith") in reviewers


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
    assert Reviewer("my-group", is_group=True) in reviewers


def test_rule_extracts_blocking():
    rule = {
        "id": "test_extracts_blocking",
        "name": "test_extracts_blocking",
        "actions": [
            {
                "type": "add-reviewers",
                "reviewers": [{"target": "my-group", "blocking": True}],
            }
        ],
    }
    reviewers = Rules.get_rule_reviewers(rule)
    assert Reviewer("my-group", blocking=True) in reviewers


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
    assert len(list(reviewers)) == 2


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
    assert len(list(reviewers)) == 1


# --- Rules.collect_reviewers tests ---


def test_rule_collects_from_matching_rules(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: iter(["locales/en/messages.ftl"])

    reviewers = list(rules.collect_reviewers(patch, []))

    assert Reviewer("fluent-reviewers", is_group=True) in reviewers
    assert Reviewer("ent:fluent-reviewers", is_group=True) in reviewers


def test_rule_respects_repo_filter(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: iter(["remote/protocol.js"])

    reviewers = list(rules.collect_reviewers(patch, iter(["mozilla-central"])))

    assert Reviewer("jsmith") in reviewers


def test_rule_excludes_non_matching_repo(sample_rules_data: dict):
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: list(["remote/protocol.js"])

    reviewers = list(rules.collect_reviewers(patch, ["comm-central"]))

    assert Reviewer("jsmith") not in reviewers


def test_rule_deduplicates_reviewers(sample_rules_data: dict):
    # If same reviewer appears in multiple rules, should only appear once
    rules = Rules(sample_rules_data)
    patch = mock.MagicMock()
    patch.get_changed_files = lambda: iter([
        "testing/test.ftl"
    ])  # matches H1 (.ftl) and H3 (testing/)

    reviewers = list(rules.collect_reviewers(patch, []))

    # Count occurrences
    assert len([r for r in reviewers if r.name == "fluent-reviewers"]) <= 1
