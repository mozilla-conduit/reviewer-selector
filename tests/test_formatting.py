"""
Code Style Tests.
"""

import subprocess

LINT_PATHS = (".",)


def test_ruff():
    passed = []
    for lint_path in LINT_PATHS:
        passed.append(subprocess.call(("ruff", "check", lint_path)) == 0)
    assert all(passed), "ruff did not run cleanly."
