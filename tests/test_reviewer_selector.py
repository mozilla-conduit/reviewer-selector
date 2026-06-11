"""Tests for reviewer_selector.py"""

from unittest import mock

from reviewer_selector import (
    Patch,
    Rules,
    UserResolver,
)


# --- Patch.get_changed_files tests ---


class TestParseDiff:
    def test_extracts_file_paths(self, sample_diff: str):
        patch = Patch(sample_diff)
        files = patch.get_changed_files()
        assert list(files) == ["locales/en/messages.ftl"]

    def test_handles_multiple_files(self, sample_diff_multiple_files: str):
        patch = Patch(sample_diff_multiple_files)
        files = patch.get_changed_files()
        assert "file1.py" in files
        assert "dir/file2.js" in files

    def test_empty_diff(self):
        patch = Patch("")
        files = patch.get_changed_files()
        assert files == []


# --- Rules.rule_matches_repos tests ---


class TestMatchesRepoFilter:
    def test_no_repo_flag_always_matches(self):
        rule = {
            "id": "test_no_repo_flag_always_matches",
            "name": "test_no_repo_flag_always_matches",
            "conditions": [{"type": "repository", "value": ["mozilla-central"]}],
        }
        assert Rules.rule_matches_repos(rule, []) is True

    def test_rule_without_repo_condition_matches(self):
        rule = {
            "id": "test_rule_without_repo_condition_matches",
            "name": "test_rule_without_repo_condition_matches",
            "conditions": [{"type": "differential-affected-files", "value": ".*"}],
        }
        assert Rules.rule_matches_repos(rule, ["mozilla-central"]) is True

    def test_matching_repos(self):
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

    def test_non_matching_repo(self):
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

    def test_multiple_repos_in_rule(self):
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

    def test_multiple_repos_in_flag(self):
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


class TestMatchesFiles:
    def test_matching_regex(self):
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

    def test_non_matching_regex(self):
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

    def test_any_file_matches(self):
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

    def test_no_affected_files_condition(self):
        rule = {
            "id": "test_no_affected_files_condition",
            "name": "test_no_affected_files_condition",
            "conditions": [{"type": "repository", "value": ["mozilla-central"]}],
        }
        assert Rules.rule_matches_files(rule, ["anything.txt"]) is False


# --- Rules.get_rule_reviewers tests ---


class TestGetRuleReviewers:
    def test_extracts_reviewers(self):
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
        assert ("jsmith", False) in reviewers

    def test_extracts_groups(self):
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
        assert ("my-group", True) in reviewers

    def test_multiple_reviewers(self):
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

    def test_ignores_non_reviewer_actions(self):
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


class TestCollectReviewers:
    def test_collects_from_matching_rules(self, sample_rules_data: dict):
        rules = Rules(sample_rules_data)
        patch = mock.MagicMock()
        patch.get_changed_files = lambda: ["locales/en/messages.ftl"]

        reviewers = rules.collect_reviewers(patch, [])

        assert ("fluent-reviewers", True) in reviewers
        assert ("/ent:fluent-reviewers", True) in reviewers

    def test_respects_repo_filter(self, sample_rules_data: dict):
        rules = Rules(sample_rules_data)
        patch = mock.MagicMock()
        patch.get_changed_files = lambda: ["remote/protocol.js"]

        reviewers = rules.collect_reviewers(patch, ["mozilla-central"])

        assert ("jsmith", False) in reviewers

    def test_excludes_non_matching_repo(self, sample_rules_data: dict):
        rules = Rules(sample_rules_data)
        patch = mock.MagicMock()
        patch.get_changed_files = lambda: ["remote/protocol.js"]

        reviewers = rules.collect_reviewers(patch, ["comm-central"])

        assert ("jsmith", False) not in reviewers

    def test_deduplicates_reviewers(self, sample_rules_data: dict):
        # If same reviewer appears in multiple rules, should only appear once
        rules = Rules(sample_rules_data)
        patch = mock.MagicMock()
        patch.get_changed_files = lambda: [
            "testing/test.ftl"
        ]  # matches H1 (.ftl) and H3 (testing/)

        reviewers = rules.collect_reviewers(patch, [])

        # Count occurrences
        assert len([r for r in reviewers if r[0] == "fluent-reviewers"]) <= 1


# --- UserResolver.resolve_reviewers tests ---


class TestResolveReviewers:
    def test_resolves_user_to_github(self, sample_rules_data: dict):
        resolver = UserResolver(sample_rules_data["github_users"], "#")
        reviewers = {("jsmith", False)}

        resolved = resolver.resolve_reviewers(reviewers)

        assert "jsmith-gh" in resolved

    def test_prefixes_groups(self, sample_rules_data: dict):
        resolver = UserResolver(sample_rules_data["github_users"], "#")
        reviewers = {("fluent-reviewers", True), ("/ent:fluent-reviewers", True)}

        resolved = resolver.resolve_reviewers(reviewers)

        assert "#fluent-reviewers" in resolved
        assert "/ent:fluent-reviewers" in resolved

    def test_custom_group_prefix(self, sample_rules_data: dict):
        resolver = UserResolver(sample_rules_data["github_users"], "@")
        reviewers = {("fluent-reviewers", True), ("/ent:fluent-reviewers", True)}

        resolved = resolver.resolve_reviewers(reviewers)

        assert "@fluent-reviewers" in resolved
        assert "/ent:fluent-reviewers" in resolved

    def test_skips_unresolved_users(self, sample_rules_data: dict):
        resolver = UserResolver(sample_rules_data["github_users"], "#")
        reviewers = {("unknown-user", False)}

        resolved = resolver.resolve_reviewers(reviewers)

        assert len(resolved) == 0

    def test_mixed_users_and_groups(self, sample_rules_data: dict):
        resolver = UserResolver(sample_rules_data["github_users"], "#")
        reviewers = {("jsmith", False), ("fluent-reviewers", True)}

        resolved = resolver.resolve_reviewers(reviewers)

        assert "jsmith-gh" in resolved
        assert "#fluent-reviewers" in resolved
