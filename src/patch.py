from abc import ABCMeta, abstractmethod
from collections.abc import Mapping, Sequence
import logging
import sys
from typing import Any, override

import rs_parsepatch

logger = logging.getLogger(__name__)


class Patch:
    _patch: str
    _parsed_diffs: Sequence[Mapping[str, Any]]

    def __init__(self, diff: str):
        self._patch = diff
        self._parse_patch()

    def _parse_patch(self):
        self._parsed_diffs = rs_parsepatch.get_diffs(self._patch)

    def get_patch(self):
        return self._patch

    def get_changed_files(self):
        """Extract file paths from git diff."""
        filenames = [d["filename"] for d in self._parsed_diffs]

        logger.info(f"Considering filenames: {', '.join(filenames)} ...")

        return filenames


class PatchSource(metaclass=ABCMeta):
    """An interface for something able to produce a unified diff,
    with optional path metadata header."""

    @abstractmethod
    def fetch_patch(self) -> str:
        """Return a patch from this source."""


class StdinPatchSource(PatchSource):
    @override
    def fetch_patch(self) -> str:
        return sys.stdin.read()
