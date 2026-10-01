# This module is the authoritative one from where `version` should be imported.
try:
    from reviewer_selector._version import version
except ImportError:
    version = "unknown version"

USER_AGENT = f"reviewer-selector/{version}"
