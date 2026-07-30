from functools import wraps
from typing import Any, Callable

Decoratable = Callable[..., Any]
Decorator = Callable[[Decoratable], Decoratable]
Noneable = Any | None


def instance_cache(cache_attribute: str) -> Decorator:
    """Decorator to cache a method's return on the object.

    `cache_attribute` is the name of any attribute on the object,
    which must be `<ANY> | None`. If None, the `retriever_fn` will be called to populate
    it, otherwise it will be returned as-is.
    """

    def _cache_decorator(retriever_fn: Decoratable) -> Decoratable:
        @wraps(retriever_fn)
        def _instance_cache(self: Any, *args: Any, **kwargs: Any) -> Any:
            if (value := getattr(self, cache_attribute, None)) is None:
                value = retriever_fn(self, *args, **kwargs)
                setattr(self, cache_attribute, value)

            return value

        return _instance_cache

    return _cache_decorator
