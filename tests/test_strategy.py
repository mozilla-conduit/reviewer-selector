from reviewer_selector.review import Reviewer
from reviewer_selector.strategies import RoundRobinStrategy


def test_strategy_split_groups():
    u1 = Reviewer("u1")
    u2 = Reviewer("u2")
    g1 = Reviewer("g1", is_group=True)
    g2 = Reviewer("g2", is_group=True)

    strategy = RoundRobinStrategy()

    users, groups = strategy._split_groups([u1, g1, u2, g2])

    assert users == {u1, u2}, "Users should have been splits from groups"
    assert groups == {g1, g2}, "Groups should have been split from users"


def test_round_robin_strategy():
    alice = Reviewer("alice")
    bob = Reviewer("bob")
    charlie = Reviewer("charlie")

    members = {alice, bob}

    group = Reviewer("group-rotation", is_group=True, _members=members)

    rrs = RoundRobinStrategy()

    selected_reviewers = rrs.apply([group])

    assert len(selected_reviewers) == 1, "Only one reviewer should have been selected"
    assert alice in members or bob in members, (
        "Should have selected a reviewer from the members"
    )

    selected_reviewers = rrs.apply([group, charlie])

    assert len(selected_reviewers) == 2, (
        "Should have one individual reviewers and one group stand-in"
    )
    assert charlie in selected_reviewers, "Individual reviewer should still be present"
    assert alice in members or bob in members, (
        "Should have selected a reviewer from the members"
    )


def test_round_robin_strategy_coverage():
    """Ensure that all members are selectable."""
    alice = Reviewer("alice")
    bob = Reviewer("bob")
    charlie = Reviewer("charlie")

    members = {alice, bob, charlie}

    group = Reviewer("group-rotation", is_group=True, _members=members)

    rrs = RoundRobinStrategy()

    # With 3 members, the likelihood of missing one in n tries is (2/3)^n
    tries = 23  # less than 1/1000
    all_selected = set()
    for _ in range(tries):
        all_selected |= rrs.apply([group])

    assert all_selected == members, (
        "Not all possible reviewers got selected (flacky test, rerun)"
    )
