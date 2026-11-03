"""Exceptions raised by eaglewrapper.

Every exception here is an :class:`EagleError`, so ``except EagleError`` catches all of
them. Each one also inherits the exception type that 1.1.1 let through in the same
situation, so ``except requests.ConnectionError`` or ``except ValueError`` in older code
keeps working.
"""
from typing import Any, Optional

import requests


class EagleError(Exception):
    """Base class for every error raised by eaglewrapper."""


class EagleConnectionError(EagleError, requests.exceptions.ConnectionError):
    """Eagle could not be reached: it is not running, or the host, port or network is wrong.

    Also a :class:`requests.exceptions.ConnectionError`, which is what 1.1.1 raised.
    """


class EagleResponseError(EagleError, ValueError):
    """Eagle answered with something that is not JSON, e.g. a plain ``Not Found`` page.

    This is what you get when calling a V2 endpoint on an Eagle older than 4.0 Build 21.
    Also a :class:`ValueError`, which is what 1.1.1 raised (a JSON decoding error).
    """

    def __init__(self, message: str, endpoint: Optional[str] = None,
                 status_code: Optional[int] = None, text: Optional[str] = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code
        self.text = text


class EagleAPIError(EagleError):
    """Eagle answered, but reported a failure (``{"status": "error", ...}``).

    Attributes:
        endpoint: The API path that failed, e.g. ``/api/v2/item/add``.
        message: Eagle's error message, if it sent one.
        status_code: The HTTP status code of the reply, if known.
        payload: The decoded reply.
    """

    def __init__(self, message: str, endpoint: Optional[str] = None, status_code: Optional[int] = None,
                 payload: Any = None):
        super().__init__(message)
        self.endpoint = endpoint
        self.message = message
        self.status_code = status_code
        self.payload = payload
