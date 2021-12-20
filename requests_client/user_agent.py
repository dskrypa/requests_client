"""
Utilities for setting the User-Agent header for requests.

:author: Doug Skrypa
"""

import inspect
import logging
import os
import platform
from pathlib import Path
from typing import Any

import requests

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
USER_AGENT_LIBS = '{py_impl}/{py_ver} Requests/{requests_ver} RequestsClient/{rc_ver}'
USER_AGENT_BASIC = '{script}/{script_ver} ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_OS = '{script}/{script_ver} ({os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_CONTACT = '{script}/{script_ver} ({url}; {email}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_URL = '{script}/{script_ver} ({url}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_URL_OS = '{script}/{script_ver} ({url}; {os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_SCRIPT_CONTACT_OS = '{script}/{script_ver} ({url}; {email}; {os_name} {os_rel}; {arch}) ' + USER_AGENT_LIBS
USER_AGENT_FIREFOX = 'Mozilla/5.0 ({os_info}; rv:{firefox_ver}) Gecko/20100101 Firefox/{firefox_ver}'
USER_AGENT_CHROME = 'Mozilla/5.0 ({os_info}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_ver} Safari/537.36'


def generate_user_agent(ua_format, downgrade=True, **kwargs):
    """
    :param str ua_format: User agent format string
    :param bool downgrade: Allow a format downgrade if a given value is missing and a default template is used
    :param kwargs: Value overrides or custom keys/values to use
    :return str: The user agent string based on the given format and available system information
    """
    arch = platform.architecture()[0]
    if arch.endswith('bit'):
        arch = 'x{}'.format(arch.replace('bit', ''))

    try:
        top_level_name, top_level_globals = _get_top_level_info(inspect.stack())
    except Exception as e:
        log.debug(f'Error determining top-level script info: {e}')
        top_level_name = 'RequestsClient'
        top_level_globals = {}

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
        'requests_ver': requests.__version__,           # 2.22.0
        'rc_ver': __version__,                          # 2020.01.18
        'firefox_ver': kwargs.pop('firefox_ver', None) or os.environ.get('FIREFOX_VERSION') or 95.0,
        'chrome_ver': kwargs.pop('chrome_ver', None) or os.environ.get('CHROME_VERSION') or '96.0.4664.110',
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


def _get_top_level_info(stack) -> tuple[str, dict[str, Any]]:
    top_level_frame_info = stack[-1]
    top_level_name = Path(inspect.getsourcefile(top_level_frame_info[0])).stem
    top_level_globals = top_level_frame_info.frame.f_globals

    if top_level_name == 'runpy':  # happens when running `python -m unittest tests/*.py`
        for frame_info in reversed(stack):
            frame_path = Path(inspect.getsourcefile(frame_info[0]))
            if frame_path.name != 'runpy.py' and frame_path.parent.name != 'unittest':
                top_level_name = frame_path.stem
                top_level_globals = frame_info.frame.f_globals
                break

    return top_level_name, top_level_globals
