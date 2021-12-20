"""
Misc utilities.

:author: Doug Skrypa
"""

import logging
import os
from functools import wraps, partial
from operator import attrgetter
from threading import Lock
from time import sleep, monotonic
from typing import Optional, Callable

__all__ = ['proxy_bypass_append', 'rate_limited', 'format_path_prefix']
log = logging.getLogger(__name__)


class UrlPart:
    """Part of a URL.  Enables cached values that rely on this value to be reset if this value is changed"""

    def __init__(self, formatter: Callable = None):
        self.formatter = formatter

    def __set_name__(self, owner, name):
        self.name = name  # Note: when both __get__ and __set__ are defined, descriptor takes precedence over __dict__

    def __get__(self, instance, owner):
        try:
            return instance.__dict__.get(self.name)
        except AttributeError:
            return self

    def __set__(self, instance, value):
        if self.formatter is not None:
            value = self.formatter(value)
        instance.__dict__[self.name] = value
        try:
            del instance.__dict__['_url_fmt']
        except KeyError:
            pass


class RequestMethod:
    """A request method.  Allows subclasses to override the ``request`` method and have this method call it."""

    def __set_name__(self, owner, name):
        self.method = name.upper()

    def __get__(self, instance, owner):
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


def rate_limited(interval: float = 0, log_lvl: int = logging.DEBUG):
    """
    :param interval: Interval between allowed invocations in seconds
    :param log_lvl: The log level that should be used to indicate that the wrapped function is being delayed
    """
    # noinspection PyTypeChecker
    is_attrgetter = isinstance(interval, (attrgetter, str))
    if is_attrgetter:
        interval = attrgetter(interval) if isinstance(interval, str) else interval

    def decorator(func):
        last_call = 0
        lock = Lock()
        log_fmt = 'Rate limited {} {!r} is being delayed {{:,.3f}} seconds'.format(
            'method' if is_attrgetter else 'function', func.__name__
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_call, lock
            obj_interval = interval(args[0]) if is_attrgetter else interval  # noqa
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


def format_path_prefix(value: Optional[str]) -> str:
    if value:
        value = value if not value.startswith('/') else value[1:]
        return value if value.endswith('/') else value + '/'
    return ''
