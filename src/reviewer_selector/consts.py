# This module is the authoritative one from where `version` should be imported.
from importlib.metadata import version as metadata_version

version = metadata_version("reviewer-selector")

USER_AGENT = f"reviewer-selector/{version}"
