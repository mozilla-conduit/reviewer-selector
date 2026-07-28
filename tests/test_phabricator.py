from unittest import mock

import pytest

from reviewer_selector.phabricator import PhabricatorRevision


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
