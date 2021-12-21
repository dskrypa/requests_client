"""
Facilitates submission of multiple requests for different endpoints to a single server.

:author: Doug Skrypa
"""

import logging
import re
from functools import cached_property
from typing import Optional, Union, Callable, MutableMapping, Any, Mapping
from urllib.parse import urlencode, urlparse

from .utils import UrlPart, RequestMethod, format_path_prefix

__all__ = ['BaseClient']
log = logging.getLogger(__name__)
Bool = Union[bool, Any]


class BaseClient:
    scheme = UrlPart()
    host = UrlPart()
    port = UrlPart(lambda v: int(v) if v is not None else v)
    path_prefix = UrlPart(format_path_prefix)

    def __init__(
        self,
        host_or_url: str,
        port: Union[int, str, None] = None,
        *,
        scheme: str = None,
        path_prefix: str = None,
        raise_errors: Bool = True,
        exc: Callable = None,
        headers: MutableMapping[str, Any] = None,
        verify: Union[None, str, bool] = None,
        log_lvl: int = logging.DEBUG,
        log_params: Bool = True,
        nopath: Bool = False,
        **kwargs,
    ):
        if host_or_url and re.match('^[a-zA-Z]+://', host_or_url):  # If it begins with a scheme, assume it is a url
            parsed = urlparse(host_or_url)
            self.host = parsed.hostname
            port = port or parsed.port
            scheme = scheme or parsed.scheme
            path_prefix = path_prefix if nopath else path_prefix or parsed.path
        else:
            self.host = host_or_url
            if self.host and ':' in self.host and port:
                raise ValueError(f'Conflicting arguments: port provided twice (host_or_url={self.host!r}, {port=})')

        self.scheme = scheme or 'http'
        self.port = port
        self.path_prefix = path_prefix
        self.raise_errors = raise_errors
        self._headers = headers or {}
        self._verify = verify
        self.log_lvl = log_lvl
        self.log_params = log_params
        self._session_kwargs = kwargs
        self.exc = exc

    def __repr__(self) -> str:
        return '<{}[{}]>'.format(self.__class__.__name__, self.url_for(''))

    @cached_property
    def _url_fmt(self) -> str:
        host_port = f'{self.host}:{self.port}' if self.port else self.host
        return f'{self.scheme}://{host_port}/{{}}'

    def url_for(self, path: str, params: Mapping[str, Any] = None, relative: Bool = True) -> str:
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
            url = '{}?{}'.format(url, urlencode(params, True))
        return url

    def _log_req(
        self, method: str, url: str, path: str, relative: Bool, params: Optional[Mapping[str, Any]], log_params: Bool
    ):
        if params and (log_params or (log_params is None and self.log_params)):
            url = self.url_for(path, params, relative=relative)
        log.log(self.log_lvl, f'{method} -> {url}')

    get = RequestMethod()
    put = RequestMethod()
    post = RequestMethod()
    delete = RequestMethod()
    options = RequestMethod()
    head = RequestMethod()
    patch = RequestMethod()
