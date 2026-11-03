"""Check what each method sends to Eagle's local HTTP API, without a running Eagle.

`requests.get` and `requests.post` are replaced by mocks, so these tests only check
the request (method, URL, parameters, JSON body) and how the reply is handled.
Parameter names follow the Eagle API documentation: https://api.eagle.cool/
"""
import unittest
from unittest import mock

import requests

from eaglewrapper import Eagle

HOST = 'http://localhost:41595'
SUCCESS = {'status': 'success', 'data': {'ok': True}}
ERROR = {'status': 'error'}


def fake_response(payload):
    resp = mock.Mock()
    resp.json.return_value = payload
    return resp


def sent_url(call):
    """The full URL a mocked requests.get/post call would hit, query string included."""
    args, kwargs = call
    return requests.Request('GET', args[0], params=kwargs.get('params')).prepare().url


class EagleRequestTestCase(unittest.TestCase):

    def setUp(self):
        self.eagle = Eagle()
        self.get = mock.patch('eaglewrapper.eagle.requests.get').start()
        self.post = mock.patch('eaglewrapper.eagle.requests.post').start()
        self.addCleanup(mock.patch.stopall)
        self.reply(SUCCESS)

    def reply(self, payload):
        self.get.return_value = fake_response(payload)
        self.post.return_value = fake_response(payload)

    def assert_get(self, path, params=None):
        self.post.assert_not_called()
        args, kwargs = self.get.call_args
        self.assertEqual(args[0], HOST + path)
        self.assertEqual(kwargs.get('params'), params)

    def assert_post(self, path, body):
        self.get.assert_not_called()
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], HOST + path)
        self.assertEqual(kwargs['json'], body)


class TestHost(unittest.TestCase):

    def test_default_host_is_local_eagle(self):
        self.assertEqual(Eagle().host, HOST)

    def test_custom_port(self):
        self.assertEqual(Eagle(port=1234).host, 'http://localhost:1234')


class TestApplication(EagleRequestTestCase):

    def test_get_application_info(self):
        self.assertEqual(self.eagle.get_application_info(), {'ok': True})
        self.assert_get('/api/application/info')


class TestFolder(EagleRequestTestCase):

    def test_create_folder(self):
        self.assertEqual(self.eagle.create_folder('New'), {'ok': True})
        self.assert_post('/api/folder/create', {'folderName': 'New'})

    def test_create_folder_with_parent(self):
        self.eagle.create_folder('New', parent_id='P1')
        self.assert_post('/api/folder/create', {'folderName': 'New', 'parent': 'P1'})

    def test_rename_folder(self):
        self.eagle.rename_folder('F1', 'Renamed')
        self.assert_post('/api/folder/rename', {'folderId': 'F1', 'newName': 'Renamed'})

    def test_update_folder_sends_only_given_fields(self):
        self.eagle.update_folder('F1', new_color='red')
        self.assert_post('/api/folder/update', {'folderId': 'F1', 'newColor': 'red'})

    def test_update_folder_all_fields(self):
        self.eagle.update_folder('F1', new_name='n', new_description='d', new_color='blue')
        self.assert_post('/api/folder/update', {
            'folderId': 'F1', 'newName': 'n', 'newDescription': 'd', 'newColor': 'blue'})

    def test_list_folders(self):
        self.eagle.list_folders()
        self.assert_get('/api/folder/list')

    def test_get_recent_folders(self):
        self.eagle.get_recent_folders()
        self.assert_get('/api/folder/listRecent')


class TestItem(EagleRequestTestCase):

    def test_add_from_url_readme_example(self):
        ok = self.eagle.add_from_url('https://example.com/a.jpg', 'name', ['t1', 't2'],
                                     'https://example.com', 'note')
        self.assertIs(ok, True)
        self.assert_post('/api/item/addFromURL', {
            'url': 'https://example.com/a.jpg', 'name': 'name', 'website': 'https://example.com',
            'tags': ['t1', 't2'], 'annotation': 'note', 'modificationTime': None, 'headers': {}})

    def test_add_from_url_with_folder_time_and_headers(self):
        self.eagle.add_from_url('https://example.com/a.jpg', 'name', modification_time=1680000000000,
                                folder_id='F1', headers={'referer': 'https://example.com'})
        args, kwargs = self.post.call_args
        self.assertEqual(kwargs['json']['folderId'], 'F1')
        self.assertEqual(kwargs['json']['modificationTime'], 1680000000000)
        self.assertEqual(kwargs['json']['headers'], {'referer': 'https://example.com'})

    def test_add_from_url_reports_failure(self):
        self.reply(ERROR)
        self.assertIs(self.eagle.add_from_url('https://example.com/a.jpg', 'name'), False)

    def test_add_from_url_requires_url_and_name(self):
        with self.assertRaises(ValueError):
            self.eagle.add_from_url('', 'name')
        with self.assertRaises(ValueError):
            self.eagle.add_from_url('https://example.com/a.jpg', '')
        self.post.assert_not_called()

    def test_add_from_urls_with_every_key(self):
        ok = self.eagle.add_from_urls([{
            'url': 'https://example.com/a.jpg', 'name': 'a', 'website': 'https://example.com',
            'tags': ['t'], 'annotation': 'note', 'modification_time': 1, 'headers': {'h': 'v'},
        }], folder_id='F1')
        self.assertIs(ok, True)
        self.assert_post('/api/item/addFromURLs', {
            'items': [{'url': 'https://example.com/a.jpg', 'name': 'a', 'website': 'https://example.com',
                       'tags': ['t'], 'annotation': 'note', 'modificationTime': 1, 'headers': {'h': 'v'}}],
            'folderId': 'F1'})

    def test_add_from_urls_with_only_required_keys(self):
        # website, tags, annotation, modificationTime and headers are documented as optional.
        self.assertIs(self.eagle.add_from_urls([{'url': 'https://example.com/a.jpg', 'name': 'a'}]), True)
        self.assert_post('/api/item/addFromURLs', {
            'items': [{'url': 'https://example.com/a.jpg', 'name': 'a', 'website': '', 'tags': [],
                       'annotation': '', 'modificationTime': None, 'headers': {}}]})

    def test_add_from_urls_accepts_documented_modificationTime_key(self):
        self.eagle.add_from_urls([{'url': 'https://example.com/a.jpg', 'name': 'a', 'modificationTime': 5}])
        args, kwargs = self.post.call_args
        self.assertEqual(kwargs['json']['items'][0]['modificationTime'], 5)

    def test_add_from_path(self):
        self.eagle.add_from_path('/tmp/a.jpg', 'a', website='https://example.com', annotation='note',
                                 tags=['t'], folder_id='F1')
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], HOST + '/api/item/addFromPath')
        body = kwargs['json']
        self.assertNotIn('url', body)
        for key, value in {'path': '/tmp/a.jpg', 'name': 'a', 'website': 'https://example.com',
                           'annotation': 'note', 'tags': ['t'], 'folderId': 'F1'}.items():
            self.assertEqual(body[key], value)

    def test_add_from_paths_with_every_key(self):
        ok = self.eagle.add_from_paths([{
            'path': '/tmp/a.jpg', 'name': 'a', 'website': 'https://example.com',
            'tags': ['t'], 'annotation': 'note',
        }], folder_id='F1')
        self.assertIs(ok, True)
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], HOST + '/api/item/addFromPaths')
        self.assertEqual(kwargs['json']['folderId'], 'F1')
        item = kwargs['json']['items'][0]
        self.assertNotIn('url', item)
        for key, value in {'path': '/tmp/a.jpg', 'name': 'a', 'website': 'https://example.com',
                           'tags': ['t'], 'annotation': 'note'}.items():
            self.assertEqual(item[key], value)

    def test_add_from_paths_with_only_required_keys(self):
        # website, annotation and tags are documented as optional.
        self.assertIs(self.eagle.add_from_paths([{'path': '/tmp/a.jpg', 'name': 'a'}]), True)
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], HOST + '/api/item/addFromPaths')
        self.assertNotIn('folderId', kwargs['json'])
        item = kwargs['json']['items'][0]
        for key, value in {'path': '/tmp/a.jpg', 'name': 'a', 'website': '', 'tags': [],
                           'annotation': ''}.items():
            self.assertEqual(item[key], value)

    def test_add_bookmark(self):
        ok = self.eagle.add_bookmark('https://example.com', 'site', tags=['t'], thumbnail_base64='data:',
                                     modification_time=1, folder_id='F1')
        self.assertIs(ok, True)
        self.assert_post('/api/item/addBookmark', {
            'url': 'https://example.com', 'name': 'site', 'tags': ['t'], 'base64': 'data:',
            'modificationTime': 1, 'folderId': 'F1'})

    def test_get_item_info(self):
        self.assertEqual(self.eagle.get_item_info('I1'), {'ok': True})
        self.assert_get('/api/item/info', {'id': 'I1'})

    def test_get_item_info_returns_none_on_error(self):
        self.reply(ERROR)
        self.assertIsNone(self.eagle.get_item_info('I1'))

    def test_get_thumbnail_path(self):
        self.reply({'status': 'success', 'data': '/lib/images/I1.info/a_thumbnail.png'})
        self.assertEqual(self.eagle.get_thumbnail_path('I1'), '/lib/images/I1.info/a_thumbnail.png')
        self.assert_get('/api/item/thumbnail', {'id': 'I1'})

    def test_get_thumbnail_path_returns_none_on_error(self):
        self.reply(ERROR)
        self.assertIsNone(self.eagle.get_thumbnail_path('I1'))

    def test_list_items_defaults(self):
        self.eagle.list_items()
        self.assert_get('/api/item/list', {'limit': 200, 'offset': 0})

    def test_list_items_filters(self):
        self.eagle.list_items(limit=5, offset=1, order_by='-FILESIZE', keyword='cat', ext='png',
                              tags=['a', 'b'], folders=['F1', 'F2'])
        self.assert_get('/api/item/list', {
            'limit': 5, 'offset': 1, 'orderBy': '-FILESIZE', 'keyword': 'cat', 'ext': 'png',
            'tags': 'a,b', 'folders': 'F1,F2'})

    def test_move_to_trash(self):
        self.assertIs(self.eagle.move_to_trash(['I1', 'I2']), True)
        self.assert_post('/api/item/moveToTrash', {'itemIds': ['I1', 'I2']})

    def test_refresh_palette(self):
        self.assertIs(self.eagle.refresh_palette('I1'), True)
        self.assert_post('/api/item/refreshPalette', {'id': 'I1'})

    def test_refresh_thumbnail(self):
        self.assertIs(self.eagle.refresh_thumbnail('I1'), True)
        self.assert_post('/api/item/refreshThumbnail', {'id': 'I1'})

    def test_update_item_sends_only_given_fields(self):
        self.assertEqual(self.eagle.update_item('I1', tags=['t'], star=5), {'ok': True})
        self.assert_post('/api/item/update', {'id': 'I1', 'tags': ['t'], 'star': 5})

    def test_update_item_raises_on_error(self):
        self.reply(ERROR)
        with self.assertRaises(Exception):
            self.eagle.update_item('I1', annotation='note')

    def test_set_tag_with_id(self):
        self.eagle.set_tag_with_id('I1', ['t'])
        self.assert_post('/api/item/update', {'id': 'I1', 'tags': ['t']})

    def test_get_img_list_info_readme_example(self):
        self.reply({'status': 'success', 'data': [{'name': 'ぼっち'}, {'name': 'example'}]})
        self.assertEqual(self.eagle.get_img_list_info(10, 'ぼ'), [{'name': 'ぼっち'}])
        self.assertEqual(sent_url(self.get.call_args), HOST + '/api/item/list?limit=10')


class TestLibrary(EagleRequestTestCase):

    def test_get_library_info(self):
        self.eagle.get_library_info()
        self.assert_get('/api/library/info')

    def test_get_library_history(self):
        self.eagle.get_library_history()
        self.assert_get('/api/library/history')

    def test_switch_library(self):
        self.assertIs(self.eagle.switch_library('/my/test.library'), True)
        self.assert_post('/api/library/switch', {'libraryPath': '/my/test.library'})


if __name__ == '__main__':
    unittest.main()
