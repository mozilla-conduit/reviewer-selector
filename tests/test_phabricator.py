import pytest

from reviewer_selector import PhabricatorRevision


@pytest.mark.parametrize(
    "base_url,rest_path,valid",
    (
        ("https://phabricator.services.mozilla.com", "D315229", True),
        ("https://github.com", "mozilla-conduit/reviewer_selector/pulls/18", False),
    ),
)
def test_url_parsing(base_url: str, rest_path: str, valid: bool):

    url = f"{base_url}/{rest_path}"

    if not valid:
        with pytest.raises(ValueError, match="Not a valid Phabricator revision URL"):
            rev = PhabricatorRevision(url)
        return

    rev = PhabricatorRevision(url)

    assert rev.base_url == base_url
    assert rev.revision_id == rest_path
