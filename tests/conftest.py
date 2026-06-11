from typing import Any

import pytest

SAMPLE_DIFF = """\
diff --git a/locales/en/messages.ftl b/locales/en/messages.ftl
index 1234567..abcdefg 100644
--- a/locales/en/messages.ftl
+++ b/locales/en/messages.ftl
@@ -1,3 +1,4 @@
+new-message = Hello
 old-message = World
"""


@pytest.fixture
def sample_diff() -> str:
    return SAMPLE_DIFF


SAMPLE_DIFF_MULTIPLE_FILES = """\
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


@pytest.fixture
def sample_diff_multiple_files() -> str:
    return SAMPLE_DIFF_MULTIPLE_FILES


SAMPLE_DIFF_REMOTE = """\
diff --git a/remote/protocol.js b/remote/protocol.js
index 1234567..abcdefg 100644
--- a/remote/protocol.js
+++ b/remote/protocol.js
@@ -1 +1 @@
-old
+new
"""


@pytest.fixture
def sample_diff_remote() -> str:
    """A diff changing a file in the remote/ subdirectory."""
    return SAMPLE_DIFF_REMOTE


@pytest.fixture
def sample_rules_data() -> dict[str, Any]:
    return {
        "rules": [
            {
                "id": "H1",
                "name": "H1",
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
                "name": "H2",
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
                "name": "H3",
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
            {
                "id": "H4",
                "name": "H4",
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
                        "reviewers": [
                            {"target": "/ent:fluent-reviewers", "is_group": True}
                        ],
                    }
                ],
            },
        ],
        "groups": {
            "fluent-reviewers": {"members": ["alice", "bob"]},
            "test-reviewers": {"members": ["charlie"]},
            "/ent:fluent-reviewers": {"members": ["bob"]},
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
