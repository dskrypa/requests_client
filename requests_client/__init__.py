"""
:author: Doug Skrypa
"""

from .__version__ import *  # noqa

try:
    from .client import RequestsClient
except ImportError:

    class RequestsClient:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError('Missing required dependency: requests')


try:
    from .async_client import AsyncRequestsClient
except ImportError:

    class AsyncRequestsClient:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError('Missing required dependency: httpx')


from .user_agent import (
    USER_AGENT_BASIC,
    USER_AGENT_CHROME,
    USER_AGENT_FIREFOX,
    USER_AGENT_LIBS,
    USER_AGENT_SCRIPT_CONTACT,
    USER_AGENT_SCRIPT_CONTACT_OS,
    USER_AGENT_SCRIPT_OS,
    USER_AGENT_SCRIPT_URL,
    USER_AGENT_SCRIPT_URL_OS,
    generate_user_agent,
)
