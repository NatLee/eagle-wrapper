"""The HTTP layer shared by the V1 methods (:class:`~eaglewrapper.Eagle`) and the V2 API.

Eagle runs a small HTTP server on the machine where the app is open (port 41595 by
default) and answers in JSend format: ``{"status": "success", "data": ...}`` or
``{"status": "error", "message": ...}``. :class:`EagleClient` builds the URL, adds the
API token, sends the request and turns the reply (or the lack of one) into Python
values and exceptions, so the endpoint methods only describe what to send.
"""
import os
from typing import Any, Dict, Optional, Tuple

import requests

from ._apis import api_for_path
from .errors import EagleAPIError, EagleConnectionError, EagleResponseError

DEFAULT_HOST = 'http://localhost'
DEFAULT_PORT = 41595
DEFAULT_BASE_URL = '{}:{}'.format(DEFAULT_HOST, DEFAULT_PORT)
TOKEN_ENV_VAR = 'EAGLE_API_TOKEN'
REPLY_TEXT_KEPT = 200  # characters of a non-JSON reply kept on EagleResponseError.text

Params = Optional[Dict[str, Any]]


def compact(**fields: Any) -> Dict[str, Any]:
    """The given request fields without the ones that are ``None`` (= not set), in the given order."""
    return {key: value for key, value in fields.items() if value is not None}


def is_success(payload: Any) -> bool:
    """True if a decoded Eagle reply says ``"status": "success"``."""
    return isinstance(payload, dict) and payload.get('status') == 'success'


def error_message(payload: Any) -> str:
    """The most useful error text in a decoded Eagle reply."""
    if isinstance(payload, dict):
        for key in ('message', 'data'):
            if isinstance(payload.get(key), str) and payload[key]:
                return payload[key]
        if 'status' in payload:
            return 'Eagle answered status {!r}'.format(payload['status'])
    return 'Eagle answered {!r}'.format(payload)


class EagleClient:
    """Sends requests to one Eagle instance and decodes the replies.

    Args:
        base_url: Where Eagle listens, e.g. ``http://localhost:41595`` (the default) or
            ``http://192.168.1.20:41595`` for Eagle on another computer.
        token: API token, needed only when Eagle runs on another device. It is sent as the
            ``token`` query parameter on every request. When omitted, the ``EAGLE_API_TOKEN``
            environment variable is used if it is set; pass ``''`` to send no token at all.
        timeout: Seconds to wait for Eagle, passed to ``requests``. ``None`` (the default)
            waits as long as it takes, like 1.1.1 did.
        session: A ``requests.Session`` (or anything with the same ``get``/``post``) to send
            requests with, e.g. to reuse connections. By default each request goes through
            ``requests.get``/``requests.post``.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: Optional[str] = None,
                 timeout: Optional[float] = None, session: Optional[requests.Session] = None):
        if token is None:
            token = os.environ.get(TOKEN_ENV_VAR) or None
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.timeout = timeout
        self.session = session

    def __repr__(self) -> str:
        return '{}({!r}, token={})'.format(type(self).__name__, self.base_url, 'set' if self.token else None)

    # ---- sending -----------------------------------------------------------------------------

    def send(self, method: str, path: str, params: Params = None, body: Any = None) -> requests.Response:
        """Send one request and return the raw response.

        Raises:
            EagleConnectionError: Eagle could not be reached.
        """
        query = dict(params) if params else {}
        if self.token:
            query['token'] = self.token
        kwargs = {}  # type: Dict[str, Any]
        if query:
            kwargs['params'] = query
        if self.timeout is not None:
            kwargs['timeout'] = self.timeout
        http = self.session if self.session is not None else requests
        url = self.base_url + path
        try:
            if method == 'GET':
                return http.get(url, **kwargs)
            return http.post(url, json=body, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            raise EagleConnectionError(
                'Cannot reach Eagle at {} ({}). Is Eagle open, and are the host and port right?'.format(
                    self.base_url, path)) from exc

    def exchange(self, method: str, path: str, params: Params = None, body: Any = None) -> Tuple[Any, Optional[int]]:
        """Send one request and return ``(decoded JSON reply, HTTP status code)``.

        Raises:
            EagleConnectionError: Eagle could not be reached.
            EagleResponseError: The reply is not JSON.
        """
        return self._decode(self.send(method, path, params, body), path)

    def call(self, method: str, path: str, params: Params = None, body: Any = None) -> Any:
        """Send one request and return the decoded JSON reply, whatever its status."""
        return self.exchange(method, path, params, body)[0]

    def data(self, method: str, path: str, params: Params = None, body: Any = None) -> Any:
        """Send one request and return the reply's ``data``.

        Raises:
            EagleConnectionError: Eagle could not be reached.
            EagleResponseError: The reply is not JSON.
            EagleAPIError: Eagle reported a failure.
        """
        payload, status_code = self.exchange(method, path, params, body)
        if not is_success(payload):
            raise EagleAPIError('{} failed: {}'.format(path, error_message(payload)),
                                endpoint=path, status_code=status_code, payload=payload)
        return payload.get('data')

    def binary(self, path: str, params: Params = None) -> bytes:
        """GET an endpoint that answers with a file (e.g. a library icon) and return its bytes.

        Raises:
            EagleConnectionError: Eagle could not be reached.
            EagleResponseError: Eagle answered with an HTTP error that is not JSON.
            EagleAPIError: Eagle answered with a JSON error.
        """
        resp = self.send('GET', path, params)
        content_type = (getattr(resp, 'headers', None) or {}).get('Content-Type', '')
        status_code = getattr(resp, 'status_code', 200)
        if 'json' in content_type or status_code >= 400:
            payload, status_code = self._decode(resp, path)
            raise EagleAPIError('{} failed: {}'.format(path, error_message(payload)),
                                endpoint=path, status_code=status_code, payload=payload)
        return resp.content

    @staticmethod
    def _decode(resp: requests.Response, path: str) -> Tuple[Any, Optional[int]]:
        status_code = getattr(resp, 'status_code', None)
        try:
            return resp.json(), status_code
        except ValueError as exc:
            text = getattr(resp, 'text', None)
            api = api_for_path(path)
            hint = ' {} needs Eagle {} or later.'.format(api.name, api.since) if api else ''
            raise EagleResponseError(
                'Eagle answered {} with something that is not JSON (HTTP {}).{}'.format(path, status_code, hint),
                endpoint=path, status_code=status_code,
                text=text[:REPLY_TEXT_KEPT] if isinstance(text, str) else None) from exc
