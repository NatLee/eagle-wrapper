"""The V1 features 1.1.1 did not cover: the star rating of addFromURL and /api/library/icon."""
import unittest

from eaglewrapper import Eagle, EagleAPIError

from .fakes import ERROR, HOST, MockedHTTP


class TestStar(MockedHTTP):

    def test_star_is_sent_only_when_given(self):
        eagle = Eagle()
        eagle.add_from_url('https://example.com/a.jpg', 'a', star=4)
        self.assertEqual(self.post.call_args[1]['json']['star'], 4)
        eagle.add_from_url('https://example.com/a.jpg', 'a')
        self.assertNotIn('star', self.post.call_args[1]['json'])

    def test_zero_stars(self):
        Eagle().add_from_url('https://example.com/a.jpg', 'a', star=0)
        self.assertEqual(self.post.call_args[1]['json']['star'], 0)


class TestLibraryIcon(MockedHTTP):

    def test_get_library_icon(self):
        self.reply(content=b'\x89PNG...', content_type='image/png')
        self.assertEqual(Eagle().get_library_icon('/lib/Design.library'), b'\x89PNG...')
        self.assertEqual(self.get.call_args[0][0], HOST + '/api/library/icon')
        self.assertEqual(self.get.call_args[1]['params'], {'libraryPath': '/lib/Design.library'})

    def test_failure(self):
        self.reply(ERROR, status_code=500)
        self.assertIsNone(Eagle().get_library_icon('/missing.library'))
        with self.assertRaises(EagleAPIError):
            Eagle(raise_errors=True).get_library_icon('/missing.library')


if __name__ == '__main__':
    unittest.main()
