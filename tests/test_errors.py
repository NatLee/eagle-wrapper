"""What the V1 methods do when Eagle is closed, answers garbage, or reports a failure."""
import unittest
from unittest import mock

import requests

from eaglewrapper import Eagle, EagleAPIError, EagleConnectionError, EagleError, EagleResponseError

from .fakes import ERROR, HOST, SUCCESS, MockedHTTP, fake_response


class TestEagleUnreachable(MockedHTTP):

    def test_eagle_not_running(self):
        self.get.side_effect = requests.exceptions.ConnectionError('refused')
        with self.assertRaises(EagleConnectionError) as ctx:
            Eagle().get_application_info()
        self.assertIn('Is Eagle open', str(ctx.exception))
        self.assertIn(HOST, str(ctx.exception))
        self.assertIsInstance(ctx.exception, EagleError)

    def test_connection_error_is_still_a_requests_connection_error(self):
        # Code written for 1.1.1 catches requests' exception.
        self.post.side_effect = requests.exceptions.ConnectionError('refused')
        with self.assertRaises(requests.exceptions.ConnectionError):
            Eagle().add_from_url('https://example.com/a.jpg', 'a')


class TestReplyNotJson(MockedHTTP):

    def test_reply_that_is_not_json(self):
        self.reply(status_code=404, content=b'Not Found', content_type='text/plain', not_json=True)
        with self.assertRaises(EagleResponseError) as ctx:
            Eagle().list_items()
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.endpoint, '/api/item/list')
        self.assertEqual(ctx.exception.text, 'Not Found')
        self.assertIsInstance(ctx.exception, ValueError)  # what 1.1.1 raised
        self.assertIsInstance(ctx.exception, EagleError)


class TestEagleReportsFailure(MockedHTTP):
    """By default the V1 methods keep 1.1.1's return values, and now also log a warning."""

    def setUp(self):
        super().setUp()
        self.reply(ERROR)

    def test_bool_methods_return_false_and_log(self):
        with mock.patch('eaglewrapper.eagle.logger') as logger:
            self.assertIs(Eagle().add_from_url('https://example.com/a.jpg', 'a'), False)
        message = logger.warning.call_args[0][1]
        self.assertIn('/api/item/addFromURL', message)
        self.assertIn('Item not found', message)

    def test_every_bool_method_returns_false(self):
        eagle = Eagle()
        calls = [
            lambda: eagle.add_from_url('https://example.com/a.jpg', 'a'),
            lambda: eagle.add_from_urls([{'url': 'https://example.com/a.jpg', 'name': 'a'}]),
            lambda: eagle.add_from_paths([{'path': '/tmp/a.jpg', 'name': 'a'}]),
            lambda: eagle.add_bookmark('https://example.com', 'a'),
            lambda: eagle.move_to_trash(['I1']),
            lambda: eagle.refresh_palette('I1'),
            lambda: eagle.refresh_thumbnail('I1'),
            lambda: eagle.switch_library('/lib'),
        ]
        for call in calls:
            with self.subTest(call=call):
                self.assertIs(call(), False)

    def test_data_methods_return_eagle_data(self):
        eagle = Eagle()
        for call in (eagle.list_folders, eagle.get_recent_folders, eagle.get_application_info,
                     eagle.get_library_info, eagle.get_library_history, eagle.list_items):
            with self.subTest(call=call):
                self.assertIsNone(call())
        self.assertIsNone(eagle.get_item_info('I1'))
        self.assertIsNone(eagle.get_thumbnail_path('I1'))

    def test_get_img_list_info_returns_none_instead_of_crashing(self):
        # 1.1.1 raised TypeError ('NoneType' is not iterable) when a filter was given.
        self.assertIsNone(Eagle().get_img_list_info(10, 'a'))

    def test_add_from_path_returns_the_reply(self):
        self.assertEqual(Eagle().add_from_path('/tmp/a.jpg', 'a'), ERROR)

    def test_update_item_always_raises_an_exception(self):
        with self.assertRaises(EagleAPIError) as ctx:
            Eagle().update_item('I1', star=1)
        self.assertIn('Failed to update the item', str(ctx.exception))
        self.assertIn('Item not found', str(ctx.exception))
        self.assertIsInstance(ctx.exception, Exception)  # 1.1.1 raised a plain Exception


class TestCheckSuccess(unittest.TestCase):

    def test_accepts_a_response_or_a_dict(self):
        eagle = Eagle()
        self.assertTrue(eagle.check_success(fake_response(SUCCESS)))
        self.assertFalse(eagle.check_success(fake_response(ERROR)))
        self.assertTrue(eagle.check_success({'status': 'success'}))
        self.assertFalse(eagle.check_success({'status': 'error'}))


if __name__ == '__main__':
    unittest.main()
