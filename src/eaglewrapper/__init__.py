"""A Python wrapper for the local HTTP API of Eagle, the image and design asset manager.

* :class:`Eagle` - the V1 (legacy) API methods, the library-folder reader, and ``.v2``.
* :class:`EagleV2` - the Web API V2 on its own (Eagle 4.0 Build 21 or later).
* :mod:`eaglewrapper.errors` - the exceptions.
"""
__version__ = '1.1.1'

from .client import EagleClient
from .eagle import Eagle, ImageData
from .errors import EagleAPIError, EagleConnectionError, EagleError, EagleResponseError
from .v2 import EagleV2

__all__ = [
    'Eagle', 'EagleV2', 'EagleClient', 'ImageData',
    'EagleError', 'EagleAPIError', 'EagleConnectionError', 'EagleResponseError',
]
