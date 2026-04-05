"""
Misc utilities.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import os
import sys
from functools import partial, wraps
from operator import attrgetter
from threading import Lock
from time import monotonic, sleep
from typing import TYPE_CHECKING, Any, Callable, Generic, ParamSpec, Self, TypeVar, overload

if TYPE_CHECKING:
    from requests import Response

    from .base import BaseClient

__all__ = ['proxy_bypass_append', 'rate_limited', 'format_path_prefix']
log = logging.getLogger(__name__)

T = TypeVar('T')
P = ParamSpec('P')

if sys.version_info >= (3, 13):
    U = TypeVar('U', default=str, bound=str | int | None)
else:
    U = TypeVar('U', bound=str | int | None)


class UrlPart(Generic[U]):
    """Part of a URL.  Enables cached values that rely on this value to be reset if this value is changed"""

    __slots__ = ('formatter', 'name')

    def __init__(self, formatter: Callable[[U | str | None], U] | None = None):
        self.formatter = formatter

    def __set_name__(self, owner, name: str):
        self.name = name  # Note: when both __get__ and __set__ are defined, descriptor takes precedence over __dict__

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: Any) -> Self: ...

        @overload
        def __get__(self, instance: object, owner: Any) -> U: ...

    def __get__(self, instance: None | object, owner: Any) -> Self | U:
        if instance is None:
            return self

        return instance.__dict__.get(self.name)  # type: ignore[return-value]

    def __set__(self, instance, value: U | str | None):
        if self.formatter is not None:
            value = self.formatter(value)

        instance.__dict__[self.name] = value
        try:
            del instance.__dict__['_url_fmt']
        except KeyError:
            pass


class RequestMethod:
    """A request method.  Allows subclasses to override the ``request`` method and have this method call it."""

    __slots__ = ('method',)

    def __set_name__(self, owner, name):
        self.method = name.upper()

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: Any) -> Self: ...

        @overload
        def __get__(self, instance: BaseClient, owner: Any) -> Callable[..., Response]: ...

    def __get__(self, instance: None | BaseClient, owner: Any) -> Self | Callable[..., Response]:
        if instance is None:
            return self

        try:
            return partial(instance.request, self.method)
        except AttributeError:
            return self


def proxy_bypass_append(host: str):
    """
    Adds the given host to os.environ['no_proxy'] if it was not already present.  This environment variable is used by
    the Requests library to disable proxies for requests to particular hosts.

    :param host: A host to add to os.environ['no_proxy']
    """
    if 'no_proxy' not in os.environ:
        os.environ['no_proxy'] = host
    elif host not in os.environ['no_proxy']:
        os.environ['no_proxy'] += ',' + host


def rate_limited(
    interval: float | str | attrgetter[float] = 0, log_lvl: int = logging.DEBUG
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    :param interval: Interval between allowed invocations in seconds
    :param log_lvl: The log level that should be used to indicate that the wrapped function is being delayed
    """
    if is_attr_getter := isinstance(interval, (attrgetter, str)):
        interval: attrgetter[float]  # type: ignore[no-redef]
        if isinstance(interval, str):
            interval = attrgetter(interval)

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        last_call: float | int = 0
        lock = Lock()
        log_fmt = 'Rate limited {} {!r} is being delayed {{:,.3f}} seconds'.format(
            'method' if is_attr_getter else 'function', func.__name__
        )

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            nonlocal last_call, lock
            obj_interval: float = interval(args[0]) if is_attr_getter else interval  # type: ignore[operator,assignment]
            with lock:
                elapsed = monotonic() - last_call
                if elapsed < obj_interval:
                    wait = obj_interval - elapsed
                    log.log(log_lvl, log_fmt.format(wait))
                    sleep(wait)
                last_call = monotonic()
                return func(*args, **kwargs)

        return wrapper

    return decorator


def format_path_prefix(value: str | None) -> str:
    if value:
        if value.startswith('/'):
            value = value[1:]
        return value if value.endswith('/') else value + '/'  # noqa

    return ''
