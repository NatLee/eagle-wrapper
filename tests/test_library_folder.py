"""get_img_info_from_lib_path reads metadata.json files from a library folder on disk.

An Eagle library keeps one folder per image (`images/<id>.info/metadata.json`).
These tests build such a folder in a temporary directory, so no Eagle is needed.
"""
import json
import os
import shutil
import tempfile
import unittest

from eaglewrapper import Eagle


class LibraryFolderTestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.library = os.path.join(self.tmp, 'example.library')
        os.makedirs(self.library)
        self.eagle = Eagle()

    def add_image(self, item_id, name):
        folder = os.path.join(self.library, 'images', item_id + '.info')
        os.makedirs(folder)
        with open(os.path.join(folder, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump({'id': item_id, 'name': name}, f, ensure_ascii=False)

    def names(self, *args, **kwargs):
        return sorted(d['name'] for d in self.eagle.get_img_info_from_lib_path(self.library, *args, **kwargs))


class TestNameFilter(LibraryFolderTestCase):

    def setUp(self):
        super().setUp()
        self.add_image('A1', 'ぼっち・ざ・ろっく！')
        self.add_image('B2', 'example cat')
        self.add_image('C3', 'other')

    def test_without_filter_returns_every_image(self):
        self.assertEqual(self.names(), ['example cat', 'other', 'ぼっち・ざ・ろっく！'])

    def test_filtered_out_images_are_left_out(self):
        # They used to come back as empty {} entries.
        result = self.eagle.get_img_info_from_lib_path(self.library, ['ぼ'])
        self.assertEqual(result, [{'id': 'A1', 'name': 'ぼっち・ざ・ろっく！'}])

    def test_no_match_returns_empty_list(self):
        self.assertEqual(self.eagle.get_img_info_from_lib_path(self.library, ['zzz']), [])

    def test_unreadable_metadata_is_skipped(self):
        folder = os.path.join(self.library, 'images', 'D4.info')
        os.makedirs(folder)
        with open(os.path.join(folder, 'metadata.json'), 'w', encoding='utf-8') as f:
            f.write('{not json')
        self.assertEqual(self.names(), ['example cat', 'other', 'ぼっち・ざ・ろっく！'])

    def test_several_filters_must_all_match_by_default(self):
        # The 1.1.1 behaviour: a name has to start with every prefix.
        self.assertEqual(self.names(['example', 'ぼ']), [])
        self.assertEqual(self.names(['ex', 'exam']), ['example cat'])

    def test_a_single_string_is_one_prefix(self):
        # 1.1.1 treated every character of the string as a prefix of its own.
        self.assertEqual(self.names('ex'), ['example cat'])

    def test_positional_max_workers(self):
        self.assertEqual(self.names(['o'], 1), ['other'])

    def test_item_without_a_name_does_not_pass_a_name_filter(self):
        folder = os.path.join(self.library, 'images', 'E5.info')
        os.makedirs(folder)
        with open(os.path.join(folder, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump({'id': 'E5'}, f)
        result = self.eagle.get_img_info_from_lib_path(self.library, ['o'])
        self.assertEqual([d['id'] for d in result], ['C3'])
        self.assertIn('E5', [d['id'] for d in self.eagle.get_img_info_from_lib_path(self.library)])

    def test_missing_library_folder_gives_empty_list(self):
        self.assertEqual(self.eagle.get_img_info_from_lib_path(os.path.join(self.tmp, 'nope.library')), [])


class TestLibraryMetadata(LibraryFolderTestCase):
    """The library folder has its own metadata.json (folders, smart folders, ...)."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.library, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump({'folders': [], 'smartFolders': [], 'quickAccess': [], 'tagsGroups': [],
                       'modificationTime': 1680000000000, 'applicationVersion': '3.0.0'}, f)
        self.add_image('A1', 'ぼっち・ざ・ろっく！')
        self.add_image('B2', 'example cat')

    def test_library_metadata_is_not_an_image(self):
        result = self.eagle.get_img_info_from_lib_path(self.library)
        self.assertEqual(sorted(d['id'] for d in result), ['A1', 'B2'])

    def test_library_metadata_is_not_an_image_with_filter(self):
        result = self.eagle.get_img_info_from_lib_path(self.library, ['ぼ'])
        self.assertEqual(result, [{'id': 'A1', 'name': 'ぼっち・ざ・ろっく！'}])


if __name__ == '__main__':
    unittest.main()
