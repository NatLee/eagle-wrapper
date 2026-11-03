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


if __name__ == '__main__':
    unittest.main()
