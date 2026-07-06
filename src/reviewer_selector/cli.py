import argparse
import logging
from collections.abc import Iterable
import os


from reviewer_selector.taskcluster import Taskcluster
from reviewer_selector.github import GitHubPR
from reviewer_selector.patch import Patch, StdinPatchSource
from reviewer_selector.review import Reviewer, StdoutReviewable, MappingUserResolver
from reviewer_selector.rules import Rules


logger = logging.getLogger(__name__)


def cli() -> None:
    """Select reviewers based on Herald rules and unified diff."""
    args: argparse.Namespace = parse_args()

    # Honour the highest verbosity level requested.
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)

    rules = Rules.from_file(args.rules_file)

    repos = args.repo

    # Default parameters that always work.
    patch_source = StdinPatchSource()
    resolver = MappingUserResolver(
        args.group_prefix, rules.get_rules().get("github_users", {})
    )
    reviewable = StdoutReviewable(args.reviewer_separator)

    # Override the parameters based on context.
    if args.pr_url:
        ghpr = GitHubPR(args.pr_url, rules)
        repo_branch = f"{ghpr.repository}-{ghpr.target_branch_name}"

        logger.info(
            f"PR URL provided ({args.pr_url}); using GitHub adapters for {repo_branch} ..."
        )

        repos.append(repo_branch)

        # Override rules with in-tree file if present.
        rules = ghpr.rules or rules

        patch_source = ghpr
        resolver = ghpr

        if github_creds := resolve_github_credentials(args):
            ghpr.set_app_credentials(*github_creds)
            reviewable = ghpr
        else:
            logger.warning(
                "Missing GitHub credentials (GITHUB_APP_ID and GITHUB_APP_PRIVKEY, or TC_SECRET_ID, reviewers will be output to stdout instead"
            )
    patch = Patch(patch_source.fetch_patch())

    reviewers: Iterable[Reviewer] = rules.collect_reviewers(patch, repos)

    resolved: Iterable[Reviewer] = resolver.resolve_reviewers(reviewers)

    reviewable.add_reviewers(resolved)


def resolve_github_credentials(args: argparse.Namespace) -> tuple[str, str] | None:
    """Resolve GitHub app ID and privkey from CLI options, environment and TaskCluster."""

    # Give precedence to explicit options, or default to environment.
    app_id = args.github_app_id or os.environ.get("GITHUD_APP_ID")
    app_privkey = args.github_app_privkey or os.environ.get("GITHUD_APP_PRIVKEY")

    if app_id and app_privkey:
        return app_id, app_privkey

    # If any is missing, try to update from credentials store.
    if tc_secret_id := (args.taskcluster_secret_id or os.environ.get("TC_SECRET_ID")):
        logger.debug(
            f"Fetching GitHup app credentials from TC_SECRET_ID {tc_secret_id} ..."
        )
        tc = Taskcluster()
        tc_secret = tc.fetch_secret(tc_secret_id)
        app_id = app_id or tc_secret.get("GITHUD_APP_ID")
        app_privkey = app_privkey or tc_secret.get("GITHUD_APP_PRIVKEY")

        if app_id and app_privkey:
            return app_id, app_privkey

    return None


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

    # GitHub options.
    parser.add_argument(
        "--pr-url",
        default=None,
        help="HTML URL of the GitHub PR to process. If app credentials are provided, the reviewers will be set on the PR automatically.",
    )
    parser.add_argument(
        "--github-app-id",
        default=None,
        help="GitHub application ID (credentials: GITHUB_APP_ID)",
    )
    parser.add_argument(
        "--github-app-privkey",
        default=None,
        help="GitHub application private key (credentials: GITHUB_APP_PRIVKEY)",
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


if __name__ == "__main__":
    cli()
