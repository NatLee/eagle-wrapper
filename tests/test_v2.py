"""What every V2 method sends to Eagle and what it returns, without a running Eagle.

Endpoints, parameter names and reply shapes follow the official V2 docs:
https://developer.eagle.cool/web-api  (Eagle 4.0 Build 21+; smart folders and comments Build 22+)
"""
import inspect
import os
import unittest

import requests

from eaglewrapper import Eagle, EagleAPIError, EagleConnectionError, EagleResponseError, EagleV2

from .fakes import ERROR, HOST, MockedHTTP, fake_response

PAGE = {'data': [{'id': 'M3QSGJNQTC2DG', 'name': 'sunset-photo'}], 'total': 1, 'offset': 0, 'limit': 50}
CONDITIONS = [{'rules': [{'property': 'width', 'method': '>', 'value': [1920]}], 'match': 'AND'}]


# (description, call, HTTP method, path, query params or JSON body, reply data, expected return value)
CASES = [
    # ---- item ----
    ('item.get default', lambda v2: v2.item.get(), 'POST', 'item/get', {}, PAGE, PAGE),
    ('item.get every filter', lambda v2: v2.item.get(
        item_id='I1', item_ids=('I1', 'I2'), is_selected=True, is_untagged=False, is_unfiled=True,
        keywords=['k'], tags=['design'], folders=['F1'], smart_folders=['S1'], ext='png', annotation='note',
        rating=4, url='https://example.com', shape='landscape', fields=['id', 'name'], offset=100, limit=20),
     'POST', 'item/get', {
         'id': 'I1', 'ids': ['I1', 'I2'], 'isSelected': True, 'isUntagged': False, 'isUnfiled': True,
         'keywords': ['k'], 'tags': ['design'], 'folders': ['F1'], 'smartFolders': ['S1'], 'ext': 'png',
         'annotation': 'note', 'rating': 4, 'url': 'https://example.com', 'shape': 'landscape',
         'fields': ['id', 'name'], 'offset': 100, 'limit': 20}, PAGE, PAGE),
    ('item.query', lambda v2: v2.item.query('(cat OR dog) -cartoon', limit=20), 'POST', 'item/query',
     {'query': '(cat OR dog) -cartoon', 'limit': 20}, PAGE, PAGE),
    ('item.count_all', lambda v2: v2.item.count_all(), 'GET', 'item/countAll', None, 12500, 12500),
    ('item.add url', lambda v2: v2.item.add(url='https://example.com/photo.jpg', name='Example Photo',
                                            tags=['downloaded'], folders=['F1']),
     'POST', 'item/add', {'url': 'https://example.com/photo.jpg', 'name': 'Example Photo', 'tags': ['downloaded'],
                          'folders': ['F1']}, {'id': 'NEW1'}, 'NEW1'),
    ('item.add path', lambda v2: v2.item.add(path='C:\\Users\\User\\design.png', name='My Design'),
     'POST', 'item/add', {'path': 'C:\\Users\\User\\design.png', 'name': 'My Design'}, {'id': 'NEW2'}, 'NEW2'),
    ('item.add bookmark', lambda v2: v2.item.add(bookmark_url='https://www.example.com', tags=['bookmark']),
     'POST', 'item/add', {'bookmarkURL': 'https://www.example.com', 'tags': ['bookmark']}, {'id': 'NEW3'}, 'NEW3'),
    ('item.add base64 + every field', lambda v2: v2.item.add(
        base64='iVBORw0KGgo=', name='n', annotation='a', website='https://example.com', item_id='CUSTOMID'),
     'POST', 'item/add', {'base64': 'iVBORw0KGgo=', 'name': 'n', 'annotation': 'a', 'website': 'https://example.com',
                          'id': 'CUSTOMID'}, {'id': 'CUSTOMID'}, 'CUSTOMID'),
    ('item.add_many', lambda v2: v2.item.add_many([{'url': 'https://example.com/1.jpg', 'name': 'Photo 1'},
                                                   {'bookmarkURL': 'https://www.example.com'}]),
     'POST', 'item/add', {'items': [{'url': 'https://example.com/1.jpg', 'name': 'Photo 1'},
                                    {'bookmarkURL': 'https://www.example.com'}]},
     {'ids': ['A', 'B']}, ['A', 'B']),
    ('item.update every field', lambda v2: v2.item.update(
        'I1', name='n', tags=['t1', 't2'], folders=['F1'], annotation='a', url='https://example.com', star=5,
        modification_time=1700000000000, no_thumbnail=True, no_preview=False, is_deleted=False),
     'POST', 'item/update', {
         'id': 'I1', 'name': 'n', 'tags': ['t1', 't2'], 'folders': ['F1'], 'annotation': 'a',
         'url': 'https://example.com', 'star': 5, 'modificationTime': 1700000000000, 'noThumbnail': True,
         'noPreview': False, 'isDeleted': False}, {'id': 'I1'}, {'id': 'I1'}),
    ('item.update only given fields', lambda v2: v2.item.update('I1', star=0), 'POST', 'item/update',
     {'id': 'I1', 'star': 0}, {'id': 'I1', 'star': 0}, {'id': 'I1', 'star': 0}),
    ('item.update to trash', lambda v2: v2.item.update('I1', is_deleted=True), 'POST', 'item/update',
     {'id': 'I1', 'isDeleted': True}, {'id': 'I1'}, {'id': 'I1'}),
    ('item.set_custom_thumbnail', lambda v2: v2.item.set_custom_thumbnail('I1', 'C:\\thumbs\\custom.png'),
     'POST', 'item/setCustomThumbnail', {'itemId': 'I1', 'filePath': 'C:\\thumbs\\custom.png'}, True, True),
    ('item.refresh_thumbnail', lambda v2: v2.item.refresh_thumbnail('I1'), 'POST', 'item/refreshThumbnail',
     {'itemId': 'I1'}, True, True),
    ('item.get_comments', lambda v2: v2.item.get_comments('I1'), 'GET', 'item/getComments', {'id': 'I1'},
     [{'id': 'C1', 'annotation': 'Face area'}], [{'id': 'C1', 'annotation': 'Face area'}]),
    ('item.add_comment image', lambda v2: v2.item.add_comment('I1', 'face', x=350, y=480, width=380, height=400),
     'POST', 'item/addComment', {'id': 'I1', 'annotation': 'face', 'x': 350, 'y': 480, 'width': 380, 'height': 400},
     {'id': 'C1'}, {'id': 'C1'}),
    ('item.add_comment video at 0s', lambda v2: v2.item.add_comment('V1', 'start', duration=0),
     'POST', 'item/addComment', {'id': 'V1', 'annotation': 'start', 'duration': 0}, {'id': 'C2'}, {'id': 'C2'}),
    ('item.update_comment text', lambda v2: v2.item.update_comment('I1', 'C1', 'new text'),
     'POST', 'item/updateComment', {'id': 'I1', 'commentId': 'C1', 'annotation': 'new text'}, True, True),
    ('item.update_comment area', lambda v2: v2.item.update_comment('I1', 'C1', x=5, width=10),
     'POST', 'item/updateComment', {'id': 'I1', 'commentId': 'C1', 'x': 5, 'width': 10}, True, True),
    ('item.remove_comment', lambda v2: v2.item.remove_comment('I1', 'C1'), 'POST', 'item/removeComment',
     {'id': 'I1', 'commentId': 'C1'}, True, True),
    # ---- folder ----
    ('folder.get default', lambda v2: v2.folder.get(), 'POST', 'folder/get', {}, PAGE, PAGE),
    ('folder.get filters', lambda v2: v2.folder.get(folder_id='F1', folder_ids=['F1', 'F2'], is_selected=False,
                                                    is_recent=True, offset=0, limit=10),
     'POST', 'folder/get', {'id': 'F1', 'ids': ['F1', 'F2'], 'isSelected': False, 'isRecent': True, 'offset': 0,
                            'limit': 10}, PAGE, PAGE),
    ('folder.create', lambda v2: v2.folder.create('My New Folder'), 'POST', 'folder/create',
     {'name': 'My New Folder'}, {'id': 'NF'}, {'id': 'NF'}),
    ('folder.create subfolder', lambda v2: v2.folder.create('Sub', description='d', parent='P1'),
     'POST', 'folder/create', {'name': 'Sub', 'description': 'd', 'parent': 'P1'}, {'id': 'NF'}, {'id': 'NF'}),
    ('folder.update', lambda v2: v2.folder.update('F1', name='Renamed', description='d', tags=['t'],
                                                  icon_color='green', parent='P2'),
     'POST', 'folder/update', {'id': 'F1', 'name': 'Renamed', 'description': 'd', 'tags': ['t'],
                               'iconColor': 'green', 'parent': 'P2'}, {'id': 'F1'}, {'id': 'F1'}),
    ('folder.update move to root', lambda v2: v2.folder.update('F1', move_to_root=True), 'POST', 'folder/update',
     {'id': 'F1', 'parent': None}, {'id': 'F1'}, {'id': 'F1'}),
    # ---- smart folder ----
    ('smart_folder.get', lambda v2: v2.smart_folder.get(), 'POST', 'smartFolder/get', {}, [{'id': 'S1'}],
     [{'id': 'S1'}]),
    ('smart_folder.get ids', lambda v2: v2.smart_folder.get(smart_folder_id='S1', smart_folder_ids=['S1', 'S2']),
     'POST', 'smartFolder/get', {'id': 'S1', 'ids': ['S1', 'S2']}, [{'id': 'S1'}], [{'id': 'S1'}]),
    ('smart_folder.create', lambda v2: v2.smart_folder.create('Large PNGs', CONDITIONS, icon_color='blue',
                                                              parent='S0'),
     'POST', 'smartFolder/create', {'name': 'Large PNGs', 'conditions': CONDITIONS, 'iconColor': 'blue',
                                    'parent': 'S0'}, {'id': 'S9'}, {'id': 'S9'}),
    ('smart_folder.update', lambda v2: v2.smart_folder.update('S1', name='n', conditions=CONDITIONS,
                                                              description='d', icon='i', icon_color='red'),
     'POST', 'smartFolder/update', {'id': 'S1', 'name': 'n', 'conditions': CONDITIONS, 'description': 'd',
                                    'icon': 'i', 'iconColor': 'red'}, {'id': 'S1'}, {'id': 'S1'}),
    ('smart_folder.remove', lambda v2: v2.smart_folder.remove('S1'), 'POST', 'smartFolder/remove', {'id': 'S1'},
     True, True),
    ('smart_folder.get_items', lambda v2: v2.smart_folder.get_items('S1', order_by='-CREATEDATE', fields=['id']),
     'POST', 'smartFolder/getItems', {'smartFolderId': 'S1', 'orderBy': '-CREATEDATE', 'fields': ['id']},
     [{'id': 'I1'}], [{'id': 'I1'}]),
    ('smart_folder.get_rules', lambda v2: v2.smart_folder.get_rules(), 'GET', 'smartFolder/getRules', None,
     {'width': {'methods': ['>']}}, {'width': {'methods': ['>']}}),
    # ---- tag ----
    ('tag.get', lambda v2: v2.tag.get(name='design', limit=100), 'POST', 'tag/get', {'name': 'design', 'limit': 100},
     PAGE, PAGE),
    ('tag.get_recent', lambda v2: v2.tag.get_recent(), 'GET', 'tag/getRecentTags', None, PAGE, PAGE),
    ('tag.get_recent paged', lambda v2: v2.tag.get_recent(offset=50, limit=100), 'GET', 'tag/getRecentTags',
     {'offset': 50, 'limit': 100}, PAGE, PAGE),
    ('tag.get_starred', lambda v2: v2.tag.get_starred(limit=5), 'GET', 'tag/getStarredTags', {'limit': 5},
     PAGE, PAGE),
    ('tag.rename', lambda v2: v2.tag.rename('old-tag-name', 'new-tag-name'), 'POST', 'tag/update',
     {'originalName': 'old-tag-name', 'name': 'new-tag-name'}, {'name': 'new-tag-name'}, {'name': 'new-tag-name'}),
    ('tag.merge', lambda v2: v2.tag.merge('photograph', 'photography'), 'POST', 'tag/merge',
     {'source': 'photograph', 'target': 'photography'}, {'affectedItems': 25, 'sourceRemoved': True},
     {'affectedItems': 25, 'sourceRemoved': True}),
    # ---- tag group ----
    ('tag_group.get', lambda v2: v2.tag_group.get(), 'GET', 'tagGroup/get', None, PAGE, PAGE),
    ('tag_group.create', lambda v2: v2.tag_group.create('Color Palette', ('warm', 'cool'), description='d'),
     'POST', 'tagGroup/create', {'name': 'Color Palette', 'tags': ['warm', 'cool'], 'description': 'd'},
     {'id': 'G1'}, {'id': 'G1'}),
    ('tag_group.update', lambda v2: v2.tag_group.update('G1', 'Updated', ['t1'], color='green'),
     'POST', 'tagGroup/update', {'id': 'G1', 'name': 'Updated', 'tags': ['t1'], 'color': 'green'},
     {'id': 'G1'}, {'id': 'G1'}),
    ('tag_group.remove', lambda v2: v2.tag_group.remove('G1'), 'POST', 'tagGroup/remove', {'id': 'G1'}, True, True),
    ('tag_group.add_tags', lambda v2: v2.tag_group.add_tags('G1', ['modern'], remove_from_source=True),
     'POST', 'tagGroup/addTags', {'groupId': 'G1', 'tags': ['modern'], 'removeFromSource': True},
     {'id': 'G1'}, {'id': 'G1'}),
    ('tag_group.remove_tags', lambda v2: v2.tag_group.remove_tags('G1', ['outdated']), 'POST', 'tagGroup/removeTags',
     {'groupId': 'G1', 'tags': ['outdated']}, {'id': 'G1'}, {'id': 'G1'}),
    # ---- library / app ----
    ('library.info', lambda v2: v2.library.info(), 'GET', 'library/info', None, {'name': 'L'}, {'name': 'L'}),
    ('library.history', lambda v2: v2.library.history(offset=0, limit=10), 'GET', 'library/history',
     {'offset': 0, 'limit': 10}, PAGE, PAGE),
    ('library.switch', lambda v2: v2.library.switch('D:\\Eagle\\Design.library'), 'POST', 'library/switch',
     {'libraryPath': 'D:\\Eagle\\Design.library'}, True, True),
    ('app.info', lambda v2: v2.app.info(), 'GET', 'app/info', None, {'version': '4.0.0'}, {'version': '4.0.0'}),
    # ---- AI search ----
    ('ai_search.is_installed', lambda v2: v2.ai_search.is_installed(), 'GET', 'aiSearch/isInstalled', None,
     True, True),
    ('ai_search.is_ready', lambda v2: v2.ai_search.is_ready(), 'GET', 'aiSearch/isReady', None, True, True),
    ('ai_search.is_starting', lambda v2: v2.ai_search.is_starting(), 'GET', 'aiSearch/isStarting', None,
     False, False),
    ('ai_search.is_syncing', lambda v2: v2.ai_search.is_syncing(), 'GET', 'aiSearch/isSyncing', None, False, False),
    ('ai_search.get_sync_status', lambda v2: v2.ai_search.get_sync_status(), 'GET', 'aiSearch/getSyncStatus', None,
     {'progress': 1.0}, {'progress': 1.0}),
    ('ai_search.check_service_health', lambda v2: v2.ai_search.check_service_health(), 'GET',
     'aiSearch/checkServiceHealth', None, {'healthy': True}, {'healthy': True}),
    ('ai_search.search_by_text', lambda v2: v2.ai_search.search_by_text('an orange cat'), 'POST',
     'aiSearch/searchByText', {'query': 'an orange cat'}, {'results': []}, {'results': []}),
    ('ai_search.search_by_text limit', lambda v2: v2.ai_search.search_by_text('logo', limit=20), 'POST',
     'aiSearch/searchByText', {'query': 'logo', 'options': {'limit': 20}}, {'results': []}, {'results': []}),
    ('ai_search.search_by_base64', lambda v2: v2.ai_search.search_by_base64('/9j/4AAQ', limit=10), 'POST',
     'aiSearch/searchByBase64', {'base64': '/9j/4AAQ', 'options': {'limit': 10}}, {'results': []}, {'results': []}),
    ('ai_search.search_by_item_id', lambda v2: v2.ai_search.search_by_item_id('I1', options={'limit': 3}),
     'POST', 'aiSearch/searchByItemId', {'itemId': 'I1', 'options': {'limit': 3}}, {'results': []},
     {'results': []}),
    # ---- escape hatch ----
    ('request GET relative', lambda v2: v2.request('GET', 'item/countAll'), 'GET', 'item/countAll', None, 3, 3),
    ('request POST full path', lambda v2: v2.request('post', '/api/v2/tag/merge', body={'source': 'a', 'target': 'b'}),
     'POST', 'tag/merge', {'source': 'a', 'target': 'b'}, {'affectedItems': 0}, {'affectedItems': 0}),
    ('request POST without body', lambda v2: v2.request('POST', 'item/get'), 'POST', 'item/get', {}, PAGE, PAGE),
]


class V2TestCase(MockedHTTP):

    def setUp(self):
        super().setUp()
        self.v2 = Eagle().v2

    def sent(self):
        """(HTTP method, path, query params or JSON body) of the only request sent."""
        calls = [('GET', c) for c in self.get.call_args_list] + [('POST', c) for c in self.post.call_args_list]
        self.assertEqual(len(calls), 1, calls)
        method, (args, kwargs) = calls[0]
        self.assertTrue(args[0].startswith(HOST + '/api/v2/'), args[0])
        path = args[0][len(HOST + '/api/v2/'):]
        return method, path, kwargs.get('params') if method == 'GET' else kwargs['json']


class TestEveryEndpoint(V2TestCase):

    def test_request_and_return_value(self):
        for name, call, method, path, sent, data, expected in CASES:
            with self.subTest(name):
                self.get.reset_mock()
                self.post.reset_mock()
                self.reply({'status': 'success', 'data': data})
                self.assertEqual(call(self.v2), expected)
                self.assertEqual(self.sent(), (method, path, sent))
                if method == 'POST':
                    self.assertNotIn('params', self.post.call_args[1])  # no token configured

    def test_every_endpoint_raises_on_eagle_error(self):
        for name, call, *_ in CASES:
            with self.subTest(name):
                self.reply({'status': 'error', 'message': 'Item not found'}, status_code=400)
                with self.assertRaises(EagleAPIError) as ctx:
                    call(self.v2)
                self.assertIn('Item not found', str(ctx.exception))
                self.assertEqual(ctx.exception.status_code, 400)
                self.assertTrue(ctx.exception.endpoint.startswith('/api/v2/'))

    def test_every_public_method_is_covered(self):
        covered = {name.split(' ')[0] for name, *_ in CASES}
        covered |= {'item.iterate', 'item.iterate_query', 'item.get_by_id', 'folder.iterate', 'tag.iterate',
                    'library.icon'}  # tested below
        public = set()
        for section in ('item', 'folder', 'smart_folder', 'tag', 'tag_group', 'library', 'app', 'ai_search'):
            api = getattr(self.v2, section)
            public |= {'{}.{}'.format(section, m) for m in dir(api) if not m.startswith('_')}
        self.assertEqual(public - covered, set())


class TestTokenAndSetup(V2TestCase):

    def test_token_on_get_and_post(self):
        self.reply({'status': 'success', 'data': PAGE})
        v2 = EagleV2('http://192.168.1.100:41595', token='f366c476')
        v2.item.get(tags=['design'], limit=20)
        args, kwargs = self.post.call_args
        self.assertEqual(args[0], 'http://192.168.1.100:41595/api/v2/item/get')
        self.assertEqual(kwargs['params'], {'token': 'f366c476'})
        self.assertEqual(kwargs['json'], {'tags': ['design'], 'limit': 20})
        v2.library.history(limit=5)
        self.assertEqual(self.get.call_args[1]['params'], {'limit': 5, 'token': 'f366c476'})

    def test_token_from_environment(self):
        os.environ['EAGLE_API_TOKEN'] = 'env-token'
        self.reply({'status': 'success', 'data': {}})
        EagleV2().app.info()
        self.assertEqual(self.get.call_args[1]['params'], {'token': 'env-token'})

    def test_old_eagle_without_v2(self):
        self.reply(status_code=404, content=b'Not Found', content_type='text/plain', not_json=True)
        with self.assertRaises(EagleResponseError) as ctx:
            self.v2.item.count_all()
        self.assertIn('4.0 Build 21', str(ctx.exception))

    def test_eagle_shares_its_connection_settings(self):
        self.reply({'status': 'success', 'data': {}})
        eagle = Eagle(base_url='http://10.0.0.5:41595', token='t', timeout=2)
        eagle.v2.app.info()
        args, kwargs = self.get.call_args
        self.assertEqual(args[0], 'http://10.0.0.5:41595/api/v2/app/info')
        self.assertEqual((kwargs['params'], kwargs['timeout']), ({'token': 't'}, 2))

    def test_repr(self):
        self.assertEqual(repr(self.v2), "EagleV2('http://localhost:41595')")
        self.assertIn('/api/v2/item/', repr(self.v2.item))


class TestPagination(V2TestCase):

    def serve(self, rows, cap=None, total=True):
        """Answer item/get like Eagle: slice rows by offset/limit (optionally capping the limit)."""
        def post(url, json=None, **kwargs):
            offset, limit = json.get('offset', 0), json.get('limit', 50)
            if cap:
                limit = min(limit, cap)
            page = {'data': rows[offset:offset + limit], 'offset': offset, 'limit': limit}
            if total:
                page['total'] = len(rows)
            return fake_response({'status': 'success', 'data': page if total else page['data']})
        self.post.side_effect = post

    def offsets(self):
        return [c[1]['json'].get('offset') for c in self.post.call_args_list]

    def test_iterate_walks_every_page(self):
        rows = [{'id': str(n)} for n in range(7)]
        self.serve(rows)
        self.assertEqual(list(self.v2.item.iterate(page_size=3, tags=['cat'])), rows)
        self.assertEqual(self.offsets(), [0, 3, 6])
        self.assertTrue(all(c[1]['json']['tags'] == ['cat'] for c in self.post.call_args_list))

    def test_iterate_stops_on_an_exact_last_page(self):
        self.serve([{'id': str(n)} for n in range(6)])
        self.assertEqual(len(list(self.v2.item.iterate(page_size=3))), 6)
        self.assertEqual(self.offsets(), [0, 3])

    def test_iterate_trusts_total_when_eagle_caps_the_page(self):
        rows = [{'id': str(n)} for n in range(5)]
        self.serve(rows, cap=2)
        self.assertEqual(list(self.v2.item.iterate(page_size=10)), rows)
        self.assertEqual(self.offsets(), [0, 2, 4])

    def test_iterate_without_total_stops_on_a_short_page(self):
        self.serve([{'id': str(n)} for n in range(4)], total=False)
        self.assertEqual(len(list(self.v2.item.iterate(page_size=3))), 4)
        self.assertEqual(self.offsets(), [0, 3])

    def test_iterate_empty(self):
        self.serve([])
        self.assertEqual(list(self.v2.item.iterate()), [])

    def test_iterate_from_an_offset(self):
        self.serve([{'id': str(n)} for n in range(5)])
        self.assertEqual([r['id'] for r in self.v2.item.iterate(page_size=2, offset=3)], ['3', '4'])

    def test_iterate_query_folders_and_tags(self):
        self.serve([{'id': 'a'}, {'id': 'b'}])
        self.assertEqual(len(list(self.v2.item.iterate_query('cat', page_size=1))), 2)
        self.assertEqual(self.post.call_args[1]['json']['query'], 'cat')
        self.assertTrue(self.post.call_args[0][0].endswith('/api/v2/item/query'))
        self.post.reset_mock()
        self.assertEqual(len(list(self.v2.folder.iterate(is_recent=True))), 2)
        self.assertTrue(self.post.call_args[0][0].endswith('/api/v2/folder/get'))
        self.assertEqual(self.post.call_args[1]['json']['isRecent'], True)
        self.post.reset_mock()
        self.assertEqual(len(list(self.v2.tag.iterate(name='de'))), 2)
        self.assertEqual(self.post.call_args[1]['json'], {'name': 'de', 'offset': 0, 'limit': 200})

    def test_page_size_limits(self):
        for bad in (0, 1001):
            with self.subTest(bad), self.assertRaises(ValueError):
                list(self.v2.item.iterate(page_size=bad))
        self.post.assert_not_called()

    def test_iterate_is_lazy(self):
        self.serve([{'id': 'a'}])
        iterator = self.v2.item.iterate()
        self.post.assert_not_called()
        self.assertEqual(next(iterator), {'id': 'a'})


class TestHelpersAndValidation(V2TestCase):

    def test_get_by_id(self):
        self.reply({'status': 'success', 'data': PAGE})
        self.assertEqual(self.v2.item.get_by_id('M3QSGJNQTC2DG', fields=['id']), PAGE['data'][0])
        self.assertEqual(self.post.call_args[1]['json'], {'id': 'M3QSGJNQTC2DG', 'fields': ['id']})

    def test_get_by_id_missing(self):
        self.reply({'status': 'success', 'data': {'data': [], 'total': 0, 'offset': 0, 'limit': 50}})
        self.assertIsNone(self.v2.item.get_by_id('NOPE'))

    def test_get_by_id_when_eagle_answers_with_the_item_itself(self):
        self.reply({'status': 'success', 'data': {'id': 'I1', 'name': 'x'}})
        self.assertEqual(self.v2.item.get_by_id('I1'), {'id': 'I1', 'name': 'x'})

    def test_add_needs_exactly_one_source(self):
        for kwargs in ({}, {'name': 'n'}, {'url': 'https://example.com/a.jpg', 'path': '/a.jpg'}):
            with self.subTest(kwargs), self.assertRaises(ValueError):
                self.v2.item.add(**kwargs)
        self.post.assert_not_called()

    def test_add_many_size(self):
        for items in ([], [{'url': 'u'}] * 1001):
            with self.subTest(len(items)), self.assertRaises(ValueError):
                self.v2.item.add_many(items)
        self.post.assert_not_called()

    def test_comment_position(self):
        bad = [{}, {'x': 1, 'y': 2}, {'x': 1, 'y': 2, 'width': 3, 'height': 4, 'duration': 5}]
        for kwargs in bad:
            with self.subTest(kwargs), self.assertRaises(ValueError):
                self.v2.item.add_comment('I1', 'note', **kwargs)
        with self.assertRaises(ValueError):
            self.v2.item.update_comment('I1', 'C1', x=1, duration=2)
        self.post.assert_not_called()

    def test_folder_parent_and_root_together(self):
        with self.assertRaises(ValueError):
            self.v2.folder.update('F1', parent='P', move_to_root=True)

    def test_request_method(self):
        with self.assertRaises(ValueError):
            self.v2.request('DELETE', 'item/get')

    def test_library_icon(self):
        self.reply(content=b'\x89PNG', content_type='image/png')
        self.assertEqual(self.v2.library.icon('D:\\Eagle\\Design.library'), b'\x89PNG')
        args, kwargs = self.get.call_args
        self.assertEqual(args[0], HOST + '/api/v2/library/icon')
        self.assertEqual(kwargs['params'], {'libraryPath': 'D:\\Eagle\\Design.library'})

    def test_library_icon_error(self):
        self.reply({'status': 'error', 'message': 'Library not found'}, status_code=404)
        with self.assertRaises(EagleAPIError) as ctx:
            self.v2.library.icon('/missing.library')
        self.assertIn('Library not found', str(ctx.exception))

    def test_library_icon_not_json_error(self):
        self.reply(status_code=404, content=b'Not Found', content_type='text/plain', not_json=True)
        with self.assertRaises(EagleResponseError):
            self.v2.library.icon('/missing.library')



class TestSupportsV2(MockedHTTP):

    def test_new_eagle(self):
        self.assertIs(Eagle().supports_v2(), True)
        self.assertEqual(self.get.call_args[0][0], HOST + '/api/v2/app/info')

    def test_old_eagle(self):
        self.reply(status_code=404, content=b'Not Found', content_type='text/plain', not_json=True)
        self.assertIs(Eagle().supports_v2(), False)
        self.reply(ERROR)
        self.assertIs(Eagle().supports_v2(), False)

    def test_eagle_closed(self):
        self.get.side_effect = requests.exceptions.ConnectionError('refused')
        with self.assertRaises(EagleConnectionError):
            Eagle().supports_v2()


class TestDefaults(unittest.TestCase):
    """The defaults 1.2.0 shipped: Eagle's local address and 200 rows per page for the iterate methods."""

    def test_default_address(self):
        self.assertEqual(repr(EagleV2()), "EagleV2('http://localhost:41595')")

    def test_every_iterate_method_fetches_200_rows_per_page(self):
        v2 = EagleV2()
        for method in (v2.item.iterate, v2.item.iterate_query, v2.folder.iterate, v2.tag.iterate):
            with self.subTest(method=method.__qualname__):
                self.assertEqual(inspect.signature(method).parameters['page_size'].default, 200)


if __name__ == '__main__':
    unittest.main()
