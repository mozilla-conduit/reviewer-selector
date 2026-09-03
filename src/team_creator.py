#!/usr/bin/env python

import json
import logging
import os
import sys
from argparse import ArgumentParser
from typing import Any

import requests
from requests.exceptions import HTTPError
from simple_github import Client, TokenClient

logger = logging.getLogger(__name__)


def main():
    args_parser = ArgumentParser()
    args_parser.add_argument("--base-team", default="all-reviewers")
    args_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
    )
    args_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
    )
    args_parser.add_argument("--github-token")
    args_parser.add_argument("--organisation", default="bug2001552")
    args_parser.add_argument("rules")

    arguments = args_parser.parse_args()

    # Honour the highest verbosity level requested.
    if arguments.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    organisation = arguments.organisation
    base_team = arguments.base_team

    token = arguments.github_token or os.getenv("GH_TOKEN", os.getenv("GITHUB_TOKEN"))
    if not token:
        logger.error("No --github-token, GH_TOKEN or GITHUB_TOKEN")
        sys.exit(1)

    client = TokenClient(token)

    with open(arguments.rules) as f:
        rules = json.load(f)

    try:
        create_teams(client, rules, organisation, base_team, arguments.dry_run)
    except HTTPError as exc:
        print(f"{exc} for {exc.request.body}: {exc.response.text}")
        sys.exit(3)


RulesGitHubUsers = dict[str, dict[str, str]]
RulesGroups = dict[str, dict[str, Any]]

PhabGitHubMap = dict[str, str]
GitHubTeams = dict[str, list[str]]


def create_teams(
    client: Client,
    herald_rules: dict[str, Any],
    organisation: str,
    base_team: str,
    dry_run: bool,
):

    logger.debug("Creating Phabricator->GitHub user map ...")
    github_users: RulesGitHubUsers = herald_rules.get("github_users", {})
    phab_github_user_map: PhabGitHubMap = {
        phab_name: github_users[phab_name]["username"] for phab_name in github_users
    }
    logger.info(f"Found {len(phab_github_user_map)} Phabricator->GitHub user mappings")

    logger.info("Creating GitHub Teams member lists ...")
    groups: RulesGroups = herald_rules.get("groups", {})
    teams: GitHubTeams = {}
    for group_name, group_data in groups.items():
        members = []
        for phab_name in group_data.get("members", []):
            if phab_name not in github_users:
                logger.warning(f"Unresolved GitHub username for {phab_name}")
                continue
            github_name = github_users[phab_name].get("username", "")
            if not github_name:
                logger.warning(f"Empty or missing GitHub username for {phab_name}")
                continue
            members.append(github_name)

        teams[group_name] = members

    # find base team
    ensure_team_exists(client, organisation, base_team, dry_run)
    members = get_team_members(client, organisation, base_team, dry_run)
    logger.info(f"All members of {base_team}: {members}")

    for team in teams:
        # create team
        ensure_team_exists(client, organisation, team, dry_run, parent_team=base_team)

        # get team members
        members = get_team_members(client, organisation, team, dry_run)
        logger.info(f"Current members of {team}: {members}")

        # add new users
        if users_to_add := set(teams[team]) - members:
            add_team_members(client, organisation, team, users_to_add, dry_run)

        # remove missing users
        if members_to_remove := members - set(teams[team]):
            remove_team_members(client, organisation, team, members_to_remove, dry_run)


def ensure_team_exists(
    client: Client,
    organisation: str,
    team_name: str,
    dry_run: bool,
    *,
    parent_team: str = "",
) -> dict[str, Any]:
    logger.debug(f"Ensuring {team_name} exists ...")
    team_url = _make_team_url(organisation, team_name)
    resp: requests.Response = client.get(team_url)

    if resp.status_code == 404:
        if dry_run:
            logger.info(f"[DRY-RUN] Would create team {team_name}")
            return {}

        create_payload = {
            "name": team_name,
            "description": "Automatically created by reviewer-selector's team-creator",
            "permission": "pull",
            "notification_setting": "notifications_enabled",
            "privacy": "closed",
        }
        if parent_team:
            create_payload["parent_team_slug"] = parent_team

        logger.debug(f"Creating team {team_name} ...")
        resp = client.post(f"/orgs/{organisation}/teams", data=create_payload)
        logger.info(f"Created team {team_name}")

    try:
        resp.raise_for_status()
    except:  # noqa: E722
        if not dry_run:
            raise
        logger.info(f"[DRY-RUN] Error getting {team_name} details")
        return {}

    return resp.json()


def add_team_members(
    client: Client, organisation: str, team_name: str, users: set[str], dry_run: bool
):
    logger.debug(f"Adding users to {team_name}: {users} ...")
    add_url = f"orgs/{organisation}/teams/{team_name}/memberships/"
    add_payload = {"role": "member"}
    added_users = []

    if dry_run:
        logger.info(f"[DRY RUN] Would add users to {team_name}: {users}")
        return

    for user in users:
        try:
            resp: requests.Response = client.put(add_url + user, data=add_payload)
            resp.raise_for_status()
            added_users.append(user)
        except HTTPError as exc:
            logger.warning(f"Cannot add {user} to {team_name}: {exc.response.text}")

    logger.info(f"Added users to {team_name}: {added_users}")


def remove_team_members(
    client: Client, organisation: str, team_name: str, members: set[str], dry_run: bool
):
    logger.debug(f"Removing members from {team_name}: {members} ...")
    remove_url = f"orgs/{organisation}/teams/{team_name}/memberships/"
    removed_members = []

    if dry_run:
        logger.info(
            f"[DRY RUN] Would remove members from {team_name}: {removed_members}"
        )
        return

    for user in members:
        try:
            # simple_github.Client.delete returns None
            client.delete(remove_url + user)
            removed_members.append(user)
        except HTTPError as exc:
            logger.warning(
                f"Cannot remove {user} from {team_name}: {exc.response.text}"
            )

    logger.info(f"Removed members from {team_name}: {removed_members}")


def get_team_members(
    client: Client, organisation: str, team_name: str, dry_run: bool
) -> set[str]:
    logger.debug(f"Getting {team_name} membership ...")
    team_url = _make_team_url(organisation, team_name)

    resp: requests.Response = client.get(
        f"{team_url}/members",
    )

    try:
        resp.raise_for_status()
    except:  # noqa: E722
        if not dry_run:
            raise
        logger.info(f"[DRY-RUN] Error getting {team_name} membership, assuming empty")
        return set()

    return {user["login"] for user in resp.json()}


def _make_team_url(organisation: str, team_name: str) -> str:
    return f"/orgs/{organisation}/teams/{team_name}"


if __name__ == "__main__":
    main()
