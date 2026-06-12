from reviewer_selector.review import UserResolver


def test_user_resolves_user_to_github(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {("jsmith", False)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert ("jsmith-gh", False) in resolved


def test_user_prefixes_groups(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {("fluent-reviewers", True), ("/ent:fluent-reviewers", True)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert ("#fluent-reviewers", True) in resolved
    assert ("/ent:fluent-reviewers", True) in resolved


def test_user_custom_group_prefix(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "@")
    reviewers = {("fluent-reviewers", True), ("/ent:fluent-reviewers", True)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert ("@fluent-reviewers", True) in resolved
    assert ("/ent:fluent-reviewers", True) in resolved


def test_user_skips_unresolved_users(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {("unknown-user", False)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert len(list(resolved)) == 0


def test_user_mixed_users_and_groups(sample_rules_data: dict):
    resolver = UserResolver(sample_rules_data["github_users"], "#")
    reviewers = {("jsmith", False), ("fluent-reviewers", True)}

    resolved = resolver.resolve_reviewers(reviewers)

    assert ("jsmith-gh", False) in resolved
    assert ("#fluent-reviewers", True) in resolved
