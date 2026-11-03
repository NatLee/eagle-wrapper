"""Where requests go and how: host, port, base_url, token, timeout, session, raise_errors."""
import os
import unittest
from unittest import mock

from eaglewrapper import Eagle, EagleAPIError

from .fakes import ERROR, HOST, SUCCESS, MockedHTTP, fake_response


class TestAddress(MockedHTTP):

    def test_defaults_match_1_1_1(self):
        eagle = Eagle()
        self.assertEqual((eagle.domain, eagle.port, eagle.host), ('http://localhost', 41595, HOST))
        self.assertIsNone(eagle.token)
        self.assertFalse(eagle.raise_errors)
        self.assertEqual(repr(eagle), "Eagle('http://localhost:41595')")

    def test_positional_domain_and_port(self):
        eagle = Eagle('http://127.0.0.1', 1234)
        eagle.list_folders()
        self.assertEqual(self.get.call_args[0][0], 'http://127.0.0.1:1234/api/folder/list')

    def test_base_url(self):
        eagle = Eagle(base_url='http://192.168.1.20:41595/')
        self.assertEqual((eagle.host, eagle.domain, eagle.port),
                         ('http://192.168.1.20:41595', 'http://192.168.1.20', 41595))
        eagle.get_application_info()
        self.assertEqual(self.get.call_args[0][0], 'http://192.168.1.20:41595/api/application/info')

    def test_changing_host_after_creation(self):
        eagle = Eagle()
        eagle.host = 'http://10.0.0.5:41595/'
        eagle.get_library_info()
        self.assertEqual(self.get.call_args[0][0], 'http://10.0.0.5:41595/api/library/info')


class TestToken(MockedHTTP):

    def test_token_is_sent_on_get_and_post(self):
        eagle = Eagle(token='secret')
        eagle.get_item_info('I1')
        self.assertEqual(self.get.call_args[1]['params'], {'id': 'I1', 'token': 'secret'})
        eagle.move_to_trash(['I1'])
        self.assertEqual(self.post.call_args[1]['params'], {'token': 'secret'})
        self.assertEqual(self.post.call_args[1]['json'], {'itemIds': ['I1']})

    def test_no_token_means_no_query_parameters(self):
        Eagle().move_to_trash(['I1'])
        self.assertNotIn('params', self.post.call_args[1])

    def test_token_from_environment(self):
        os.environ['EAGLE_API_TOKEN'] = 'from-env'
        eagle = Eagle()
        self.assertEqual(eagle.token, 'from-env')
        eagle.list_folders()
        self.assertEqual(self.get.call_args[1]['params'], {'token': 'from-env'})

    def test_empty_token_ignores_environment(self):
        os.environ['EAGLE_API_TOKEN'] = 'from-env'
        Eagle(token='').list_folders()
        self.assertNotIn('params', self.get.call_args[1])

    def test_token_can_be_set_later(self):
        eagle = Eagle()
        eagle.token = 't2'
        eagle.list_folders()
        self.assertEqual(self.get.call_args[1]['params'], {'token': 't2'})


class TestTransport(MockedHTTP):

    def test_timeout_is_passed_to_requests(self):
        Eagle(timeout=3).list_folders()
        self.assertEqual(self.get.call_args[1]['timeout'], 3)

    def test_no_timeout_by_default(self):
        Eagle().list_folders()
        self.assertNotIn('timeout', self.get.call_args[1])

    def test_custom_session(self):
        session = mock.Mock()
        session.post.return_value = fake_response(SUCCESS)
        self.assertIs(Eagle(session=session).switch_library('/lib'), True)
        session.post.assert_called_once()
        self.assertEqual(session.post.call_args[0][0], HOST + '/api/library/switch')
        self.post.assert_not_called()


class TestRaiseErrors(MockedHTTP):

    def test_every_v1_method_raises(self):
        self.reply(ERROR, status_code=400)
        eagle = Eagle(raise_errors=True)
        calls = [
            lambda: eagle.add_from_url('https://example.com/a.jpg', 'a'),
            lambda: eagle.add_from_urls([{'url': 'https://example.com/a.jpg', 'name': 'a'}]),
            lambda: eagle.add_from_path('/tmp/a.jpg', 'a'),
            lambda: eagle.add_from_paths([{'path': '/tmp/a.jpg', 'name': 'a'}]),
            lambda: eagle.add_bookmark('https://example.com', 'a'),
            lambda: eagle.get_item_info('I1'),
            lambda: eagle.get_thumbnail_path('I1'),
            lambda: eagle.list_items(),
            lambda: eagle.get_img_list_info(5),
            lambda: eagle.move_to_trash(['I1']),
            lambda: eagle.refresh_palette('I1'),
            lambda: eagle.refresh_thumbnail('I1'),
            lambda: eagle.update_item('I1', tags=['t']),
            lambda: eagle.set_tag_with_id('I1', ['t']),
            lambda: eagle.create_folder('f'),
            lambda: eagle.rename_folder('F1', 'f'),
            lambda: eagle.update_folder('F1', new_name='f'),
            lambda: eagle.list_folders(),
            lambda: eagle.get_recent_folders(),
            lambda: eagle.get_application_info(),
            lambda: eagle.get_library_info(),
            lambda: eagle.get_library_history(),
            lambda: eagle.switch_library('/lib'),
        ]
        for call in calls:
            with self.subTest(call=call):
                with self.assertRaises(EagleAPIError) as ctx:
                    call()
                self.assertIn('Item not found', str(ctx.exception))
                self.assertEqual(ctx.exception.payload, ERROR)
                self.assertEqual(ctx.exception.status_code, 400)

    def test_success_is_unchanged(self):
        eagle = Eagle(raise_errors=True)
        self.assertIs(eagle.move_to_trash(['I1']), True)
        self.assertEqual(eagle.list_folders(), {'ok': True})
        self.assertEqual(eagle.add_from_path('/tmp/a.jpg', 'a'), SUCCESS)


if __name__ == '__main__':
    unittest.main()
