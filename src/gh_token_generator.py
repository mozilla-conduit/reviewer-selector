#!/usr/bin/env python

import os


from reviewer_selector import Taskcluster, GitHubApp


def main() -> int:
    """Generate a GitHub token using a TaskCluster secret, with parameters in env."""

    gh_app_id = os.environ.get("GITHUB_APP_ID")
    gh_app_privkey = os.environ.get("GITHUB_APP_PRIVKEY")

    if not (gh_owner := os.environ.get("ORG_NAME")):
        raise ValueError("Missing or empty ORG_NAME in environment")

    if not (gh_repo := os.environ.get("REPO_NAME")):
        raise ValueError("Missing or empty REPO_NAME in environment")

    if not (gh_app_id and gh_app_privkey):
        tc = Taskcluster()
        if not (tc_secret_id := os.environ.get("TC_SECRET_ID")):
            raise ValueError("Missing or empty TC_SECRET_ID in environment")

        gh_app_id, gh_app_privkey = get_app_credentials(tc, tc_secret_id)

    print(generate_token(gh_app_id, gh_app_privkey, gh_owner, gh_repo))
    return 0


def get_app_credentials(tc: Taskcluster, tc_secret_id: str) -> tuple[str, str]:
    """Fetch GitHub app credentials from a TaskCluster secret, fetched by ID."""
    tc_secret = tc.fetch_secret(tc_secret_id)
    return (tc_secret["GITHUB_APP_ID"], tc_secret["GITHUB_APP_PRIVKEY"])


def generate_token(
    gh_app_id: str, gh_app_privkey: str, gh_owner: str, gh_repo: str
) -> str:
    """Generate a GitHub token."""
    github_app = GitHubApp(gh_app_id, gh_app_privkey, gh_owner, gh_repo)
    return github_app.generate_token()


if __name__ == "__main__":
    exit(main())
