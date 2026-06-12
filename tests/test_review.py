from reviewer_selector.review import Reviewer, UserResolver


def test_user_resolves_user_to_github(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {Reviewer("jsmith", False)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("jsmith-gh", False) in resolved


def test_user_prefixes_groups(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {
        Reviewer("fluent-reviewers", True),
        Reviewer("/ent:fluent-reviewers", True),
    }

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("#fluent-reviewers", True) in resolved
    assert Reviewer("/ent:fluent-reviewers", True) in resolved


def test_user_custom_group_prefix(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "@")
    reviewers = {
        Reviewer("fluent-reviewers", True),
        Reviewer("/ent:fluent-reviewers", True),
    }

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("@fluent-reviewers", True) in resolved
    assert Reviewer("/ent:fluent-reviewers", True) in resolved


def test_user_skips_unresolved_users(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {Reviewer("unknown-user", False)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert len(list(resolved)) == 0


def test_user_mixed_users_and_groups(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {Reviewer("jsmith", False), Reviewer("fluent-reviewers", True)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert Reviewer("jsmith-gh", False) in resolved
    assert Reviewer("#fluent-reviewers", True) in resolved
