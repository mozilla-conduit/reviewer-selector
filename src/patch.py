from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence
import logging
import sys
from typing import Any, override

import rs_parsepatch

logger = logging.getLogger(__name__)


class Patch:
    """Wrapper around patch data, with optional path metadata header."""
    _patch: str
    _parsed_diffs: Sequence[Mapping[str, Any]]

    def __init__(self, diff: str):
        self._patch = diff
        self._parse_patch()

    def _parse_patch(self):
        self._parsed_diffs = rs_parsepatch.get_diffs(self._patch)

    def get_patch(self):
        """Get the raw patch data."""
        return self._patch

    def get_changed_files(self):
        """Get the list of modified file paths."""
        filenames = [d["filename"] for d in self._parsed_diffs]

        logger.info(f"Considering filenames: {', '.join(filenames)} ...")

        return filenames


class PatchSource(metaclass=ABCMeta):
    """An interface for something able to produce Patch data."""

    @abstractmethod
    def fetch_patch(self) -> str:
        """Return a patch from this source."""


class StdinPatchSource(PatchSource):
    """A PatchSource implementation reading a diff from STDIN."""
    @override
    def fetch_patch(self) -> str:
        return sys.stdin.read()
