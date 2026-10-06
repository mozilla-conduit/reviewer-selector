import json
from pathlib import Path

HERALD_RULES = Path(__file__).parent.parent / "herald_rules.json"


def test_valid_reviewer_target():
    with open(HERALD_RULES, "r") as fp:
        herald_rules = json.load(fp)

    rules = herald_rules.get("rules")
    assert rules, f"Missing rules section in {HERALD_RULES}"

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

        assert not (any(not t or t == "Restricted Project" for t in targets)), (
            f"Incorrect add-reviewers target for rule {rule_id}"
        )
