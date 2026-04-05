"""
Facilitates submission of multiple requests for different endpoints to a single server.

:author: Doug Skrypa
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Mapping, MutableMapping
from urllib.parse import urlencode, urlparse

from .utils import RequestMethod, UrlPart, format_path_prefix

if TYPE_CHECKING:
    from ._typing import Bool, OptStr

__all__ = ['BaseClient']
log = logging.getLogger(__name__)


class BaseClient(ABC):
    scheme: UrlPart[str] = UrlPart()
    host: UrlPart[str] = UrlPart()
    port: UrlPart[int | None] = UrlPart(lambda v: int(v) if v is not None else v)
    path_prefix: UrlPart[str] = UrlPart(format_path_prefix)

    def __init__(
        self,
        host_or_url: str,
        port: int | str | None = None,
        *,
        scheme: OptStr = None,
        path_prefix: OptStr = None,
        raise_errors: Bool = True,
        exc: Callable | None = None,
        headers: MutableMapping[str, Any] | None = None,
        verify: None | str | bool = None,
        log_lvl: int = logging.DEBUG,
        log_params: Bool = True,
        log_data: Bool = False,
        nopath: Bool = False,
        **kwargs,
    ):
        self.host, port, scheme, path_prefix = _normalize_args(host_or_url, port, scheme, path_prefix, nopath)
        self.scheme = scheme or 'http'
        self.port = port
        self.path_prefix = path_prefix
        self.raise_errors = raise_errors
        self._headers = headers or {}
        self._verify = verify
        self.log_lvl = log_lvl
        self.log_params = log_params
        self.log_data = log_data
        self._session_kwargs = kwargs
        self.exc = exc

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.url_for("")}]>'

    @cached_property
    def _url_fmt(self) -> str:
        host_port = f'{self.host}:{self.port}' if self.port else self.host
        return f'{self.scheme}://{host_port}/{{}}'

    def url_for(self, path: str, params: Mapping[str, Any] | None = None, relative: Bool = True) -> str:
        """
        :param path: The URL path to retrieve
        :param params: Request query parameters
        :param relative: Whether the stored :attr:`.path_prefix` should be used
        :return: The full URL for the given path
        """
        if not relative and path.startswith(('http://', 'https://')):
            url = path
        else:
            path = path[1:] if path.startswith('/') else path
            url = self._url_fmt.format(self.path_prefix + path if relative else path)
        if params:
            url = f'{url}?{urlencode(params, True)}'
        return url

    def _log_req(
        self,
        method: str,
        url: str,
        path: str = '',
        relative: Bool = True,
        params: Mapping[str, Any] | None = None,
        log_params: Bool = None,
        log_data: Bool = None,
        kwargs: Mapping[str, Any] | None = None,
    ):
        if params and (log_params or (log_params is None and self.log_params)):
            url = self.url_for(path, params, relative=relative)

        data_repr = _get_data_repr(log_data or (log_data is None and self.log_data), kwargs)
        log.log(self.log_lvl, f'{method} -> {url}{data_repr}')

    get = RequestMethod()
    put = RequestMethod()
    post = RequestMethod()
    delete = RequestMethod()
    options = RequestMethod()
    head = RequestMethod()
    patch = RequestMethod()

    @abstractmethod
    def request(
        self,
        method: str,
        path: str,
        *,
        relative: Bool = True,
        raise_errors: Bool = None,
        log: Bool = True,  # noqa
        log_params: Bool = None,
        log_data: Bool = None,
        **kwargs,
    ):
        raise NotImplementedError


def _get_data_repr(should_log: Bool, kwargs: Mapping[str, Any] | None) -> str:
    if should_log and kwargs:
        if data := kwargs.get('data') or kwargs.get('json'):
            return f' < {data=}'  # noqa

    return ''


def _normalize_args(
    host_or_url: str, port: int | OptStr, scheme: OptStr, path_prefix: OptStr, nopath: Bool
) -> tuple[str, int | OptStr, OptStr, OptStr]:
    if host_or_url and re.match('^[a-zA-Z]+://', host_or_url):  # If it begins with a scheme, assume it is a url
        parsed = urlparse(host_or_url)
        if not nopath and not path_prefix:
            path_prefix = parsed.path

        return parsed.hostname, port or parsed.port, scheme or parsed.scheme, path_prefix  # type: ignore[return-value]

    if host_or_url and ':' in host_or_url and port:
        raise ValueError(f'Conflicting arguments: port provided twice ({host_or_url=}, {port=})')

    return host_or_url, port, scheme, path_prefix
