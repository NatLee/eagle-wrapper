"""The Eagle APIs this release speaks, kept in one place.

Eagle has two generations of its local HTTP API and no finer API version number:
whatever Eagle adds inside a generation is tied to the Eagle build that brought it.
So for each generation this module records where its endpoints live, the first Eagle
build that has it, and the newest Eagle build whose additions this release wraps.

The code (endpoint paths, error hints), setup.py (PyPI summary and links) and the
README all take these facts from here, and a test checks the README against them.
The major number of EagleWrapper's own version follows the API generation; see
"Versioning" in the README.

This file imports nothing from the rest of the package, so setup.py can load it on
its own without installing the package's dependencies.
"""
from typing import NamedTuple, Optional


class EagleAPI(NamedTuple):
    """One generation of Eagle's local HTTP API.

    Attributes:
        name: What Eagle's docs call it, e.g. ``'Web API V2'``.
        prefix: The path every endpoint of it starts with, e.g. ``'/api/v2/'``.
        since: The first Eagle build that has it, e.g. ``'4.0 Build 21'``.
        covered_up_to: The newest Eagle build whose additions to this API this
            release wraps. Endpoints Eagle adds later are still reachable with
            :meth:`EagleV2.request() <eaglewrapper.v2.EagleV2.request>`.
        docs: The official documentation.
    """

    name: str
    prefix: str
    since: str
    covered_up_to: str
    docs: str

    def path(self, endpoint: str) -> str:
        """The full path of an endpoint: ``API_V2.path('item/get')`` is ``'/api/v2/item/get'``."""
        return self.prefix + endpoint.lstrip('/')


API_V1 = EagleAPI(
    name='V1', prefix='/api/', since='1.11 Build 21', covered_up_to='3.0 Build 23',
    docs='https://api.eagle.cool/')
"""The original API, which Eagle now calls legacy. Its last documented change came in Eagle 3.0 Build 23."""

API_V2 = EagleAPI(
    name='Web API V2', prefix='/api/v2/', since='4.0 Build 21', covered_up_to='4.0 Build 22',
    docs='https://developer.eagle.cool/web-api')
"""The current API. Eagle 4.0 Build 22 added smart folders and comments."""

SUPPORTED_APIS = (API_V1, API_V2)
"""Every Eagle API generation this release speaks, oldest first."""


def api_for_path(path: str) -> Optional[EagleAPI]:
    """The API generation an endpoint path belongs to (the longest matching prefix), or ``None``."""
    matches = [api for api in SUPPORTED_APIS if path.startswith(api.prefix)]
    return max(matches, key=lambda api: len(api.prefix)) if matches else None
