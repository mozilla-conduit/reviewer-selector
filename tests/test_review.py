from collections.abc import Iterable
from unittest import mock

import pytest

from reviewer_selector import StdoutReviewable
from reviewer_selector.review import AddReviewersStatus, MappingUserResolver, Reviewer


def test_reviewer_hashable():
    r = Reviewer("bob", is_group=False)
    rbis = Reviewer("bob", is_group=False)
    rgroup = Reviewer("bob", is_group=True)
    rgroupbis = Reviewer("bob", is_group=True, _members=[r])

    assert r == rbis, "Equal reviewers don't compare as equal"
    assert len({r, rbis}) == 1, "Equal reviewers duplicated in set"
    assert r != rgroup, "User and group with the same name should be different"
    assert len({r, rgroup}) == 2, (
        "User and group with the same name should be retained in set"
    )

    assert rgroup == rgroupbis, (
        "Identical review groups with different members should compare the same"
    )


@pytest.mark.parametrize(
    "input,expected",
    (
        (
            [{Reviewer("alice")}, {Reviewer("bob", blocking=True)}],
            {Reviewer("alice"), Reviewer("bob", blocking=True)},
        ),
    ),
)
def test_reviewer_flatten_merge(
    input: Iterable[set[Reviewer]], expected: set[Reviewer]
):
    flattened = Reviewer.flatten(*input)
    assert len(flattened) == len(expected), (
        "Incorrect number of reviewers after flattening"
    )
    for rev in expected:
        assert rev in flattened, "Flattened set is missing expected reviewers"


@pytest.mark.parametrize(
    "input,expected",
    (
        ([{Reviewer("alice")}], Reviewer("alice")),
        (
            [{Reviewer("alice")}, {Reviewer("alice", blocking=True)}],
            Reviewer("alice", blocking=True),
        ),
        (
            [{Reviewer("alice")}, {Reviewer("alice", _as_groups={"some-group"})}],
            Reviewer("alice", _as_groups={"some-group"}),
        ),
        (
            [
                {
                    Reviewer("group", _members={Reviewer("alice")}),
                    Reviewer("group", _members={Reviewer("bob")}),
                }
            ],
            Reviewer("group", _members={Reviewer("alice"), Reviewer("bob")}),
        ),
    ),
)
def test_reviewer_flatten_properties(
    input: Iterable[set[Reviewer]], expected: Reviewer
):
    flattened = next(iter(Reviewer.flatten(*input)))
    assert flattened == expected, "Reviewers were incorrectly flattened"
    assert flattened.blocking == expected.blocking, (
        "Reviewers blocking were incorrectly flattened"
    )
    if flattened.is_group:
        assert flattened.members == expected.members, (
            "Reviewers members were incorrectly flattened"
        )
    else:
        assert flattened.as_groups == expected.as_groups, (
            "Reviewers as_groups were incorrectly flattened"
        )


def test_reviewer_set_as_groups():
    reviewer = Reviewer("reviewer")

    assert len(reviewer.as_groups) == 0, (
        "Initial reviewer's group stand-in should be empty"
    )

    reviewer.assign_as_groups(["some-group", "some-other-group"])
    assert reviewer.as_groups == {"some-group", "some-other-group"}, (
        "New groups should have been set (as a set)"
    )

    reviewer.assign_as_groups(["some-third-group"])
    assert reviewer.as_groups == {"some-third-group"}, (
        "Groups should have been reset (as a set)"
    )


def test_reviewer_groups_no_as_groups():
    group = Reviewer("group", is_group=True)

    with pytest.raises(ValueError, match="Groups can't stand-in as other groups"):
        _ = group.as_groups

    with pytest.raises(ValueError, match="Groups can't stand-in as other groups"):
        group.assign_as_groups(["another-group"])


def test_reviewer_set_members():
    group = Reviewer("group", is_group=True)

    assert len(group.members) == 0, "Initial group should be empty"

    members = [Reviewer("alice"), Reviewer("bob")]
    group.assign_members(members)

    assert group.members == set(members), "Members shoud have been set (as a set)"

    group.assign_members(members[:1])

    assert group.members == set(members[:1]), "Members shoud have been reset (as a set)"


def test_reviewer_individuals_no_members():
    reviewer = Reviewer("alice")

    with pytest.raises(ValueError, match="Individual reviewers don't have members"):
        _test = reviewer.members

    with pytest.raises(ValueError, match="Individual reviewers don't have members"):
        reviewer.assign_members([Reviewer("bob")])


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

    added = sr.add_reviewers([r])

    outerr = capsys.readouterr()

    assert added == 1
    assert r in sr.reviewers
    assert outerr.out.strip() == "bob"


def test_stdout_reviewable_add_new_reviewers():
    sr = StdoutReviewable()

    alice = Reviewer("alice")
    sr.add_reviewers([alice])

    sr.add_reviewers = mock.MagicMock()
    sr.add_reviewers.return_value = 1

    bob = Reviewer("bob")
    status = sr.add_new_reviewers([alice, bob])

    sr.add_reviewers.assert_called_with([bob])
    assert status == AddReviewersStatus(1, True)
