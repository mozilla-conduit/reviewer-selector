#!/usr/bin/env python

import os


from reviewer_selector import Taskcluster, GitHubApp


def main() -> int:
    """Generate a GitHub token using a TaskCluster secret, with parameters in env."""
    tc = Taskcluster()

    if not (tc_secret_id := os.environ.get("TC_SECRET_ID")):
        raise ValueError("Missing or empty TC_SECRET_ID in environment")

    if not (gh_owner := os.environ.get("ORG_NAME")):
        raise ValueError("Missing or empty ORG_NAME in environment")

    if not (gh_repo := os.environ.get("REPO_NAME")):
        raise ValueError("Missing or empty REPO_NAME in environment")

    print(generate_token(tc, tc_secret_id, gh_owner, gh_repo))
    return 0


def generate_token(
    tc: Taskcluster, tc_secret_id: str, gh_owner: str, gh_repo: str
) -> str:
    """Generate a GitHub token using a TaskCluster secret, fetched by its ID."""
    tc_secret = tc.fetch_secret(tc_secret_id)
    github_app = GitHubApp(
        tc_secret["GITHUB_APP_ID"], tc_secret["GITHUB_APP_PRIVKEY"], gh_owner, gh_repo
    )
    return github_app.generate_token()


if __name__ == "__main__":
    exit(main())
