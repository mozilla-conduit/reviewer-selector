import pytest

from reviewer_selector.patch import Patch
from reviewer_selector.review import Reviewer


def test_patch_extracts_file_paths(sample_diff: str):
    patch = Patch(sample_diff)
    files = patch.get_changed_files()
    assert list(files) == ["locales/en/messages.ftl"]


def test_patch_handles_multiple_files(sample_diff_multiple_files: str):
    patch = Patch(sample_diff_multiple_files)
    files = patch.get_changed_files()
    assert "file1.py" in files
    assert "dir/file2.js" in files


def test_patch_empty_diff():
    patch = Patch("")
    files = patch.get_changed_files()
    assert files == []


@pytest.mark.parametrize(
    "subject,expected",
    (
        ("a commit message", []),
        ("a commit message r=bob", ["bob"]),
        ("a commit message r?bob", ["bob"]),
        ("a commit message r=#bob", ["#bob"]),
        ("a commit message r?#bob!", ["#bob!"]),
        ("a commit message r=bob,#alice!", ["bob", "#alice!"]),
        (
            "a commit message r?#ent:infra-testing-reviewers,alice!,bob",
            ["#ent:infra-testing-reviewers", "alice!", "bob"],
        ),
        (
            "a commit message r=#ent:infra-testing-reviewers,alice!,bob",
            ["#ent:infra-testing-reviewers", "alice!", "bob"],
        ),
    ),
)
def test_parse_subject_reviewers(subject: str, expected: list[str]):
    assert Patch.parse_subject_reviewers(subject) == expected


@pytest.mark.parametrize(
    "subject,expected",
    (
        ("a commit message", []),
        ("a commit message r=bob", [Reviewer("bob")]),
        ("a commit message r?bob", [Reviewer("bob")]),
        ("a commit message r=#bob", [Reviewer("bob", is_group=True)]),
        (
            "a commit message r?#bob!",
            [Reviewer("bob", is_group=True, blocking=True)],
        ),
        (
            "a commit message r=bob,#alice!",
            [Reviewer("bob"), Reviewer("alice", is_group=True, blocking=True)],
        ),
        (
            "a commit message r?#ent:infra-testing-reviewers,alice!,bob",
            [
                Reviewer("ent:infra-testing-reviewers", is_group=True),
                Reviewer("alice", blocking=True),
                Reviewer("bob"),
            ],
        ),
        (
            "a commit message r=#ent:infra-testing-reviewers,alice!,bob",
            [
                Reviewer("ent:infra-testing-reviewers", is_group=True),
                Reviewer("alice", blocking=True),
                Reviewer("bob"),
            ],
        ),
    ),
)
def test_get_subject_reviewers(subject: str, expected: list[Reviewer]):
    patch = Patch("", subject)
    assert patch.get_subject_reviewers() == expected
