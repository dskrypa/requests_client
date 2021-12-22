"""
Facilitates submission of multiple requests for different endpoints to a single server.

:author: Doug Skrypa
"""

import logging
import warnings
from asyncio import Lock, sleep
from time import monotonic
from typing import Union, Callable, MutableMapping, Any, Awaitable

from httpx import AsyncClient, HTTPError, Response
from httpx._client import ClientState

from .base import BaseClient, Bool
from .user_agent import generate_user_agent, USER_AGENT_SCRIPT_CONTACT_OS

__all__ = ['AsyncRequestsClient']
log = _log = logging.getLogger(__name__)


class AsyncRequestsClient(BaseClient):
    """
    Facilitates submission of multiple requests for different endpoints to a single server.

    :param str host_or_url: A hostname or host:port, or a URL from which the scheme, host, port, and path_prefix should
      be derived.
    :param str|int port: A port
    :param str scheme: The URI scheme to use (http, https, etc.) (default: http)
    :param str path_prefix: A URI path prefix to include on all URLs.  If provided, it may be overridden on a
      per-request basis.  A ``/`` will be added to the beginning and end if it was not included.
    :param bool raise_errors: Whether :meth:`Response.raise_for_status<httpx.Response.raise_for_status>` should
      be used to raise an exception if a response has a 4xx/5xx status code.  This may be overridden on a per-request
      basis.
    :param class exc: A custom exception class to raise when an error is encountered.  Its init method must accept two
      positional arguments: ``cause`` (either a :class:`Response<httpx.Response>` or a :class:`RequestException
      <httpx.HTTPError>` / a subclass thereof) and ``url`` (string).  When a response has a 4xx/5xx status
      code and ``raise_errors`` is True, then the exception will be initialized with the response object.  For
      non-code-based exceptions, the exception will be initialized with the original exception.
    :param dict headers: Headers that should be included in the session.
    :param bool|str verify: Allows the ``verify`` option to be specified at a session level.  See the documentation for
      :func:`httpx.request` for more information.
    :param str|None user_agent_fmt: A format string to be used to generate the ``User-Agent`` header.  If a custom value
      already exists in the provided ``headers``, then this format is not used.
    :param int log_lvl: Log level to use when logging messages about the method/url when requests are made
    :param bool log_params: Include query params in logged messages when requests are made
    :param float rate_limit: Interval in seconds to wait between requests (default: no rate limiting).  If specified,
      then a lock is used to prevent concurrent requests.
    :param callable session_fn: A callable that returns a :class:`AsyncClient<httpx.AsyncClient>` object.  Defaults to
      the normal constructor for :class:`AsyncClient<httpx.AsyncClient>`.  Allows users to perform other initialization
      tasks for the session, such as adding an auth handler.
    :param bool local_sessions: By default, sessions are shared between threads.  If this is specified, then sessions
      are stored locally in each thread.
    :param bool nopath: When initialized with a URL, ignore the path portion
    :param kwargs: Keyword arguments to pass to the given ``session_fn`` whenever a new session is initialized.  The
      default constructor does not accept any arguments, so these should only be provided if ``session_fn`` is also
      specified.
    """

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
        user_agent_fmt: str = USER_AGENT_SCRIPT_CONTACT_OS,
        log_lvl: int = logging.DEBUG,
        log_params: Bool = True,
        log_data: Bool = False,
        rate_limit: float = 0,
        session_fn: Callable = AsyncClient,
        nopath: Bool = False,
        **kwargs,
    ):
        super().__init__(
            host_or_url,
            port,
            scheme=scheme,
            path_prefix=path_prefix,
            raise_errors=raise_errors,
            exc=exc,
            headers=headers,
            verify=verify,
            log_lvl=log_lvl,
            log_params=log_params,
            log_data=log_data,
            nopath=nopath,
            **kwargs,
        )
        if user_agent_fmt:
            self._headers.setdefault('User-Agent', generate_user_agent(user_agent_fmt, httpx=True))
        self._session_fn = session_fn
        self._lock = Lock()
        self.__session = None  # type: AsyncClient | None
        self._rate_limit = rate_limit
        self._last_req = 0

    async def _init_session(self) -> AsyncClient:
        session = self._session_fn(**self._session_kwargs)
        session.headers.update(self._headers)
        if self._verify is not None:
            session.verify = self._verify
        return session

    async def get_session(self) -> AsyncClient:
        """
        Initializes a new session using the provided ``session_fn``, or returns the already created one if it already
        exists.

        :return: The :class:`AsyncClient<httpx.AsyncClient>` that will be used for requests
        """
        async with self._lock:
            if self.__session is None:
                self.__session = await self._init_session()
            return self.__session

    async def set_session(self, value: AsyncClient, close: bool = True):
        async with self._lock:
            if close and self.__session is not None:
                await self.__session.aclose()
            self.__session = value

    @property
    def session(self) -> Awaitable[AsyncClient]:
        """
        Initializes a new session using the provided ``session_fn``, or returns the already created one if it already
        exists.

        :return: The :class:`AsyncClient<httpx.AsyncClient>` that will be used for requests
        """
        return self.get_session()

    async def request(
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
    ) -> Response:
        """
        Submit a request to the URL based on the given path, using the given HTTP method.

        :param method: HTTP method to use (GET/PUT/POST/etc.)
        :param path: The URL path to retrieve
        :param relative: Whether the stored :attr:`.path_prefix` should be used
        :param raise_errors: Whether :meth:`Response.raise_for_status<httpx.Response.raise_for_status>` should
          be used to raise an exception if the response has a 4xx/5xx status code.  Overrides the setting stored when
          initializing :class:`AsyncRequestsClient`, if provided.  Setting this to False does not prevent exceptions
          caused by anything other than 4xx/5xx errors from being raised.
        :param log: Whether a message should be logged with the method and url.  The log level is set when
          initializing :class:`AsyncRequestsClient`.
        :param log_params: Whether query params should be logged, if ``log=True``.  Overrides the setting stored when
          initializing :class:`AsyncRequestsClient`, if provided.
        :param log_data: Whether POST/PUT data should be logged, if ``log=True``.  Overrides the setting stored when
          initializing :class:`AsyncRequestsClient`, if provided.
        :param kwargs: Keyword arguments to pass to :meth:`AsyncClient.request<httpx.AsyncClient.request>`
        :return: The :class:`Response<httpx.Response>` to the request
        :raises: :class:`HTTPError<httpx.HTTPError>` (or a subclass thereof) if the request failed.  If
          the exception is caused by an HTTP error code, then a :class:`HTTPError<httpx.HTTPError>` will be raised,
          and the code can be accessed via the exception's ``.response.status_code`` attribute. If the exception is due
          to a request or connection timeout, then a :class:`Timeout<httpx.Timeout>` (or further subclass thereof)
          will be raised, and the exception will not have a ``response`` property.
        """
        url = self.url_for(path, relative=relative)
        if rate_limit := self._rate_limit:
            elapsed = monotonic() - self._last_req
            if (wait := rate_limit - elapsed) > 0:
                if log:
                    _log.log(self.log_lvl, f'Delaying request {wait:.2f} seconds due to {rate_limit=}')
                await sleep(wait)

        if log:
            self._log_req(method, url, path, relative, kwargs.get('params'), log_params, log_data, kwargs)

        raise_on_code = raise_errors or (raise_errors is None and self.raise_errors)
        try:
            if self.exc:
                try:
                    resp = await (await self.session).request(method, url, **kwargs)
                except HTTPError as e:
                    raise self.exc(e, url)
                else:
                    if raise_on_code and 400 <= resp.status_code < 600:
                        raise self.exc(resp, url)
            else:
                resp = await (await self.session).request(method, url, **kwargs)
                if raise_on_code:
                    resp.raise_for_status()
        finally:
            self._last_req = monotonic()
        return resp

    async def aclose(self):
        async with self._lock:
            if self.__session is not None:
                await self.__session.aclose()
                self.__session = None

    def __del__(self):
        if self.__session is not None and getattr(self.__session, '_state', None) == ClientState.OPENED:
            warnings.warn(f'Unclosed {self!r} - it is not possible to close synchronously - need to close explicitly')

    async def __aenter__(self) -> 'AsyncRequestsClient':
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()
