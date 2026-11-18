from unittest import mock

import pytest

from reviewer_selector.phabricator import PhabricatorRevision
from reviewer_selector.review import Reviewer
from tests.phabricator_double import PhabricatorDouble


@mock.patch("reviewer_selector.phabricator.PhabricatorRevision.get_token_from_env")
@pytest.mark.parametrize(
    "base_url,rest_path,valid",
    (
        ("https://phabricator.services.mozilla.com", "D315229", True),
        ("https://github.com", "mozilla-conduit/reviewer_selector/pulls/18", False),
    ),
)
def test_url_parsing(
    _mock_get_token_from_env: mock.Mock, base_url: str, rest_path: str, valid: bool
):

    url = f"{base_url}/{rest_path}"

    if not valid:
        with pytest.raises(ValueError, match="Not a valid Phabricator revision URL"):
            rev = PhabricatorRevision(url)
        return

    rev = PhabricatorRevision(url)

    assert rev.base_url == base_url
    assert rev.revision_id == rest_path


def test_phabricator_patch_source(
    mock_phabricator_base_url: str,
    mock_phabricator_api_token: str,
    phabdouble: PhabricatorDouble,
):
    patch_text = "Imaa patch!"
    subject = "reviewer_selector: add Phabricator support (bug 2040264)"

    diff = phabdouble.diff(rawdiff=patch_text)
    phabdouble.revision(title=subject, diff=diff)
    phabrev = PhabricatorRevision.from_phid(mock_phabricator_base_url, "PHID-DREV-0")

    assert phabrev.patch_source.get_patch_subject() == subject, (
        "Unexpected patch subject"
    )
    assert phabrev.patch_source.patch == patch_text, "Unexpected patch text"


@mock.patch("reviewer_selector.phabricator.PhabricatorRevision.edit_transaction")
@pytest.mark.parametrize(
    "initial_reviewers,new_reviewers",
    (
        (
            (),
            (
                Reviewer("test-reviewer", False),
                Reviewer("jsmith", False),
                Reviewer("fluent-reviewers", True),
                Reviewer("ent:fluent-reviewers", True),
            ),
        ),
        (
            (
                Reviewer("test-reviewer", False),
                Reviewer("fluent-reviewers", True),
            ),
            (
                Reviewer("jsmith", False),
                Reviewer("ent:fluent-reviewers", True),
            ),
        ),
        (
            (
                Reviewer("test-reviewer", False),
                Reviewer("jsmith", False),
                Reviewer("fluent-reviewers", True),
                Reviewer("ent:fluent-reviewers", True),
            ),
            (),
        ),
    ),
)
def test_phabricator_reviewable(
    mock_edit_transaction: str,
    mock_phabricator_base_url: str,
    mock_phabricator_api_token: str,
    phabdouble: PhabricatorDouble,
    initial_reviewers: list[Reviewer],
    new_reviewers: list[Reviewer],
):
    double_revision = phabdouble.revision()

    all_reviewers = initial_reviewers + new_reviewers
    for reviewer in all_reviewers:
        if reviewer.is_group:
            double_reviewer = phabdouble.project(reviewer.name)
        else:
            double_reviewer = phabdouble.user(username=reviewer.name)

        if reviewer in initial_reviewers:
            phabdouble.reviewer(double_revision, double_reviewer)

    phab_rev = PhabricatorRevision.from_phid(mock_phabricator_base_url, "PHID-DREV-0")

    # initial reviewers present
    for reviewer in initial_reviewers:
        assert reviewer in phab_rev.reviewable.reviewers

    phab_rev.reviewable.add_new_reviewers(new_reviewers)

    reviewer_phids = [r.metadata.get("phid") for r in new_reviewers]

    assert all(reviewer_phids), (
        "All PHIDs should be resolved and recorded when adding new reviewers"
    )

    if new_reviewers:
        mock_edit_transaction.assert_called_once_with("reviewers.add", reviewer_phids)
