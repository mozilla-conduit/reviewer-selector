import json
from pathlib import Path

HERALD_RULES = Path(__file__).parent.parent / "herald_rules.json"


def test_valid_reviewer_valid_targets():
    """Ensure that all review groups are valid.

    1. Check that neither is a `Restricted Project`. Restricted Projects are
    visible to `All users`, but not to the `Public`. This needs to be fixed in
    Phabricator prior to re-running a crawl.

    2. Ensure that any group mentioned in an add-reviewers rule has a matching
    entry in the groups section.

    """

    with HERALD_RULES.open() as fp:
        herald_rules = json.load(fp)

    rules = herald_rules.get("rules")
    assert rules, f"Missing rules section in {HERALD_RULES}"

    incorrect_rules = []
    all_targets = {}
    for rule in rules:
        rule_id = rule.get("id")
        assert rule_id, f"Missing ID in rule {rule}"

        actions = rule.get("actions")
        assert actions, f"Empty actions for rule {rule_id}"

        targets = {
            r.get("target"): r.get("is_group")
            for a in actions
            for r in a.get("reviewers", [])
            if a.get("type") == "add-reviewers"
        }

        all_targets.update(targets)

        if [t for t in targets if not t or t == "Restricted Project"]:
            incorrect_rules.append(rule_id)

    assert not incorrect_rules, (
        f"Non-public add-reviewers target for rules: {', '.join(incorrect_rules)}"
    )

    groups = herald_rules.get("groups")
    assert groups, f"Missing groups section in {HERALD_RULES}"

    target_groups = {t for t, is_group in all_targets.items() if is_group}

    assert target_groups <= set(groups.keys())
