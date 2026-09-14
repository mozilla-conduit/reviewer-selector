#!/usr/bin/env python

import json
import logging
import os
import sys
from argparse import ArgumentParser
from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from requests.exceptions import HTTPError
from simple_github import Client, TokenClient
from simple_github.client import GITHUB_API_ENDPOINT

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
    args_parser.add_argument("--organisation", default="mozilla-firefox")
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
        logger.error("No (or empty) --github-token, GH_TOKEN or GITHUB_TOKEN")
        sys.exit(1)

    client = TokenClient(token)

    with open(arguments.rules) as f:
        rules = json.load(f)

    try:
        create_teams(client, rules, organisation, base_team, arguments.dry_run)
    except HTTPError as exc:
        logger.error(
            f"Exception when creating teams: {exc} for {exc.request.body}: {exc.response.text}"
        )
        sys.exit(2)


RulesGitHubUsers = dict[str, dict[str, str]]
RulesGroups = dict[str, dict[str, Any]]

PhabGitHubMap = dict[str, str]
GitHubTeams = dict[str, set[str]]


def create_teams(
    client: Client,
    herald_rules: dict[str, Any],
    organisation: str,
    base_team: str,
    dry_run: bool,
):

    logger.debug("Creating Phabricator->GitHub user map ...")
    github_users: RulesGitHubUsers = herald_rules.get("github_users", {})
    logger.info(f"Found {len(github_users)} Phabricator->GitHub user mappings")

    logger.info("Creating GitHub Teams member lists ...")
    groups: RulesGroups = herald_rules.get("groups", {})
    teams: GitHubTeams = {}
    all_users = set()
    for group_name, group_data in groups.items():
        members = set()
        for phab_name in group_data.get("members", []):
            if phab_name not in github_users:
                logger.warning(f"Unresolved GitHub username for {phab_name}")
                continue
            github_name = github_users[phab_name].get("username", "")
            if not github_name:
                logger.warning(f"Empty or missing GitHub username for {phab_name}")
                continue
            members.add(github_name)
            all_users.add(github_name)

        teams[group_name] = members

    # find base team
    ensure_team_exists(client, organisation, base_team, dry_run)
    update_team_members(client, organisation, base_team, all_users, dry_run)

    for team, target_members in teams.items():
        # create team
        ensure_team_exists(
            client,
            organisation,
            team,
            dry_run,
            parent_team=base_team,
            display_name=groups.get(team, {}).get("display_name"),
        )
        update_team_members(client, organisation, team, target_members, dry_run)


def ensure_team_exists(
    client: Client,
    organisation: str,
    team_name: str,
    dry_run: bool,
    *,
    display_name: str = "",
    parent_team: str = "",
) -> dict[str, Any]:
    logger.debug(f"Ensuring {team_name} exists ...")
    team_url = _make_team_url(organisation, team_name)
    resp: requests.Response = client.get(team_url)

    if resp.status_code == 404:
        if dry_run:
            logger.info(f"[DRY-RUN] Would create team {team_name}")
            return {}

        description = "Automatically created by reviewer-selector's team-creator"
        if display_name:
            description = f"{display_name} ({description})"

        create_payload = {
            "name": team_name,
            "description": description,
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
    except HTTPError:
        if not dry_run:
            raise
        logger.info(f"[DRY-RUN] Error getting {team_name} details")
        return {}

    return resp.json()


def update_team_members(
    client: Client,
    organisation: str,
    team: str,
    target_members: set[str],
    dry_run: bool,
):
    # get team members
    current_members = get_team_members(client, organisation, team, dry_run)
    logger.info(f"Current members of {team}: {current_members}")

    # add new users
    if users_to_add := target_members - current_members:
        add_team_members(client, organisation, team, users_to_add, dry_run)

    # remove missing users
    if members_to_remove := current_members - target_members:
        remove_team_members(client, organisation, team, members_to_remove, dry_run)


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
        logger.info(f"[DRY RUN] Would remove members from {team_name}: {members}")
        return

    for user in members:
        try:
            # As of 3.2.2, simple_github.Client.delete returns None ...
            client.delete(remove_url + user)
            removed_members.append(user)
        except HTTPError as exc:
            # ... so this is dead code, as we don't raise_for_status.
            # We keep it here for now, with the intention of making simple_github more
            # consistent.
            logger.warning(
                f"Cannot remove {user} from {team_name}: {exc.response.text}"
            )

    logger.info(f"Removed members from {team_name}: {removed_members}")


def get_team_members(
    client: Client, organisation: str, team_name: str, dry_run: bool
) -> set[str]:
    logger.debug(f"Getting {team_name} membership ...")
    team_url = _make_team_url(organisation, team_name)

    try:
        members = {
            member["login"]
            for page in paginated_get(client, f"{team_url}/members")
            for member in page
        }
    except HTTPError:
        if not dry_run:
            raise
        logger.info(f"[DRY-RUN] Error getting {team_name} membership, assuming empty")
        return set()

    return members


def paginated_get(client: Client, url: str) -> Generator[list[Any], None, None]:
    parsed_url = urlsplit(url)
    if not parsed_url.query or "per_page" not in (qs := parse_qs(parsed_url.query)):
        if not parsed_url.query:
            qs = {}
        qs["per_page"] = "100"
        url = parsed_url._replace(query=urlencode(qs)).geturl()

    while True:
        resp: requests.Response = client.get(url)
        resp.raise_for_status()

        yield resp.json()

        url = (
            resp.links.get("next", {}).get("url", "").removeprefix(GITHUB_API_ENDPOINT)
        )
        if not url:
            return


def _make_team_url(organisation: str, team_name: str) -> str:
    return f"/orgs/{organisation}/teams/{team_name}"


if __name__ == "__main__":
    main()
