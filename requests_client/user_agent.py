"""
Utilities for setting the User-Agent header for requests.

:author: Doug Skrypa
"""

import inspect
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any

try:
    from httpx import __version__ as httpx_ver
except ImportError:
    httpx_ver = None
try:
    from requests import __version__ as req_ver
except ImportError:
    req_ver = None

from .__version__ import __version__

__all__ = [
    'generate_user_agent',
    'USER_AGENT_LIBS',
    'USER_AGENT_BASIC',
    'USER_AGENT_SCRIPT_CONTACT',
    'USER_AGENT_SCRIPT_CONTACT_OS',
    'USER_AGENT_SCRIPT_OS',
    'USER_AGENT_SCRIPT_URL',
    'USER_AGENT_SCRIPT_URL_OS',
    'USER_AGENT_FIREFOX',
    'USER_AGENT_CHROME',
]
log = logging.getLogger(__name__)

OS_SUMMARIES = {
    'Windows': 'Windows NT 10.0; Win64; x64',
    'Linux': 'X11; Linux x86_64',
    'Darwin': 'Macintosh; Intel Mac OS X 10.15',
}
USER_AGENT_LIBS = '{py_impl}/{py_ver} {lib_name}/{lib_ver} RequestsClient/{rc_ver}'
USER_AGENT_BASIC = '{script}/{script_ver} ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_OS = '{script}/{script_ver} ({os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_CONTACT = '{script}/{script_ver} ({url}; {email}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_URL = '{script}/{script_ver} ({url}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_URL_OS = '{script}/{script_ver} ({url}; {os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_CONTACT_OS = '{script}/{script_ver} ({url}; {email}; {os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_FIREFOX = 'Mozilla/5.0 ({os_info}; rv:{firefox_ver}) Gecko/20100101 Firefox/{firefox_ver}'
USER_AGENT_CHROME = 'Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36'

DEFAULT_VERSION_CHROME = '124.0.0.0'  # While the actual version has minor/rev/etc values, the user agent uses 0s
DEFAULT_VERSION_FIREFOX = '125.0'  # While the actual version has a micro value, the user agent does not include it

_NO_TOP_LEVEL_INFO_LOGGED = False


def generate_user_agent(ua_format: str, downgrade: bool = True, httpx: bool = False, **kwargs) -> str:
    """
    :param ua_format: User agent format string
    :param downgrade: Allow a format downgrade if a given value is missing and a default template is used
    :param httpx: Set to True if using httpx instead of Requests
    :param kwargs: Value overrides or custom keys/values to use
    :return: The user agent string based on the given format and available system information
    """
    arch = platform.architecture()[0]
    if arch.endswith('bit'):
        arch = 'x{}'.format(arch.replace('bit', ''))

    try:
        top_level_name, top_level_globals = _get_top_level_info(inspect.stack())
    except Exception as e:
        if not _in_interactive_session():
            global _NO_TOP_LEVEL_INFO_LOGGED
            if not _NO_TOP_LEVEL_INFO_LOGGED:
                _NO_TOP_LEVEL_INFO_LOGGED = True
                log.debug(f'Error determining top-level script info: {e}')
        top_level_name = 'RequestsClient'
        top_level_globals = {'__version__': __version__}

    top_level_ver = top_level_globals.get('__version__', '1.0')
    url = top_level_globals.get('__url__')
    email = top_level_globals.get('__author_email__')

    uname = platform.uname()
    try:
        os_summary = OS_SUMMARIES[uname.system]
    except KeyError:
        os_summary = f'{uname.system} {uname.release}; {arch}'

    # fmt: off
    info = {
        'script': top_level_name,                       # some_script
        'script_ver': top_level_ver,                    # 1.0
        'url': url,                                     # hxxp://example.org/
        'email': email,                                 # example@fake.org
        'os_name': uname.system,                        # Windows
        'os_rel': uname.release,                        # 10
        'os_info': os_summary,                          # (see above)
        'arch': arch,                                   # x64
        'py_impl': platform.python_implementation(),    # CPython
        'py_ver': platform.python_version(),            # 3.7.4
        'lib_name': 'httpx' if httpx else 'Requests',   # Requests
        'lib_ver': httpx_ver if httpx else req_ver,     # 2.22.0
        'rc_ver': __version__,                          # 2020.01.18
        'firefox_ver': kwargs.pop('firefox_ver', None) or os.environ.get('FIREFOX_VERSION') or DEFAULT_VERSION_FIREFOX,
        'chrome_ver': kwargs.pop('chrome_ver', None) or os.environ.get('CHROME_VERSION') or DEFAULT_VERSION_CHROME,
    }
    # fmt: on
    info.update(kwargs)
    if downgrade:
        url = info.get('url')  # If overridden, use that value
        email = info.get('email')
        if (url is None or email is None) and ua_format == USER_AGENT_SCRIPT_CONTACT_OS:
            ua_format = USER_AGENT_SCRIPT_URL_OS
        if url is None and email:
            info['url'] = email
        if url is None and email is None and ua_format == USER_AGENT_SCRIPT_URL_OS:
            ua_format = USER_AGENT_SCRIPT_OS
    return ua_format.format(**info)


def _in_interactive_session() -> bool:
    # sys.ps1 is only present in interactive sessions - see: https://stackoverflow.com/questions/2356399
    return hasattr(sys, 'ps1')


def _get_top_level_info(stack: list[inspect.FrameInfo]) -> tuple[str, dict[str, Any]]:
    top_level_frame_info = stack[-1]
    top_level_name = Path(inspect.getsourcefile(top_level_frame_info[0])).stem
    top_level_globals = top_level_frame_info.frame.f_globals

    if top_level_name == 'runpy':  # happens when running `python -m unittest tests/*.py`
        for frame_info in reversed(stack):
            frame_path = Path(inspect.getsourcefile(frame_info[0]))  # Will raise TypeError in interactive sessions
            if frame_path.name != 'runpy.py' and frame_path.parent.name != 'unittest':
                top_level_name = frame_path.stem
                top_level_globals = frame_info.frame.f_globals
                break

    return top_level_name, top_level_globals
