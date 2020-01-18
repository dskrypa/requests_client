"""
Misc utilities.

:author: Doug Skrypa
"""

import functools
import logging
import os
import threading
import time
from operator import attrgetter

__all__ = ['proxy_bypass_append', 'rate_limited', 'format_path_prefix']
log = logging.getLogger(__name__)


def proxy_bypass_append(host):
    """
    Adds the given host to os.environ['no_proxy'] if it was not already present.  This environment variable is used by
    the Requests library to disable proxies for requests to particular hosts.

    :param str host: A host to add to os.environ['no_proxy']
    """
    if 'no_proxy' not in os.environ:
        os.environ['no_proxy'] = host
    elif host not in os.environ['no_proxy']:
        os.environ['no_proxy'] += ',' + host


def rate_limited(interval=0, log_lvl=logging.DEBUG):
    """
    :param float interval: Interval between allowed invocations in seconds
    :param int log_lvl: The log level that should be used to indicate that the wrapped function is being delayed
    """
    is_attrgetter = isinstance(interval, (attrgetter, str))
    if is_attrgetter:
        interval = attrgetter(interval) if isinstance(interval, str) else interval

    def decorator(func):
        last_call = 0
        lock = threading.Lock()
        log_fmt = 'Rate limited {} {!r} is being delayed {{:,.3f}} seconds'.format(
            'method' if is_attrgetter else 'function', func.__name__
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_call, lock
            obj_interval = interval(args[0]) if is_attrgetter else interval
            with lock:
                elapsed = time.monotonic() - last_call
                if elapsed < obj_interval:
                    wait = obj_interval - elapsed
                    log.log(log_lvl, log_fmt.format(wait))
                    time.sleep(wait)
                last_call = time.monotonic()
                return func(*args, **kwargs)
        return wrapper
    return decorator


def format_path_prefix(value):
    if value:
        value = value if not value.startswith('/') else value[1:]
        return value if value.endswith('/') else value + '/'
    return ''
