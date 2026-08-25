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

logging.basicConfig(level=logging.DEBUG)


def main():
    args_parser = ArgumentParser()
    args_parser.add_argument("--organisation", default="mozilla-firefox")
    args_parser.add_argument("--base-team", default="all-reviewers")
    args_parser.add_argument("--github-token")
    args_parser.add_argument("rules")

    arguments = args_parser.parse_args()

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
        create_teams(client, rules, organisation, base_team)
    except HTTPError as exc:
        print(f"{exc} for {exc.request.body}: {exc.response.text}")
        sys.exit(3)


RulesGitHubUsers = dict[str, dict[str, str]]
RulesGroups = dict[str, dict[str, Any]]

PhabGitHubMap = dict[str, str]
GitHubTeams = dict[str, list[str]]


def create_teams(
    client: Client, herald_rules: dict[str, Any], organisation: str, base_team: str
):

    logger.debug("Creating Phabricator->GitHub user map ...")
    github_users: RulesGitHubUsers = herald_rules.get("github_users", {})
    phab_github_user_map: PhabGitHubMap = {
        phab_name: github_users[phab_name]["username"] for phab_name in github_users
    }
    logger.info(
        f"Found {len(phab_github_user_map)} Phabricator->GitHub user mappings..."
    )

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
    ensure_team_exists(client, organisation, base_team)
    members = get_team_members(client, organisation, base_team)
    logger.debug(f"Current members of {base_team}: {members}")

    for team in teams:
        # create team
        ensure_team_exists(client, organisation, team, base_team)

        # get team members
        members = get_team_members(client, organisation, team)
        logger.debug(f"Current members of {team}: {members}")

        # add new users
        if users_to_add := set(teams[team]) - members:
            add_team_members(client, organisation, team, users_to_add)

        # remove missing users
        if members_to_remove := members - set(teams[team]):
            remove_team_members(client, organisation, team, members_to_remove)


def ensure_team_exists(
    client: Client, organisation: str, team_name: str, parent_team: str = ""
) -> dict[str, Any]:
    logger.debug(f"Ensuring {team_name} exists ...")
    team_url = _make_team_url(organisation, team_name)
    resp: requests.Response = client.get(team_url)

    if resp.status_code == 404:
        create_payload = {
            "name": team_name,
            "description": "Super-team of all staff allowed to review changes",
            "permission": "pull",
            "notification_setting": "notifications_enabled",
            "privacy": "closed",
        }
        if parent_team:
            create_payload["parent_team_slug"] = parent_team

        logger.info(f"Creating team {team_name} ...")
        resp = client.post(f"/orgs/{organisation}/teams", data=create_payload)

    resp.raise_for_status()

    return resp.json()


def add_team_members(
    client: Client, organisation: str, team_name: str, users: set[str]
):
    logger.debug(f"Adding users to {team_name}: {users} ...")
    add_url = f"orgs/{organisation}/teams/{team_name}/memberships/"
    add_payload = {"role": "member"}
    added_users = []
    for user in users:
        try:
            resp: requests.Response = client.put(add_url + user, data=add_payload)
            resp.raise_for_status()
            added_users.append(user)
        except HTTPError as exc:
            logger.warning(f"Cannot add {user} to {team_name}: {exc.response.text}")

    logger.debug(f"Added users to {team_name}: {added_users}")


def remove_team_members(
    client: Client, organisation: str, team_name: str, members: set[str]
):
    logger.debug(f"Removing members from {team_name}: {members} ...")
    remove_url = f"orgs/{organisation}/teams/{team_name}/memberships/"
    removed_members = []
    for user in members:
        try:
            resp: requests.Response = client.delete(remove_url + user)
            resp.raise_for_status()
            removed_members.append(user)
        except HTTPError as exc:
            logger.warning(
                f"Cannot remove {user} from {team_name}: {exc.response.text}"
            )

    logger.debug(f"Removed members from {team_name}: {removed_members}")


def get_team_members(client: Client, organisation: str, team_name: str) -> set[str]:
    logger.debug(f"Getting {team_name} membership ...")
    team_url = _make_team_url(organisation, team_name)

    resp: requests.Response = client.get(
        f"{team_url}/members",
    )
    resp.raise_for_status()

    return {user["login"] for user in resp.json()}


def _make_team_url(organisation: str, team_name: str) -> str:
    return f"/orgs/{organisation}/teams/{team_name}"


if __name__ == "__main__":
    main()
