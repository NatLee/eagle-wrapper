"""Code written for EagleWrapper 1.1.1 must keep working.

The expected signatures below were copied from the 1.1.1 source. A method may gain new
parameters only at the end and only with a default, so old positional and keyword
calls still mean the same thing.
"""
import inspect
import unittest

from eaglewrapper import Eagle, ImageData
from eaglewrapper import eagle as eagle_module

EMPTY = inspect.Parameter.empty
# 1.1.1 used mutable [] defaults; None now means the same thing (an empty list is sent).
SAME_AS_EMPTY_LIST = None

EAGLE_1_1_1 = {
    '__init__': [('domain', 'http://localhost'), ('port', 41595)],
    'check_success': [('response', EMPTY)],
    'get_img_info_from_lib_path': [('library_path', EMPTY), ('name_start_filters', SAME_AS_EMPTY_LIST),
                                   ('max_workers', 4)],
    'set_tag_with_id': [('item_id', EMPTY), ('tags', EMPTY)],
    'get_img_list_info': [('max_image_number', EMPTY), ('name_start_filter', '')],
    'get_application_info': [],
    'add_from_url': [('url', EMPTY), ('name', EMPTY), ('tags', SAME_AS_EMPTY_LIST), ('website', ''),
                     ('annotation', ''), ('modification_time', None), ('folder_id', None), ('headers', None)],
    'add_from_urls': [('items', EMPTY), ('folder_id', None)],
    'add_from_path': [('path', EMPTY), ('name', EMPTY), ('website', None), ('annotation', None), ('tags', None),
                      ('folder_id', None)],
    'add_from_paths': [('items', EMPTY), ('folder_id', None)],
    'add_bookmark': [('url', EMPTY), ('name', EMPTY), ('tags', None), ('thumbnail_base64', None),
                     ('modification_time', None), ('folder_id', None)],
    'get_item_info': [('item_id', EMPTY)],
    'get_thumbnail_path': [('item_id', EMPTY)],
    'list_items': [('limit', 200), ('offset', 0), ('order_by', None), ('keyword', None), ('ext', None),
                   ('tags', None), ('folders', None)],
    'move_to_trash': [('item_ids', EMPTY)],
    'refresh_palette': [('item_id', EMPTY)],
    'refresh_thumbnail': [('item_id', EMPTY)],
    'update_item': [('item_id', EMPTY), ('tags', None), ('annotation', None), ('url', None), ('star', None)],
    'create_folder': [('folder_name', EMPTY), ('parent_id', None)],
    'rename_folder': [('folder_id', EMPTY), ('new_name', EMPTY)],
    'update_folder': [('folder_id', EMPTY), ('new_name', None), ('new_description', None), ('new_color', None)],
    'list_folders': [],
    'get_recent_folders': [],
    'get_library_info': [],
    'get_library_history': [],
    'switch_library': [('library_path', EMPTY)],
}

IMAGE_DATA_1_1_1 = [('url', EMPTY), ('name', EMPTY), ('website', ''), ('tags', None), ('annotation', ''),
                    ('modificationTime', None), ('headers', None)]


class TestSignatures(unittest.TestCase):

    def check(self, func, expected):
        params = list(inspect.signature(func).parameters.values())[1:]  # drop self
        old = [(p.name, p.default) for p in params[:len(expected)]]
        self.assertEqual(old, expected)
        for p in params[:len(expected)]:
            self.assertEqual(p.kind, p.POSITIONAL_OR_KEYWORD, p.name)
        for p in params[len(expected):]:
            self.assertIsNot(p.default, EMPTY, 'new parameter {} needs a default'.format(p.name))

    def test_every_1_1_1_method_still_exists_with_the_same_parameters(self):
        for name, expected in EAGLE_1_1_1.items():
            with self.subTest(method=name):
                self.check(getattr(Eagle, name), expected)

    def test_image_data(self):
        self.check(ImageData.__init__, IMAGE_DATA_1_1_1)
        self.assertTrue(callable(ImageData.to_dict))

    def test_old_import_paths(self):
        self.assertIs(eagle_module.Eagle, Eagle)
        self.assertIs(eagle_module.ImageData, ImageData)
        # Tests written for 1.1.1 patched eaglewrapper.eagle.requests.get/post.
        self.assertTrue(hasattr(eagle_module, 'requests'))

    def test_attributes(self):
        eagle = Eagle()
        self.assertEqual((eagle.domain, eagle.port, eagle.host), ('http://localhost', 41595, 'http://localhost:41595'))

    def test_image_data_to_dict(self):
        data = ImageData('https://example.com/a.jpg', 'a').to_dict()
        self.assertEqual(data, {'url': 'https://example.com/a.jpg', 'name': 'a', 'website': '', 'tags': [],
                                'annotation': '', 'modificationTime': None, 'headers': {}})
        with self.assertRaises(ValueError):
            ImageData('', 'a')
        with self.assertRaises(ValueError):
            ImageData('https://example.com/a.jpg', '')


if __name__ == '__main__':
    unittest.main()
