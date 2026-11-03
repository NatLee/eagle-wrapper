"""The one place that says which Eagle APIs this release speaks (eaglewrapper._apis).

Expected values come from Eagle's docs: V1 lives under /api/ since Eagle 1.11 Build 21
(https://api.eagle.cool/), Web API V2 under /api/v2/ since Eagle 4.0 Build 21
(https://developer.eagle.cool/web-api); V1's last change was in 3.0 Build 23, V2's in 4.0 Build 22.
"""
import unittest

import eaglewrapper
from eaglewrapper import API_V1, API_V2, SUPPORTED_APIS, EagleResponseError
from eaglewrapper._apis import api_for_path

from .fakes import MockedHTTP


class TestSupportedApis(unittest.TestCase):

    def test_what_this_release_speaks(self):
        self.assertEqual(SUPPORTED_APIS, (API_V1, API_V2))
        self.assertEqual((API_V1.prefix, API_V1.since, API_V1.covered_up_to),
                         ('/api/', '1.11 Build 21', '3.0 Build 23'))
        self.assertEqual((API_V2.prefix, API_V2.since, API_V2.covered_up_to),
                         ('/api/v2/', '4.0 Build 21', '4.0 Build 22'))
        self.assertIs(eaglewrapper.SUPPORTED_APIS, SUPPORTED_APIS)

    def test_generations_count_up_from_1(self):
        self.assertEqual([api.generation for api in SUPPORTED_APIS], [1, 2])

    def test_path(self):
        self.assertEqual(API_V2.path('item/get'), '/api/v2/item/get')
        self.assertEqual(API_V2.path('/item/get'), '/api/v2/item/get')
        self.assertEqual(API_V1.path('item/list'), '/api/item/list')

    def test_api_for_path_picks_the_longest_prefix(self):
        self.assertIs(api_for_path('/api/v2/item/get'), API_V2)
        self.assertIs(api_for_path('/api/item/list'), API_V1)
        self.assertIsNone(api_for_path('/health'))


class TestNotJsonHint(MockedHTTP):
    """A reply that is not JSON says which Eagle build the API needs, taken from SUPPORTED_APIS."""

    def setUp(self):
        super().setUp()
        self.reply(status_code=404, content=b'Not Found', content_type='text/plain', not_json=True)

    def test_v2_endpoint(self):
        with self.assertRaises(EagleResponseError) as ctx:
            eaglewrapper.EagleV2().app.info()
        self.assertIn('Web API V2 needs Eagle {} or later'.format(API_V2.since), str(ctx.exception))

    def test_v1_endpoint(self):
        with self.assertRaises(EagleResponseError) as ctx:
            eaglewrapper.Eagle().list_folders()
        self.assertIn('V1 needs Eagle {} or later'.format(API_V1.since), str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
