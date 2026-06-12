import argparse
import logging
from collections.abc import Iterable


from reviewer_selector.patch import Patch, StdinPatchSource
from reviewer_selector.review import Reviewer, StdoutReviewable, UserResolver
from reviewer_selector.rules import Rules


logger = logging.getLogger(__name__)


def main() -> None:
    """Select reviewers based on Herald rules and unified diff."""
    args: argparse.Namespace = parse_args()

    # Honour the highest verbosity level requested.
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)

    rules = Rules.from_file(args.rules_file)

    patch_source = StdinPatchSource()
    reviewable = StdoutReviewable(args.reviewer_separator)

    patch = Patch(patch_source.fetch_patch())

    reviewers: Iterable[Reviewer] = rules.collect_reviewers(patch, args.repo)

    resolver = UserResolver(
        rules.get_rules().get("github_users", {}), args.group_prefix
    )

    resolved: Iterable[Reviewer] = resolver.resolve_reviewers(reviewers)

    reviewable.add_reviewers(resolved)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select reviewers from Herald rules and git diff",
        epilog="""Example:
            curl https://github.com/mozilla-firefox/infra-testing/pull/30.diff | %(prog)s herald_rules.json""",
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
    main()
