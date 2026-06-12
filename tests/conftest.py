from textwrap import dedent
from typing import Any

import pytest
from requests_mock import Mocker

#
# DIFF FIXTURES
#


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


#
# GITHUB FIXTURES
#


@pytest.fixture
def github_api_response_pull_request() -> str:
    return dedent("""\
    {
      "url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18",
      "id": 3801479461,
      "node_id": "PR_kwDORk2QWs7ilfkl",
      "html_url": "https://github.com/mozilla-conduit/reviewer-selector/pull/18",
      "diff_url": "https://github.com/mozilla-conduit/reviewer-selector/pull/18.diff",
      "patch_url": "https://github.com/mozilla-conduit/reviewer-selector/pull/18.patch",
      "issue_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/18",
      "number": 18,
      "state": "open",
      "locked": false,
      "title": "reviewer_selector: add GitHub Site support (bug 2030600)",
      "user": {
        "login": "shtrom",
        "id": 160280,
        "node_id": "MDQ6VXNlcjE2MDI4MA==",
        "avatar_url": "https://avatars.githubusercontent.com/u/160280?v=4",
        "gravatar_id": "",
        "url": "https://api.github.com/users/shtrom",
        "html_url": "https://github.com/shtrom",
        "followers_url": "https://api.github.com/users/shtrom/followers",
        "following_url": "https://api.github.com/users/shtrom/following{/other_user}",
        "gists_url": "https://api.github.com/users/shtrom/gists{/gist_id}",
        "starred_url": "https://api.github.com/users/shtrom/starred{/owner}{/repo}",
        "subscriptions_url": "https://api.github.com/users/shtrom/subscriptions",
        "organizations_url": "https://api.github.com/users/shtrom/orgs",
        "repos_url": "https://api.github.com/users/shtrom/repos",
        "events_url": "https://api.github.com/users/shtrom/events{/privacy}",
        "received_events_url": "https://api.github.com/users/shtrom/received_events",
        "type": "User",
        "user_view_type": "public",
        "site_admin": false
      },
      "body": null,
      "created_at": "2026-06-04T08:01:22Z",
      "updated_at": "2026-06-10T05:18:28Z",
      "closed_at": null,
      "merged_at": null,
      "merge_commit_sha": "cc4d7465a33b2bec63827d0f1bab942543f37ab4",
      "assignees": [

      ],
      "requested_reviewers": [

      ],
      "requested_teams": [

      ],
      "labels": [

      ],
      "milestone": null,
      "draft": true,
      "commits_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/commits",
      "review_comments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/comments",
      "review_comment_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/comments{/number}",
      "comments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/18/comments",
      "statuses_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/statuses/5c9487af01e52713fc6cb60b4177ce407ed4fe7f",
      "head": {
        "label": "mozilla-conduit:bug2030600/github-parameters-simplification",
        "ref": "bug2030600/github-parameters-simplification",
        "sha": "5c9487af01e52713fc6cb60b4177ce407ed4fe7f",
        "user": {
          "login": "mozilla-conduit",
          "id": 25333391,
          "node_id": "MDEyOk9yZ2FuaXphdGlvbjI1MzMzMzkx",
          "avatar_url": "https://avatars.githubusercontent.com/u/25333391?v=4",
          "gravatar_id": "",
          "url": "https://api.github.com/users/mozilla-conduit",
          "html_url": "https://github.com/mozilla-conduit",
          "followers_url": "https://api.github.com/users/mozilla-conduit/followers",
          "following_url": "https://api.github.com/users/mozilla-conduit/following{/other_user}",
          "gists_url": "https://api.github.com/users/mozilla-conduit/gists{/gist_id}",
          "starred_url": "https://api.github.com/users/mozilla-conduit/starred{/owner}{/repo}",
          "subscriptions_url": "https://api.github.com/users/mozilla-conduit/subscriptions",
          "organizations_url": "https://api.github.com/users/mozilla-conduit/orgs",
          "repos_url": "https://api.github.com/users/mozilla-conduit/repos",
          "events_url": "https://api.github.com/users/mozilla-conduit/events{/privacy}",
          "received_events_url": "https://api.github.com/users/mozilla-conduit/received_events",
          "type": "Organization",
          "user_view_type": "public",
          "site_admin": false
        },
        "repo": {
          "id": 1179488346,
          "node_id": "R_kgDORk2QWg",
          "name": "reviewer-selector",
          "full_name": "mozilla-conduit/reviewer-selector",
          "private": false,
          "owner": {
            "login": "mozilla-conduit",
            "id": 25333391,
            "node_id": "MDEyOk9yZ2FuaXphdGlvbjI1MzMzMzkx",
            "avatar_url": "https://avatars.githubusercontent.com/u/25333391?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/mozilla-conduit",
            "html_url": "https://github.com/mozilla-conduit",
            "followers_url": "https://api.github.com/users/mozilla-conduit/followers",
            "following_url": "https://api.github.com/users/mozilla-conduit/following{/other_user}",
            "gists_url": "https://api.github.com/users/mozilla-conduit/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/mozilla-conduit/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/mozilla-conduit/subscriptions",
            "organizations_url": "https://api.github.com/users/mozilla-conduit/orgs",
            "repos_url": "https://api.github.com/users/mozilla-conduit/repos",
            "events_url": "https://api.github.com/users/mozilla-conduit/events{/privacy}",
            "received_events_url": "https://api.github.com/users/mozilla-conduit/received_events",
            "type": "Organization",
            "user_view_type": "public",
            "site_admin": false
          },
          "html_url": "https://github.com/mozilla-conduit/reviewer-selector",
          "description": "Select reviewers based on a diff and a set of rules",
          "fork": false,
          "url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector",
          "forks_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/forks",
          "keys_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/keys{/key_id}",
          "collaborators_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/collaborators{/collaborator}",
          "teams_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/teams",
          "hooks_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/hooks",
          "issue_events_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/events{/number}",
          "events_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/events",
          "assignees_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/assignees{/user}",
          "branches_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/branches{/branch}",
          "tags_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/tags",
          "blobs_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/blobs{/sha}",
          "git_tags_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/tags{/sha}",
          "git_refs_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/refs{/sha}",
          "trees_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/trees{/sha}",
          "statuses_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/statuses/{sha}",
          "languages_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/languages",
          "stargazers_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/stargazers",
          "contributors_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/contributors",
          "subscribers_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/subscribers",
          "subscription_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/subscription",
          "commits_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/commits{/sha}",
          "git_commits_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/commits{/sha}",
          "comments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/comments{/number}",
          "issue_comment_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/comments{/number}",
          "contents_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/contents/{+path}",
          "compare_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/compare/{base}...{head}",
          "merges_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/merges",
          "archive_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/{archive_format}{/ref}",
          "downloads_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/downloads",
          "issues_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues{/number}",
          "pulls_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls{/number}",
          "milestones_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/milestones{/number}",
          "notifications_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/notifications{?since,all,participating}",
          "labels_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/labels{/name}",
          "releases_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/releases{/id}",
          "deployments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/deployments",
          "created_at": "2026-03-12T04:31:36Z",
          "updated_at": "2026-06-10T01:03:33Z",
          "pushed_at": "2026-06-10T07:21:44Z",
          "git_url": "git://github.com/mozilla-conduit/reviewer-selector.git",
          "ssh_url": "git@github.com:mozilla-conduit/reviewer-selector.git",
          "clone_url": "https://github.com/mozilla-conduit/reviewer-selector.git",
          "svn_url": "https://github.com/mozilla-conduit/reviewer-selector",
          "homepage": "",
          "size": 488,
          "stargazers_count": 1,
          "watchers_count": 1,
          "language": "Python",
          "has_issues": false,
          "has_projects": false,
          "has_downloads": true,
          "has_wiki": false,
          "has_pages": false,
          "has_discussions": false,
          "forks_count": 2,
          "mirror_url": null,
          "archived": false,
          "disabled": false,
          "open_issues_count": 3,
          "license": {
            "key": "mpl-2.0",
            "name": "Mozilla Public License 2.0",
            "spdx_id": "MPL-2.0",
            "url": "https://api.github.com/licenses/mpl-2.0",
            "node_id": "MDc6TGljZW5zZTE0"
          },
          "allow_forking": true,
          "is_template": false,
          "web_commit_signoff_required": false,
          "has_pull_requests": true,
          "pull_request_creation_policy": "all",
          "topics": [

          ],
          "visibility": "public",
          "forks": 2,
          "open_issues": 3,
          "watchers": 1,
          "default_branch": "main"
        }
      },
      "base": {
        "label": "mozilla-conduit:main",
        "ref": "main",
        "sha": "1827bbb5e31c8a1b5f57e68fb5a65e85d9808b6e",
        "user": {
          "login": "mozilla-conduit",
          "id": 25333391,
          "node_id": "MDEyOk9yZ2FuaXphdGlvbjI1MzMzMzkx",
          "avatar_url": "https://avatars.githubusercontent.com/u/25333391?v=4",
          "gravatar_id": "",
          "url": "https://api.github.com/users/mozilla-conduit",
          "html_url": "https://github.com/mozilla-conduit",
          "followers_url": "https://api.github.com/users/mozilla-conduit/followers",
          "following_url": "https://api.github.com/users/mozilla-conduit/following{/other_user}",
          "gists_url": "https://api.github.com/users/mozilla-conduit/gists{/gist_id}",
          "starred_url": "https://api.github.com/users/mozilla-conduit/starred{/owner}{/repo}",
          "subscriptions_url": "https://api.github.com/users/mozilla-conduit/subscriptions",
          "organizations_url": "https://api.github.com/users/mozilla-conduit/orgs",
          "repos_url": "https://api.github.com/users/mozilla-conduit/repos",
          "events_url": "https://api.github.com/users/mozilla-conduit/events{/privacy}",
          "received_events_url": "https://api.github.com/users/mozilla-conduit/received_events",
          "type": "Organization",
          "user_view_type": "public",
          "site_admin": false
        },
        "repo": {
          "id": 1179488346,
          "node_id": "R_kgDORk2QWg",
          "name": "reviewer-selector",
          "full_name": "mozilla-conduit/reviewer-selector",
          "private": false,
          "owner": {
            "login": "mozilla-conduit",
            "id": 25333391,
            "node_id": "MDEyOk9yZ2FuaXphdGlvbjI1MzMzMzkx",
            "avatar_url": "https://avatars.githubusercontent.com/u/25333391?v=4",
            "gravatar_id": "",
            "url": "https://api.github.com/users/mozilla-conduit",
            "html_url": "https://github.com/mozilla-conduit",
            "followers_url": "https://api.github.com/users/mozilla-conduit/followers",
            "following_url": "https://api.github.com/users/mozilla-conduit/following{/other_user}",
            "gists_url": "https://api.github.com/users/mozilla-conduit/gists{/gist_id}",
            "starred_url": "https://api.github.com/users/mozilla-conduit/starred{/owner}{/repo}",
            "subscriptions_url": "https://api.github.com/users/mozilla-conduit/subscriptions",
            "organizations_url": "https://api.github.com/users/mozilla-conduit/orgs",
            "repos_url": "https://api.github.com/users/mozilla-conduit/repos",
            "events_url": "https://api.github.com/users/mozilla-conduit/events{/privacy}",
            "received_events_url": "https://api.github.com/users/mozilla-conduit/received_events",
            "type": "Organization",
            "user_view_type": "public",
            "site_admin": false
          },
          "html_url": "https://github.com/mozilla-conduit/reviewer-selector",
          "description": "Select reviewers based on a diff and a set of rules",
          "fork": false,
          "url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector",
          "forks_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/forks",
          "keys_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/keys{/key_id}",
          "collaborators_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/collaborators{/collaborator}",
          "teams_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/teams",
          "hooks_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/hooks",
          "issue_events_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/events{/number}",
          "events_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/events",
          "assignees_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/assignees{/user}",
          "branches_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/branches{/branch}",
          "tags_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/tags",
          "blobs_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/blobs{/sha}",
          "git_tags_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/tags{/sha}",
          "git_refs_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/refs{/sha}",
          "trees_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/trees{/sha}",
          "statuses_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/statuses/{sha}",
          "languages_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/languages",
          "stargazers_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/stargazers",
          "contributors_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/contributors",
          "subscribers_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/subscribers",
          "subscription_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/subscription",
          "commits_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/commits{/sha}",
          "git_commits_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/git/commits{/sha}",
          "comments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/comments{/number}",
          "issue_comment_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/comments{/number}",
          "contents_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/contents/{+path}",
          "compare_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/compare/{base}...{head}",
          "merges_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/merges",
          "archive_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/{archive_format}{/ref}",
          "downloads_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/downloads",
          "issues_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues{/number}",
          "pulls_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls{/number}",
          "milestones_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/milestones{/number}",
          "notifications_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/notifications{?since,all,participating}",
          "labels_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/labels{/name}",
          "releases_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/releases{/id}",
          "deployments_url": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/deployments",
          "created_at": "2026-03-12T04:31:36Z",
          "updated_at": "2026-06-10T01:03:33Z",
          "pushed_at": "2026-06-10T07:21:44Z",
          "git_url": "git://github.com/mozilla-conduit/reviewer-selector.git",
          "ssh_url": "git@github.com:mozilla-conduit/reviewer-selector.git",
          "clone_url": "https://github.com/mozilla-conduit/reviewer-selector.git",
          "svn_url": "https://github.com/mozilla-conduit/reviewer-selector",
          "homepage": "",
          "size": 488,
          "stargazers_count": 1,
          "watchers_count": 1,
          "language": "Python",
          "has_issues": false,
          "has_projects": false,
          "has_downloads": true,
          "has_wiki": false,
          "has_pages": false,
          "has_discussions": false,
          "forks_count": 2,
          "mirror_url": null,
          "archived": false,
          "disabled": false,
          "open_issues_count": 3,
          "license": {
            "key": "mpl-2.0",
            "name": "Mozilla Public License 2.0",
            "spdx_id": "MPL-2.0",
            "url": "https://api.github.com/licenses/mpl-2.0",
            "node_id": "MDc6TGljZW5zZTE0"
          },
          "allow_forking": true,
          "is_template": false,
          "web_commit_signoff_required": false,
          "has_pull_requests": true,
          "pull_request_creation_policy": "all",
          "topics": [

          ],
          "visibility": "public",
          "forks": 2,
          "open_issues": 3,
          "watchers": 1,
          "default_branch": "main"
        }
      },
      "_links": {
        "self": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18"
        },
        "html": {
          "href": "https://github.com/mozilla-conduit/reviewer-selector/pull/18"
        },
        "issue": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/18"
        },
        "comments": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/issues/18/comments"
        },
        "review_comments": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/comments"
        },
        "review_comment": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/comments{/number}"
        },
        "commits": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/commits"
        },
        "statuses": {
          "href": "https://api.github.com/repos/mozilla-conduit/reviewer-selector/statuses/5c9487af01e52713fc6cb60b4177ce407ed4fe7f"
        }
      },
      "author_association": "MEMBER",
      "auto_merge": null,
      "assignee": null,
      "active_lock_reason": null,
      "merged": false,
      "mergeable": true,
      "rebaseable": false,
      "mergeable_state": "clean",
      "merged_by": null,
      "comments": 0,
      "review_comments": 6,
      "maintainer_can_modify": false,
      "commits": 4,
      "additions": 132,
      "deletions": 21,
      "changed_files": 6
    }
    """)


@pytest.fixture
def mocked_github_request(github_api_response_pull_request: str) -> Mocker:
    mock = Mocker()
    mock.get(
        "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18",
        text=github_api_response_pull_request,
    )
    return mock


#
# RULES FIXTURES
#


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
