from collections.abc import Callable
from typing import Any

import pytest
import requests
import requests_mock

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


SAMPLE_PATCH = """\
From d633a65852a20879289e0e1f613b8efb5f9cc9be Mon Sep 17 00:00:00 2001
From: Olivier Mehani <omehani@mozilla.com>
Date: Tue, 14 Jul 2026 17:48:35 +1000
Subject: [PATCH] patch: support parsing r? from subject line r?#ent:lando-reviewers! (bug 2023719)

---
 test | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

diff --git a/test b/test
index 529d85073f838..ead51b49da5ef 100644
--- a/test
+++ b/test
@@ -1 +1 @@
-14b4db08-8232-471e-8ba6-d9467607ef9f
+49fdaf00-2d64-41e9-86e3-cb5aec774930
"""


@pytest.fixture
def sample_patch() -> str:
    """A patch with metadata header."""
    return SAMPLE_PATCH


#
# GITHUB FIXTURES
#


@pytest.fixture(autouse=True)
def hide_github_tokens(
    monkeypatch: pytest.MonkeyPatch,
):
    """Shield the tests from real GitHub env variables."""
    monkeypatch.setenv("GITHUB_APP_ID", "")
    monkeypatch.setenv("GITHUB_APP_PRIVKEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GH_TOKEN", "")


GITHUB_API_PARTIAL_USER = """\
{
  "login": "test-reviewer",
  "id": 42,
  "node_id": "MDQ6VXNlcjQyCg==",
  "avatar_url": "https://avatars.githubusercontent.com/u/42?v=4",
  "gravatar_id": "",
  "url": "https://api.github.com/users/test-reviewer",
  "html_url": "https://github.com/test-reviewer",
  "followers_url": "https://api.github.com/users/test-reviewer/followers",
  "following_url": "https://api.github.com/users/test-reviewer/following{/other_user}",
  "gists_url": "https://api.github.com/users/test-reviewer/gists{/gist_id}",
  "starred_url": "https://api.github.com/users/test-reviewer/starred{/owner}{/repo}",
  "subscriptions_url": "https://api.github.com/users/test-reviewer/subscriptions",
  "organizations_url": "https://api.github.com/users/test-reviewer/orgs",
  "repos_url": "https://api.github.com/users/test-reviewer/repos",
  "events_url": "https://api.github.com/users/test-reviewer/events{/privacy}",
  "received_events_url": "https://api.github.com/users/test-reviewer/received_events",
  "type": "User",
  "user_view_type": "public",
  "site_admin": false
}
"""

GITHUB_API_RESPONSE_PULL_REQUEST = (
    """\
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
    "login": "conduit-test-user",
    "id": 1337,
    "node_id": "MDQ6VXNlcjEzMzc=",
    "avatar_url": "https://avatars.githubusercontent.com/u/1337?v=4",
    "gravatar_id": "",
    "url": "https://api.github.com/users/conduit-test-user",
    "html_url": "https://github.com/conduit-test-user",
    "followers_url": "https://api.github.com/users/conduit-test-user/followers",
    "following_url": "https://api.github.com/users/conduit-test-user/following{/other_user}",
    "gists_url": "https://api.github.com/users/conduit-test-user/gists{/gist_id}",
    "starred_url": "https://api.github.com/users/conduit-test-user/starred{/owner}{/repo}",
    "subscriptions_url": "https://api.github.com/users/conduit-test-user/subscriptions",
    "organizations_url": "https://api.github.com/users/conduit-test-user/orgs",
    "repos_url": "https://api.github.com/users/conduit-test-user/repos",
    "events_url": "https://api.github.com/users/conduit-test-user/events{/privacy}",
    "received_events_url": "https://api.github.com/users/conduit-test-user/received_events",
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
  "requested_reviewers": ["""
    + GITHUB_API_PARTIAL_USER
    + """\
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
      "default_branch": "test-branch"
    }
  },
  "base": {
    "label": "mozilla-conduit:test-branch",
    "ref": "test-branch",
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
      "default_branch": "test-branch"
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
"""
)

GITHUB_API_RESPONSE_PULL_REQUEST_REQUESTED_REVIEWERS = (
    """\
{
  "users": ["""
    + GITHUB_API_PARTIAL_USER
    + """\
  ],
  "teams": [
  ]
}
"""
)


@pytest.fixture
def github_api_response_pull_request() -> str:
    """Return basic pull request metadata.

    XXX: GitHub never populates the requested_teams property.
    """
    return GITHUB_API_RESPONSE_PULL_REQUEST


@pytest.fixture
def github_api_response_pull_request_requested_reviewers() -> str:
    """Return pull request requested_reviewers data with one user and no team."""
    return GITHUB_API_RESPONSE_PULL_REQUEST_REQUESTED_REVIEWERS


@pytest.fixture
def mocked_github_request(
    github_api_response_pull_request: str,
    github_api_response_pull_request_requested_reviewers: str,
) -> requests_mock.Mocker:
    mock = requests_mock.Mocker()
    mock.get(
        "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18",
        text=github_api_response_pull_request,
    )
    mock.get(
        "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
        text=github_api_response_pull_request_requested_reviewers,
    )
    return mock


@pytest.fixture
def configurable_mocked_github_request() -> Callable[
    [list[str], list[str]], requests_mock.Mocker
]:

    def _configurable_mocked_github_request(
        initial_reviewers: list[str] | None = None,
        initial_team_reviewers: list[str] | None = None,
    ) -> requests_mock.Mocker:
        initial_reviewers = initial_reviewers or []
        initial_team_reviewers = initial_team_reviewers or []
        # We store this data locally, so the POST callback can modify it, and the changes
        # are reflected in subsequent GET callbacks.
        requested_reviewers_data = {
            "users": [{"login": r} for r in initial_reviewers],
            "teams": [{"slug": r} for r in initial_team_reviewers],
        }

        def add_reviewers_callback(
            request: requests.Request, _context: requests_mock.response._Context
        ) -> dict[str, Any]:
            """Callback implementing side-effects of add_reviewers requests in memory.

            This does not create full user/team objects, but should be enough to satisfy the
            adapter.
            """
            payload = request.json()

            for r in payload["reviewers"]:
                requested_reviewers_data["users"].append({"login": r})
            for t in payload["team_reviewers"]:
                # As of 2026-07-09, the GitHub API requires a `/ent:` prefix when adding
                # reviewers, but returns them without a leading `/`. We normalise the
                # data to the latter.
                if t.startswith("/ent:"):
                    t = t.removeprefix("/")
                requested_reviewers_data["teams"].append({"slug": t})

            return {}

        def get_reviewers_callback(request, context):
            """Callback returning our in-memory set of reviewers."""
            return requested_reviewers_data

        mock = requests_mock.Mocker()

        # Attach sub-mock and data to the mock, for easier inspection by the caller.
        mock.requested_reviewers_post = mock.post(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            json=add_reviewers_callback,
        )
        mock.requested_reviewers_get = mock.get(
            "https://api.github.com/repos/mozilla-conduit/reviewer-selector/pulls/18/requested_reviewers",
            json=get_reviewers_callback,
        )
        mock.requested_reviewers_data = requested_reviewers_data

        return mock

    return _configurable_mocked_github_request


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
                            {"target": "ent:fluent-reviewers", "is_group": True},
                        ],
                    }
                ],
            },
        ],
        "groups": {
            "fluent-reviewers": {"members": ["alice", "bob"]},
            "test-reviewers": {"members": ["charlie"]},
            "ent:fluent-reviewers": {"members": ["bob"]},
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
