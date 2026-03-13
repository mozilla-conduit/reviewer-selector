"""Tests for reviewer_selector.py"""

import json
import subprocess
import sys
import tempfile


from reviewer_selector import (
    parse_diff,
    collect_reviewers,
    matches_repo_filter,
    matches_files,
    get_rule_reviewers,
    resolve_reviewers,
)

MAIN_SCRIPT = "src/reviewer_selector.py"

# --- Test data ---

SAMPLE_RULES_DATA = {
    "rules": [
        {
            "id": "H1",
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"\.ftl$",
                }
            ],
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [{"target": "fluent-reviewers", "is_group": True}],
                }
            ],
        },
        {
            "id": "H2",
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"^remote/",
                },
                {
                    "type": "repository",
                    "operator": "is-any-of",
                    "value": ["mozilla-central"],
                },
            ],
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [{"target": "jsmith", "is_group": False}],
                }
            ],
        },
        {
            "id": "H3",
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"^testing/",
                },
            ],
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [
                        {"target": "test-reviewers", "is_group": True},
                        {"target": "jdoe", "is_group": False},
                    ],
                }
            ],
        },
    ],
    "groups": {
        "fluent-reviewers": {"members": ["alice", "bob"]},
        "test-reviewers": {"members": ["charlie"]},
    },
    "github_users": {
        "alice": {"username": "alice-gh"},
        "bob": {"username": "bob-gh"},
        "charlie": {"username": "charlie-gh"},
        "jsmith": {"username": "jsmith-gh"},
        "jdoe": {"username": "jdoe-gh"},
    },
    "unresolved_users": [],
}

SAMPLE_DIFF = """\
diff --git a/locales/en/messages.ftl b/locales/en/messages.ftl
index 1234567..abcdefg 100644
--- a/locales/en/messages.ftl
+++ b/locales/en/messages.ftl
@@ -1,3 +1,4 @@
+new-message = Hello
 old-message = World
"""


# --- parse_diff tests ---


class TestParseDiff:
    def test_extracts_file_paths(self):
        files = parse_diff(SAMPLE_DIFF)
        assert list(files) == ["locales/en/messages.ftl"]

    def test_handles_multiple_files(self):
        diff = """\
diff --git a/file1.py b/file1.py
index 1234567..abcdefg 100644
--- a/file1.py
+++ b/file1.py
@@ -1 +1 @@
-old
+new
diff --git a/dir/file2.js b/dir/file2.js
index 1234567..abcdefg 100644
--- a/dir/file2.js
+++ b/dir/file2.js
@@ -1 +1 @@
-old
+new
"""
        files = parse_diff(diff)
        assert "file1.py" in files
        assert "dir/file2.js" in files

    def test_empty_diff(self):
        files = parse_diff("")
        assert files == []


# --- matches_repo_filter tests ---


class TestMatchesRepoFilter:
    def test_no_repo_flag_always_matches(self):
        rule = {"conditions": [{"type": "repository", "value": ["mozilla-central"]}]}
        assert matches_repo_filter(rule, []) is True

    def test_rule_without_repo_condition_matches(self):
        rule = {"conditions": [{"type": "differential-affected-files", "value": ".*"}]}
        assert matches_repo_filter(rule, ["mozilla-central"]) is True

    def test_matching_repo(self):
        rule = {
            "conditions": [
                {
                    "type": "repository",
                    "operator": "is-any-of",
                    "value": ["mozilla-central"],
                }
            ]
        }
        assert matches_repo_filter(rule, ["mozilla-central"]) is True

    def test_non_matching_repo(self):
        rule = {
            "conditions": [
                {
                    "type": "repository",
                    "operator": "is-any-of",
                    "value": ["comm-central"],
                }
            ]
        }
        assert matches_repo_filter(rule, ["mozilla-central"]) is False

    def test_multiple_repos_in_rule(self):
        rule = {
            "conditions": [
                {
                    "type": "repository",
                    "operator": "is-any-of",
                    "value": ["mozilla-central", "autoland"],
                }
            ]
        }
        assert matches_repo_filter(rule, ["autoland"]) is True

    def test_multiple_repos_in_flag(self):
        rule = {
            "conditions": [
                {
                    "type": "repository",
                    "operator": "is-any-of",
                    "value": ["mozilla-central"],
                }
            ]
        }
        assert matches_repo_filter(rule, ["autoland", "mozilla-central"]) is True


# --- matches_files tests ---


class TestMatchesFiles:
    def test_matching_regex(self):
        rule = {
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"\.py$",
                }
            ]
        }
        assert matches_files(rule, ["src/main.py"]) is True

    def test_non_matching_regex(self):
        rule = {
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"\.py$",
                }
            ]
        }
        assert matches_files(rule, ["src/main.js"]) is False

    def test_any_file_matches(self):
        rule = {
            "conditions": [
                {
                    "type": "differential-affected-files",
                    "operator": "matches-regexp",
                    "value": r"\.py$",
                }
            ]
        }
        assert matches_files(rule, ["README.md", "src/main.py", "config.json"]) is True

    def test_no_affected_files_condition(self):
        rule = {"conditions": [{"type": "repository", "value": ["mozilla-central"]}]}
        assert matches_files(rule, ["anything.txt"]) is False


# --- get_rule_reviewers tests ---


class TestGetRuleReviewers:
    def test_extracts_reviewers(self):
        rule = {
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [{"target": "jsmith", "is_group": False}],
                }
            ]
        }
        reviewers = get_rule_reviewers(rule)
        assert ("jsmith", False) in reviewers

    def test_extracts_groups(self):
        rule = {
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [{"target": "my-group", "is_group": True}],
                }
            ]
        }
        reviewers = get_rule_reviewers(rule)
        assert ("my-group", True) in reviewers

    def test_multiple_reviewers(self):
        rule = {
            "actions": [
                {
                    "type": "add-reviewers",
                    "reviewers": [
                        {"target": "user1", "is_group": False},
                        {"target": "group1", "is_group": True},
                    ],
                }
            ]
        }
        reviewers = get_rule_reviewers(rule)
        assert len(reviewers) == 2

    def test_ignores_non_reviewer_actions(self):
        rule = {
            "actions": [
                {"type": "send-email", "target": "someone"},
                {
                    "type": "add-reviewers",
                    "reviewers": [{"target": "jsmith", "is_group": False}],
                },
            ]
        }
        reviewers = get_rule_reviewers(rule)
        assert len(reviewers) == 1


# --- collect_reviewers tests ---


class TestCollectReviewers:
    def test_collects_from_matching_rules(self):
        files = ["locales/en/messages.ftl"]
        reviewers = collect_reviewers(SAMPLE_RULES_DATA, files, [])
        assert ("fluent-reviewers", True) in reviewers

    def test_respects_repo_filter(self):
        files = ["remote/protocol.js"]
        reviewers = collect_reviewers(SAMPLE_RULES_DATA, files, ["mozilla-central"])
        assert ("jsmith", False) in reviewers

    def test_excludes_non_matching_repo(self):
        files = ["remote/protocol.js"]
        reviewers = collect_reviewers(SAMPLE_RULES_DATA, files, ["comm-central"])
        assert ("jsmith", False) not in reviewers

    def test_deduplicates_reviewers(self):
        # If same reviewer appears in multiple rules, should only appear once
        files = ["testing/test.ftl"]  # matches H1 (.ftl) and H3 (testing/)
        reviewers = collect_reviewers(SAMPLE_RULES_DATA, files, [])
        # Count occurrences
        assert len([r for r in reviewers if r[0] == "fluent-reviewers"]) <= 1


# --- resolve_reviewers tests ---


class TestResolveReviewers:
    def test_resolves_user_to_github(self):
        reviewers = {("jsmith", False)}
        resolved = resolve_reviewers(reviewers, SAMPLE_RULES_DATA, "#")
        assert "jsmith-gh" in resolved

    def test_prefixes_groups(self):
        reviewers = {("fluent-reviewers", True)}
        resolved = resolve_reviewers(reviewers, SAMPLE_RULES_DATA, "#")
        assert "#fluent-reviewers" in resolved

    def test_custom_group_prefix(self):
        reviewers = {("fluent-reviewers", True)}
        resolved = resolve_reviewers(reviewers, SAMPLE_RULES_DATA, "@")
        assert "@fluent-reviewers" in resolved

    def test_skips_unresolved_users(self):
        reviewers = {("unknown-user", False)}
        resolved = resolve_reviewers(reviewers, SAMPLE_RULES_DATA, "#")
        assert len(resolved) == 0

    def test_mixed_users_and_groups(self):
        reviewers = {("jsmith", False), ("fluent-reviewers", True)}
        resolved = resolve_reviewers(reviewers, SAMPLE_RULES_DATA, "#")
        assert "jsmith-gh" in resolved
        assert "#fluent-reviewers" in resolved


# --- CLI integration tests ---


class TestCLI:
    def test_full_flow(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_RULES_DATA, f)
            rules_path = f.name

        result = subprocess.run(
            [sys.executable, MAIN_SCRIPT, rules_path],
            input=SAMPLE_DIFF,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "#fluent-reviewers" in result.stdout

    def test_repo_filter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_RULES_DATA, f)
            rules_path = f.name

        diff = """\
diff --git a/remote/protocol.js b/remote/protocol.js
index 1234567..abcdefg 100644
--- a/remote/protocol.js
+++ b/remote/protocol.js
@@ -1 +1 @@
-old
+new
"""
        result = subprocess.run(
            [
                sys.executable,
                MAIN_SCRIPT,
                rules_path,
                "--repo",
                "mozilla-central",
            ],
            input=diff,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "jsmith-gh" in result.stdout

    def test_group_prefix(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_RULES_DATA, f)
            rules_path = f.name

        result = subprocess.run(
            [sys.executable, MAIN_SCRIPT, rules_path, "--group-prefix", "@"],
            input=SAMPLE_DIFF,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "@fluent-reviewers" in result.stdout
