"""A Python wrapper for the local HTTP API of Eagle, the image and design asset manager.

* :class:`Eagle` - the V1 (legacy) API methods and the library-folder reader.
* :mod:`eaglewrapper.errors` - the exceptions.
"""
__version__ = '1.1.1'

from .client import EagleClient
from .eagle import Eagle, ImageData
from .errors import EagleAPIError, EagleConnectionError, EagleError, EagleResponseError

__all__ = [
    'Eagle', 'EagleClient', 'ImageData',
    'EagleError', 'EagleAPIError', 'EagleConnectionError', 'EagleResponseError',
]
