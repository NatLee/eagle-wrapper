"""A Python wrapper for the local HTTP API of Eagle, the image and design asset manager.

* :class:`Eagle` - the V1 (legacy) API methods, the library-folder reader, and ``.v2``.
* :class:`EagleV2` - the Web API V2 on its own.
* :mod:`eaglewrapper.errors` - the exceptions.
* :data:`SUPPORTED_APIS` - which Eagle APIs and Eagle builds this release covers.
"""
__version__ = '1.2.0'

from ._apis import API_V1, API_V2, SUPPORTED_APIS, EagleAPI
from .client import EagleClient
from .eagle import Eagle, ImageData
from .errors import EagleAPIError, EagleConnectionError, EagleError, EagleResponseError
from .v2 import EagleV2

__all__ = [
    'Eagle', 'EagleV2', 'EagleClient', 'ImageData',
    'EagleError', 'EagleAPIError', 'EagleConnectionError', 'EagleResponseError',
    'EagleAPI', 'API_V1', 'API_V2', 'SUPPORTED_APIS',
]
