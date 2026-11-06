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


def test_phabricator_reviewable(
    mock_phabricator_base_url: str,
    mock_phabricator_api_token: str,
    phabdouble: PhabricatorDouble,
):
    rev = phabdouble.revision()
    test_reviewer = phabdouble.user(username="test-reviewer")
    fluent_reviewers = phabdouble.project("fluent_reviewers")
    phabdouble.reviewer(rev, test_reviewer)
    phabdouble.reviewer(rev, fluent_reviewers)

    phabrev = PhabricatorRevision.from_phid(mock_phabricator_base_url, "PHID-DREV-0")

    reviewers = phabrev.reviewable.reviewers

    assert Reviewer("test-reviewer") in reviewers
    assert Reviewer("fluent_reviewers", is_group=True) in reviewers

    # add_reviewers

    # add_new_reviewers

    # all users and teams present
