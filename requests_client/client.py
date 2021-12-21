"""
Facilitates submission of multiple requests for different endpoints to a single server.

:author: Doug Skrypa
"""

import logging
import threading
from typing import Union, Callable, MutableMapping, Any
from weakref import finalize

import requests
from requests import RequestException

from .base import BaseClient
from .user_agent import generate_user_agent, USER_AGENT_SCRIPT_CONTACT_OS
from .utils import rate_limited

__all__ = ['RequestsClient']
log = logging.getLogger(__name__)
Bool = Union[bool, Any]


class RequestsClient(BaseClient):
    """
    Facilitates submission of multiple requests for different endpoints to a single server.

    :param str host_or_url: A hostname or host:port, or a URL from which the scheme, host, port, and path_prefix should
      be derived.
    :param str|int port: A port
    :param str scheme: The URI scheme to use (http, https, etc.) (default: http)
    :param str path_prefix: A URI path prefix to include on all URLs.  If provided, it may be overridden on a
      per-request basis.  A ``/`` will be added to the beginning and end if it was not included.
    :param bool raise_errors: Whether :meth:`Response.raise_for_status<requests.Response.raise_for_status>` should
      be used to raise an exception if a response has a 4xx/5xx status code.  This may be overridden on a per-request
      basis.
    :param class exc: A custom exception class to raise when an error is encountered.  Its init method must accept two
      positional arguments: ``cause`` (either a :class:`Response<requests.Response>` or a :class:`RequestException
      <requests.RequestException>` / a subclass thereof) and ``url`` (string).  When a response has a 4xx/5xx status
      code and ``raise_errors`` is True, then the exception will be initialized with the response object.  For
      non-code-based exceptions, the exception will be initialized with the original exception.
    :param dict headers: Headers that should be included in the session.
    :param bool|str verify: Allows the ``verify`` option to be specified at a session level.  See the documentation for
      :func:`requests.request` for more information.
    :param str|None user_agent_fmt: A format string to be used to generate the ``User-Agent`` header.  If a custom value
      already exists in the provided ``headers``, then this format is not used.
    :param int log_lvl: Log level to use when logging messages about the method/url when requests are made
    :param bool log_params: Include query params in logged messages when requests are made
    :param float rate_limit: Interval in seconds to wait between requests (default: no rate limiting).  If specified,
      then a lock is used to prevent concurrent requests.
    :param callable session_fn: A callable that returns a :class:`Session<requests.Session>` object.  Defaults to the
      normal constructor for :class:`Session<requests.Session>`.  Allows users to perform other initialization tasks for
      the session, such as adding an auth handler.
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
        rate_limit: float = 0,
        session_fn: Callable = requests.Session,
        local_sessions: Bool = False,
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
            nopath=nopath,
            **kwargs,
        )
        if user_agent_fmt:
            self._headers.setdefault('User-Agent', generate_user_agent(user_agent_fmt))
        self._session_fn = session_fn
        self._lock = None if local_sessions else threading.Lock()
        self._local = threading.local() if local_sessions else None
        self.__session = None
        self.__finalizer = finalize(self, self.__close)
        if rate_limit:
            self.request = rate_limited(rate_limit)(self.request)

    def _init_session(self) -> requests.Session:
        session = self._session_fn(**self._session_kwargs)
        session.headers.update(self._headers)
        if self._verify is not None:
            session.verify = self._verify
        if not self.__finalizer.alive:
            self.__finalizer = finalize(self, self.__close)
        return session

    @property
    def session(self) -> requests.Session:
        """
        Initializes a new session using the provided ``session_fn``, or returns the already created one if it already
        exists.

        :return: The :class:`Session<requests.Session>` that will be used for requests
        """
        if self._lock:
            with self._lock:
                if self.__session is None:
                    self.__session = self._init_session()
                return self.__session
        else:
            try:
                return self._local.session
            except AttributeError:
                self._local.session = self._init_session()
                return self._local.session

    @session.setter
    def session(self, value: requests.Session):
        if self._lock:
            with self._lock:
                self.__session = value
        else:
            self._local.session = value

    def request(
        self,
        method: str,
        path: str,
        *,
        relative: Bool = True,
        raise_errors: Bool = None,
        log: Bool = True,  # noqa
        log_params: Bool = None,
        **kwargs,
    ) -> requests.Response:
        """
        Submit a request to the URL based on the given path, using the given HTTP method.

        :param method: HTTP method to use (GET/PUT/POST/etc.)
        :param path: The URL path to retrieve
        :param relative: Whether the stored :attr:`.path_prefix` should be used
        :param raise_errors: Whether :meth:`Response.raise_for_status<requests.Response.raise_for_status>` should
          be used to raise an exception if the response has a 4xx/5xx status code.  Overrides the setting stored when
          initializing :class:`RequestsClient`, if provided.  Setting this to False does not prevent exceptions caused
          by anything other than 4xx/5xx errors from being raised.
        :param log: Whether a message should be logged with the method and url.  The log level is set when
          initializing :class:`RequestsClient`.
        :param log_params: Whether query params should be logged, if ``log=True``.  Overrides the setting stored
          when initializing :class:`RequestsClient`, if provided.
        :param kwargs: Keyword arguments to pass to :meth:`Session.request<requests.Session.request>`
        :return: The :class:`Response<requests.Response>` to the request
        :raises: :class:`RequestException<requests.RequestException>` (or a subclass thereof) if the request failed.  If
          the exception is caused by an HTTP error code, then a :class:`HTTPError<requests.HTTPError>` will be raised,
          and the code can be accessed via the exception's ``.response.status_code`` attribute. If the exception is due
          to a request or connection timeout, then a :class:`Timeout<requests.Timeout>` (or further subclass thereof)
          will be raised, and the exception will not have a ``response`` property.
        """
        url = self.url_for(path, relative=relative)
        if log:
            self._log_req(method, url, path, relative, kwargs.get('params'), log_params)

        raise_on_code = raise_errors or (raise_errors is None and self.raise_errors)
        if self.exc:
            try:
                resp = self.session.request(method, url, **kwargs)
            except RequestException as e:
                raise self.exc(e, url)
            else:
                if raise_on_code and 400 <= resp.status_code < 600:
                    raise self.exc(resp, url)
        else:
            resp = self.session.request(method, url, **kwargs)
            if raise_on_code:
                resp.raise_for_status()
        return resp

    def close(self):
        try:
            finalizer = self.__finalizer
        except AttributeError:
            pass  # This happens if an exception was raised in __init__
        else:
            if finalizer.detach():
                self.__close()

    def __del__(self):
        self.close()

    def __close(self):
        """Close the session, if it exists"""
        if self._lock:
            with self._lock:
                if self.__session is not None:
                    self.__session.close()
                    self.__session = None
        else:
            try:
                self._local.session.close()
                del self._local.session
            except AttributeError:
                pass  # This may happen if a session wasn't created, or if called outside of the thread that created it

    def __enter__(self) -> 'RequestsClient':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
