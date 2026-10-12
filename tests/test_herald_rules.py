import json
from pathlib import Path

HERALD_RULES = Path(__file__).parent.parent / "herald_rules.json"


def test_valid_reviewer_target():
    with HERALD_RULES.open() as fp:
        herald_rules = json.load(fp)

    rules = herald_rules.get("rules")
    assert rules, f"Missing rules section in {HERALD_RULES}"

    incorrect_rules = []
    for rule in rules:
        rule_id = rule.get("id")
        assert rule_id, f"Missing ID in rule {rule}"

        actions = rule.get("actions")
        assert actions, f"Empty actions for rule {rule_id}"

        targets = [
            r.get("target")
            for a in actions
            for r in a.get("reviewers", [])
            if a.get("type") == "add-reviewers"
        ]

        if [t for t in targets if not t or t == "Restricted Project"]:
            incorrect_rules.append(rule_id)

    assert not incorrect_rules, (
        f"Incorrect add-reviewers target for rules: {', '.join(incorrect_rules)}"
    )
