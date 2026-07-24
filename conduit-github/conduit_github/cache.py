import functools
from typing import (
    Callable,
    TypeVar,
)

# Generic type representing the content being cached.
T = TypeVar("T")


def cache_method(
    key_fn: Callable[..., str],
    cache_alias: str = "default",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Cache the method result using the key function.

    This method fakes it all with functools.lru_cache
    """

    return functools.lru_cache
