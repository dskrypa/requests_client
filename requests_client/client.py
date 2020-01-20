"""
Facilitates submission of multiple requests for different endpoints to a single server.

:author: Doug Skrypa
"""

import atexit
import logging
import re
import threading
from contextlib import suppress
from itertools import count
from urllib.parse import urlencode, urlparse

import requests
from requests import RequestException

from .compat import cached_property
from .user_agent import generate_user_agent, USER_AGENT_SCRIPT_CONTACT_OS
from .utils import rate_limited, format_path_prefix

__all__ = ['RequestsClient']
log = logging.getLogger(__name__)


class UrlPart:
    """Part of a URL.  Enables cached values that rely on this value to be reset if this value is changed"""
    _counter = count()

    def __init__(self, formatter=None):
        self.name = '_{}#{}'.format(type(self).__name__, next(self._counter))
        self.formatter = formatter

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return getattr(instance, self.name, None)

    def __set__(self, instance, value):
        if self.formatter is not None:
            value = self.formatter(value)
        setattr(instance, self.name, value)
        with suppress(KeyError):
            del instance.__dict__['_url_fmt']


class RequestsClient:
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
    :param kwargs: Keyword arguments to pass to the given ``session_fn`` whenever a new session is initialized.  The
      default constructor does not accept any arguments, so these should only be provided if ``session_fn`` is also
      specified.
    """
    scheme = UrlPart()
    host = UrlPart()
    port = UrlPart(lambda v: int(v) if v is not None else v)
    path_prefix = UrlPart(format_path_prefix)

    def __init__(
            self, host_or_url, port=None, *, scheme=None, path_prefix=None, raise_errors=True, exc=None, headers=None,
            verify=None, user_agent_fmt=USER_AGENT_SCRIPT_CONTACT_OS, log_lvl=logging.DEBUG, log_params=True,
            rate_limit=0, session_fn=requests.Session, local_sessions=False, **kwargs
    ):
        if re.match('^[a-zA-Z]+://', host_or_url):      # If the value begins with a scheme, assume it is a url
            parsed = urlparse(host_or_url)
            self.host = parsed.hostname
            port = port or parsed.port
            scheme = scheme or parsed.scheme
            path_prefix = path_prefix or parsed.path
        else:
            self.host = host_or_url
            if ':' in self.host and port:
                fmt = 'Conflicting arguments: port provided twice (host_or_url={!r}, port={!r})'
                raise ValueError(fmt.format(self.host, port))

        self.scheme = scheme or 'http'
        self.port = port
        self.path_prefix = path_prefix
        self.raise_errors = raise_errors
        self._headers = headers or {}
        if user_agent_fmt:
            self._headers.setdefault('User-Agent', generate_user_agent(user_agent_fmt))
        self._verify = verify
        self.log_lvl = log_lvl
        self.log_params = log_params
        self._session_fn = session_fn
        self._session_kwargs = kwargs
        self.exc = exc
        self._lock = None if local_sessions else threading.Lock()
        self._local = threading.local() if local_sessions else None
        self.__session = None
        if rate_limit:
            self.request = rate_limited(rate_limit)(self.request)

    @cached_property
    def _url_fmt(self):
        host_port = '{}:{}'.format(self.host, self.port) if self.port else self.host
        return '{}://{}/{{}}'.format(self.scheme, host_port)

    def url_for(self, path, params=None, relative=True):
        """
        :param str path: The URL path to retrieve
        :param dict params: Request query parameters
        :param bool relative: Whether the stored :attr:`.path_prefix` should be used
        :return str: The full URL for the given path
        """
        path = path[1:] if path.startswith('/') else path
        url = self._url_fmt.format(self.path_prefix + path if relative else path)
        if params:
            url = '{}?{}'.format(url, urlencode(params, True))
        return url

    def _init_session(self):
        session = self._session_fn(**self._session_kwargs)
        session.headers.update(self._headers)
        if self._verify is not None:
            session.verify = self._verify
        atexit.register(session.close)
        return session

    @property
    def session(self):
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
    def session(self, value):
        if self._lock:
            with self._lock:
                self.__session = value
        else:
            self._local.session = value

    def close(self):
        """Close the session, if it exists"""
        if self._lock:
            with self._lock:
                if self.__session is not None:
                    self.__session.close()
                    atexit.unregister(self.__session.close)
                    self.__session = None
        else:
            self._local.session.close()
            atexit.unregister(self._local.session.close)
            del self._local.session

    def _log_req(self, method, url, path, relative, params, log_params):
        if params and (log_params or (log_params is None and self.log_params)):
            url = self.url_for(path, params, relative=relative)
        log.log(self.log_lvl, '{} -> {}'.format(method, url))

    def request(self, method, path, *, relative=True, raise_errors=None, log=True, log_params=None, **kwargs):
        """
        Submit a request to the URL based on the given path, using the given HTTP method.

        :param str method: HTTP method to use (GET/PUT/POST/etc.)
        :param str path: The URL path to retrieve
        :param bool relative: Whether the stored :attr:`.path_prefix` should be used
        :param bool raise_errors: Whether :meth:`Response.raise_for_status<requests.Response.raise_for_status>` should
          be used to raise an exception if the response has a 4xx/5xx status code.  Overrides the setting stored when
          initializing :class:`RequestsClient`, if provided.  Setting this to False does not prevent exceptions caused
          by anything other than 4xx/5xx errors from being raised.
        :param bool log: Whether a message should be logged with the method and url.  The log level is set when
          initializing :class:`RequestsClient`.
        :param bool log_params: Whether query params should be logged, if ``log=True``.  Overrides the setting stored
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

    def get(self, path, **kwargs):
        return self.request('GET', path, **kwargs)

    def put(self, path, **kwargs):
        return self.request('PUT', path, **kwargs)

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request('DELETE', path, **kwargs)

    def options(self, path, **kwargs):
        return self.request('OPTIONS', path, **kwargs)

    def head(self, path, **kwargs):
        return self.request('HEAD', path, **kwargs)

    def patch(self, path, **kwargs):
        return self.request('PATCH', path, **kwargs)
