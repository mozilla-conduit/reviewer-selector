#!/usr/bin/env python

import asyncio
import os

from simple_github import AppAuth, AppInstallationAuth
from taskcluster.helper import TaskclusterConfig, load_secrets


def main() -> int:
    tc = TaskclusterConfig()
    tc.auth()

    if not (tc_secret_id := os.environ.get("TC_SECRET_ID")):
        raise Exception("Missing or empty TC_SECRET_ID in environment")

    if not (gh_owner := os.environ.get("ORG_NAME")):
        raise Exception("Missing or empty ORG_NAME in environment")

    if not (gh_repo := os.environ.get("REPO_NAME")):
        raise Exception("Missing or empty REPO_NAME in environment")

    print(generate_token(tc, tc_secret_id, gh_owner, gh_repo))
    return 0


def generate_token(
    tc: TaskclusterConfig, tc_secret_id: str, gh_owner: str, gh_repo: str
) -> str:
    tc_secret = fetch_tc_secret(tc, tc_secret_id)
    return generate_github_token(
        tc_secret["GITHUB_APP_ID"], tc_secret["GITHUB_APP_PRIVKEY"], gh_owner, gh_repo
    )


def fetch_tc_secret(tc: TaskclusterConfig, secret_id: str) -> dict[str, str]:
    secrets = tc.get_service("secrets")
    return load_secrets(secrets, secret_id)


def generate_github_token(
    app_id: str, app_privkey: str, gh_owner: str, gh_repo: str
) -> str:
    return asyncio.run(
        async_generate_github_token(app_id, app_privkey, gh_owner, gh_repo)
    )


async def async_generate_github_token(
    app_id: str, app_privkey: str, gh_owner: str, gh_repo: str
) -> str:
    app_auth = AppAuth(app_id, app_privkey)
    inst_auth = AppInstallationAuth(app_auth, gh_owner, repositories=[gh_repo])
    token = await inst_auth.get_token()
    await inst_auth.close()
    return token


if __name__ == "__main__":
    exit(main())
