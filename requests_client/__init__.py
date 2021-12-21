"""
:author: Doug Skrypa
"""

from .__version__ import *  # noqa

try:
    from .client import RequestsClient
except ImportError:

    class RequestsClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('Missing required dependency: requests')


try:
    from .async_client import AsyncRequestsClient
except ImportError:

    class AsyncRequestsClient:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('Missing required dependency: httpx')


from .user_agent import (
    generate_user_agent,
    USER_AGENT_LIBS,
    USER_AGENT_BASIC,
    USER_AGENT_SCRIPT_CONTACT,
    USER_AGENT_SCRIPT_CONTACT_OS,
    USER_AGENT_SCRIPT_OS,
    USER_AGENT_SCRIPT_URL,
    USER_AGENT_SCRIPT_URL_OS,
    USER_AGENT_CHROME,
    USER_AGENT_FIREFOX,
)
