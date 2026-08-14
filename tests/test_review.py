from unittest import mock

import pytest

from reviewer_selector import StdoutReviewable
from reviewer_selector.review import MappingUserResolver, Reviewer


def test_reviewer_hashable():
    r = Reviewer("bob", is_group=False)
    rbis = Reviewer("bob", is_group=False)
    rgroup = Reviewer("bob", is_group=True)

    assert r == rbis, "Equal reviewers don't compare as equal"
    assert len({r, rbis}) == 1, "Equal reviewers duplicated in set"
    assert r != rgroup, "User and group with the same name should be different"
    assert len({r, rgroup}) == 2, (
        "User and group with the same name should be retained in set"
    )


@pytest.mark.parametrize(
    "input,expected",
    (
        ({Reviewer("alice")}, {Reviewer("alice")}),
        (
            {Reviewer("alice"), Reviewer("alice", blocking=True)},
            {Reviewer("alice", blocking=True)},
        ),
        (
            {Reviewer("alice"), Reviewer("bob", blocking=True)},
            {Reviewer("alice"), Reviewer("bob", blocking=True)},
        ),
    ),
)
def test_reviewer_flatten_blocking(input: set[Reviewer], expected: set[Reviewer]):
    assert Reviewer.flatten_blocking(input) == expected, (
        "Blocking reviewers were incorrectly flattened"
    )


def test_user_resolves_user_with_map(sample_rules_data: dict):
    resolver = MappingUserResolver(
        group_prefix="IS_A_GROUP:", user_map=sample_rules_data["github_users"]
    )
    reviewers = {
        Reviewer("jsmith", False),
        Reviewer("fluent-reviewers", True),
    }

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("jsmith-gh", False) in resolved
    assert Reviewer("IS_A_GROUP:fluent-reviewers", True) in resolved


def test_user_prefixes_groups(sample_rules_data: dict):
    resolver = MappingUserResolver()
    reviewers = {
        Reviewer("fluent-reviewers", True),
    }

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("#fluent-reviewers", True) in resolved


def test_user_custom_group_prefix(sample_rules_data: dict):
    resolver = MappingUserResolver("@", sample_rules_data["github_users"])
    reviewers = {
        Reviewer("fluent-reviewers", True),
    }

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("@fluent-reviewers", True) in resolved


def test_user_mixed_users_and_groups(sample_rules_data: dict):
    resolver = MappingUserResolver()
    reviewers = {Reviewer("jsmith", False), Reviewer("fluent-reviewers", True)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("jsmith", False) in resolved
    assert Reviewer("#fluent-reviewers", True) in resolved


def test_stdout_reviewable_add_reviewers(capsys: pytest.CaptureFixture):
    sr = StdoutReviewable()

    r = Reviewer("bob")

    sr.add_reviewers([r])

    outerr = capsys.readouterr()

    assert r in sr.reviewers
    assert outerr.out.strip() == "bob"


def test_stdout_reviewable_add_new_reviewers():
    sr = StdoutReviewable()

    alice = Reviewer("alice")
    sr.add_reviewers([alice])

    sr.add_reviewers = mock.MagicMock()

    bob = Reviewer("bob")
    sr.add_new_reviewers([alice, bob])

    sr.add_reviewers.assert_called_with([bob])
