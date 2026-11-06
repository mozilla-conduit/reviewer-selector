import argparse
import logging
import os
import sys
from collections.abc import Collection, Iterable
from functools import lru_cache
from typing import Any

import sentry_sdk

from reviewer_selector.github import GitHubPR
from reviewer_selector.patch import Patch, PatchSource, StdinPatchSource
from reviewer_selector.phabricator import PhabricatorRevision
from reviewer_selector.review import (
    AddReviewersStatus,
    MappingUserResolver,
    Reviewable,
    Reviewer,
    StdoutReviewable,
    UserResolver,
)
from reviewer_selector.rules import Rules, RulesErrors
from reviewer_selector.taskcluster import Taskcluster, tc_task_url

logger = logging.getLogger(__name__)


def cli() -> None:
    """Select reviewers based on Herald rules and unified diff."""
    args: argparse.Namespace = parse_args()

    # Honour the highest verbosity level requested.
    if args.debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        )
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)

    if sentry_dsn := get_sentry_dsn(args):
        sentry_sdk.init(
            dsn=sentry_dsn,
            send_default_pii=True,
        )

    rules = Rules.from_file(args.rules_file)

    repos = set(args.repo)

    # Default parameters that always work.
    patch_source = StdinPatchSource()
    resolver = MappingUserResolver(
        args.group_prefix, rules.get_rules().get("github_users", {})
    )
    reviewable = StdoutReviewable(args.reviewer_separator)

    # Override the parameters based on context.
    if args.pr_url:
        rules, patch_source, resolver, gh_reviewable = create_github_objects(
            args, rules, repos
        )

        reviewable = gh_reviewable or reviewable
    elif args.phabricator_revision_url or args.phabricator_revision_phid:
        rules, patch_source, resolver, reviewable = create_phabricator_objects(
            args, rules, repos
        )

    if not reviewable.ready_for_review():
        logger.warning("Reviewable is not ready for review.")
        return

    patch = Patch(patch_source.patch, patch_source.get_patch_subject())

    reviewers = Reviewer.flatten_blocking(
        set(patch.get_subject_reviewers()) | set(rules.collect_reviewers(patch, repos))
    )

    resolved: Iterable[Reviewer] = resolver.resolve_reviewers(reviewers)

    try:
        status = reviewable.add_new_reviewers(resolved)
    except Exception:
        logger.exception("Error adding new reviewers")
        status = AddReviewersStatus(0, False)

    report_status(reviewable, status, resolved, rules.errors)


def get_sentry_dsn(args) -> str | None:
    dsn = get_env_secret(args, "SENTRY_DSN")
    if dsn:
        return dsn

    logger.warning("Exceptions will not be reported")


def create_phabricator_objects(
    args: argparse.Namespace, default_rules: Rules, repos_to_update: list[str]
) -> tuple[Rules, PatchSource, UserResolver, Reviewable]:
    """Create the Phabricator adapters."""
    phabricator_api_token = resolve_phabricator_credentials(args)

    if args.phabricator_revision_phid:
        phab_base_url = get_env_secret(args, "PHABRICATOR_BASE_URL")
        if args.phabricator_revision_phid and not phab_base_url:
            logger.error("Missing Phabricator base URL for PHID resolution")
            sys.exit(1)
        phabrev = PhabricatorRevision.from_phid(
            phab_base_url, args.phabricator_revision_phid, phabricator_api_token
        )

    else:
        phabrev = PhabricatorRevision(
            args.phabricator_revision_url, phabricator_api_token
        )

    repo_branch = f"{phabrev.repository}"

    logger.info(
        f"Phabricator Revision URL provided ({args.phabricator_revision_url}); using Phabricator adapters for {repo_branch} ..."
    )

    repos_to_update.add(repo_branch)

    patch_source = phabrev.patch_source
    # No need to remap users for Phabricator.
    resolver = MappingUserResolver("", {})
    reviewable = phabrev.reviewable

    return default_rules, patch_source, resolver, reviewable


def get_env_secret(args, variable: str) -> str | None:
    """Fetch the named value from the environment, or the TC secrets, in that order."""
    if value := os.environ.get(variable):
        return value
    if tc_secret := get_tc_secret(get_tc_secret_id(args)):
        return tc_secret.get(variable)

    logger.warning(f"No {variable} found.")


def resolve_phabricator_credentials(args: argparse.Namespace):
    """Resolve Phabricator API Token from CLI options, environment and TaskCluster."""
    if args.phabricator_api_token:
        return args.phabricator_api_token

    if conduit_token := PhabricatorRevision.get_token_from_env():
        return conduit_token

    if tc_secret_id := (args.taskcluster_secret_id or os.environ.get("TC_SECRET_ID")):
        logger.debug(f"Fetching Phabricator token from TC_SECRET_ID {tc_secret_id} ...")
        tc = Taskcluster()
        tc_secret = tc.fetch_secret(tc_secret_id)

        if conduit_token := tc_secret.get("PHABRICATOR_API_TOKEN"):
            return conduit_token

    raise ValueError("Cannot determine Phabricator API token.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select reviewers from Herald rules and git diff",
        epilog="""Example:
            curl https://github.com/mozilla-firefox/infra-testing/pull/30.diff | %(prog)s herald_rules.json

            Command line options take precedence over environment variables and stored credentials.""",
    )
    parser.add_argument("rules_file", help="Path to JSON rules file")
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Log details of the reviewer selection",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Log debug message of the reviewer selection",
    )

    parser.add_argument(
        "--repo", action="append", default=[], help="Filter by repository (repeatable)"
    )

    reviewable_type = parser.add_mutually_exclusive_group()

    # GitHub options.
    reviewable_type.add_argument(
        "--pr-url",
        default=None,
        help="HTML URL of the GitHub PR to process. If app credentials are provided, the reviewers will be set on the PR automatically.",
    )
    parser.add_argument(
        "--github-app-id",
        default=None,
        help="GitHub application ID (env/credentials: GITHUB_APP_ID)",
    )
    parser.add_argument(
        "--github-app-privkey",
        default=None,
        help="GitHub application private key (env/credentials: GITHUB_APP_PRIVKEY)",
    )
    parser.add_argument(
        "--github-token",
        default=None,
        help="GitHub token (env/credentials: GITHUB_TOKEN; env: also GH_TOKEN)",
    )

    # Phabricator options.
    parser.add_argument(
        "--phabricator-api-token",
        default=None,
        help="Phabricator API token (env/credentials: PHABRICATOR_API_TOKEN)",
    )
    parser.add_argument(
        "--phabricator-base-url",
        help="Base URL of the Phabricator instance to resolve PHIDs from (env/credentials: PHABRICATOR_BASE_URL)",
    )

    reviewable_type.add_argument(
        "--phabricator-revision-phid",
        help="PHID of the Phabricator Revision to process (PHID-DREV-...)",
    )

    reviewable_type.add_argument(
        "--phabricator-revision-url",
        help="HTML URL of the Phabricator Revision to process",
    )

    parser.add_argument(
        "--taskcluster-secret-id",
        default=None,
        help="TaskCluster secret ID to fetch GitHub credentials from (environment: TC_SECRET_ID). Command line options take precedence.",
    )

    parser.add_argument(
        "--group-prefix", default="#", help="Prefix for group names in output"
    )
    parser.add_argument(
        "--reviewer-separator",
        default=" ",
        help="Separator for reviewer names in output",
    )
    return parser.parse_args()


def create_github_objects(
    args: argparse.Namespace, default_rules: Rules, repos_to_update: set[str]
) -> tuple[Rules, PatchSource, UserResolver, Reviewable]:
    """Create the GitHub adapters.

    Note: the repos_to_update may get updated based on information on the PR.
    """
    ghpr = GitHubPR(args.pr_url, default_rules)

    repo_branch = f"{ghpr.repository}-{ghpr.target_branch_name}"
    logger.info(
        f"PR URL provided ({args.pr_url}); using GitHub adapters for {repo_branch} ..."
    )
    repos_to_update.add(repo_branch)

    # Override rules with in-tree file if present.
    rules = ghpr.rules or default_rules

    patch_source = ghpr.patch_source
    resolver = ghpr.user_resolver

    reviewable = None
    if github_creds := resolve_github_credentials(args):
        ghpr.set_app_credentials(**github_creds)
        reviewable = ghpr.reviewable
    else:
        logger.warning(
            "Missing GitHub credentials (GH_TOKEN, GITHUB_TOKEN, GITHUB_APP_ID & GITHUB_APP_PRIVKEY, or TC_SECRET_ID, reviewers will be output to stdout instead"
        )

    return rules, patch_source, resolver, reviewable


def resolve_github_credentials(args: argparse.Namespace) -> dict[str, str]:
    """Resolve GitHub token, app ID and privkey from CLI options, environment and TaskCluster."""

    # Give precedence to explicit options, or default to environment.

    # Support standard GH_TOKEN/GITHUB_TOKEN order of precedence.
    if gh_token := (
        args.github_token
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
    ):
        return {"gh_token": gh_token}

    app_id = args.github_app_id or os.environ.get("GITHUB_APP_ID")
    app_privkey = args.github_app_privkey or os.environ.get("GITHUB_APP_PRIVKEY")
    if app_id and app_privkey:
        return {"app_id": app_id, "app_privkey": app_privkey}

    # If any is missing, try to update from credentials store.
    if tc_secret := get_tc_secret(get_tc_secret_id(args)):
        app_id = app_id or tc_secret.get("GITHUB_APP_ID", "")
        app_privkey = app_privkey or tc_secret.get("GITHUB_APP_PRIVKEY", "")
        # We allow passing the GITHUB_TOKEN via secrets, but it's not recommended.
        gh_token = tc_secret.get("GITHUB_TOKEN", "")

        if app_id and app_privkey or gh_token:
            return {"app_id": app_id, "app_privkey": app_privkey, "gh_token": gh_token}

    return {}


def get_tc_secret_id(args: argparse.Namespace) -> str | None:
    return args.taskcluster_secret_id or os.environ.get("TC_SECRET_ID")


@lru_cache
def get_tc_secret(tc_secret_id: str | None) -> dict[str, Any] | None:
    if not tc_secret_id:
        return
    logger.debug(f"Fetching credentials from TC_SECRET_ID {tc_secret_id} ...")
    tc = Taskcluster()
    return tc.fetch_secret(tc_secret_id)


def report_status(
    reviewable: Reviewable,
    status: AddReviewersStatus,
    requested_reviewers: Collection[Reviewer],
    rules_errors: RulesErrors,
):
    tc_info = []
    if tc_link := make_tc_task_link():
        tc_info = ["", tc_link]

    # report_warning may alter the whole state of the Reviewable (e.g., GitHub checks),
    # so it should only be used once.
    warnings = []
    if rules_errors:
        rule_errors = "\n".join(
            f" * {rule_id}: {'; '.join(errors)}"
            for rule_id, errors in rules_errors.items()
        )
        warnings.append(f"Some rules reported exceptions:\n\n{rule_errors}")

    if not reviewable.reviewers:
        errors = ["No reviewer currently assigned."]
        if warnings:
            errors.extend(
                ["", "In addition, the following warnings were reported.", ""]
            )
            errors.extend(warnings)

        errors.extend(tc_info)
        reviewable.report_error("\n".join(errors))
    elif not status.all_new_reviewer_added or warnings:
        # Put the most important warning first.
        if not status.all_new_reviewer_added:
            missing_reviewers = ", ".join(
                f"`{r.name}`"
                for r in set(requested_reviewers) - set(reviewable.reviewers)
            )
            for line in reversed(
                [
                    "Not all reviewers were added.",
                    "",
                    f"Missing/unresolved: {missing_reviewers}.",
                    "",
                ]
            ):
                warnings.insert(0, line)

        warnings.extend(tc_info)
        reviewable.report_warning("\n".join(warnings))
    else:
        success = ["Reviewers successfully assigned."]
        success.extend(tc_info)
        reviewable.report_success("\n".join(success))


def make_tc_task_link() -> str:
    if task_url := tc_task_url():
        return f"[See task in Taskcluster]({task_url})"

    return ""


if __name__ == "__main__":
    cli()
