"""PyPI shows the README without the repository around it, so setup.py turns
every relative link in it into an absolute GitHub link, pinned to the release
tag. The README itself only uses relative links to this repository, so a
release's PyPI page keeps working when files move on the main branch later."""
import pathlib
import re
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETUP = runpy.run_path(str(ROOT / 'setup.py'), run_name='setup_under_test')
absolute_links = SETUP['absolute_links']

RAW = 'https://raw.githubusercontent.com/NatLee/eagle-wrapper/v9.9.9/'
PAGE = 'https://github.com/NatLee/eagle-wrapper/blob/v9.9.9/'


class TestReadmeLinks(unittest.TestCase):

    def test_embedded_images_point_at_the_file_in_the_release_tag(self):
        readme = ('<img src="doc/repo-logo.png" width="560">\n'
                  '![overview](doc/api-overview.png) <source srcset="doc/a.png">\n')
        self.assertEqual(absolute_links(readme, 'v9.9.9'), (
            '<img src="' + RAW + 'doc/repo-logo.png" width="560">\n'
            '![overview](' + RAW + 'doc/api-overview.png) <source srcset="' + RAW + 'doc/a.png">\n'))

    def test_links_point_at_the_github_page_in_the_release_tag(self):
        readme = 'See [`tests/`](tests/) and <a href="src/eaglewrapper/eagle.py">eagle.py</a>.'
        self.assertEqual(absolute_links(readme, 'v9.9.9'), (
            'See [`tests/`](' + PAGE + 'tests/) and <a href="' + PAGE + 'src/eaglewrapper/eagle.py">eagle.py</a>.'))

    def test_a_link_around_an_image_is_rewritten_too(self):
        readme = '[![License: MIT](https://img.shields.io/pypi/l/EagleWrapper.svg)](LICENSE)'
        self.assertEqual(absolute_links(readme, 'v9.9.9'),
                         '[![License: MIT](https://img.shields.io/pypi/l/EagleWrapper.svg)](' + PAGE + 'LICENSE)')

    def test_absolute_links_and_anchors_are_left_alone(self):
        readme = ('[issue #1](https://github.com/NatLee/eagle-wrapper/issues/1) [up](#installation) '
                  '<img src="https://avatars.githubusercontent.com/u/1"> [mail](mailto:a@b.c) '
                  '<a href="/NatLee">x</a> `eagle.add_from_url(\'doc/x.png\')`')
        self.assertEqual(absolute_links(readme, 'v9.9.9'), readme)

    def test_the_long_description_links_to_the_tag_of_this_version(self):
        version = SETUP['VERSION']
        description = SETUP['LONG_DESCRIPTION']
        self.assertIn('raw.githubusercontent.com/NatLee/eagle-wrapper/v{}/doc/repo-logo.png'.format(version),
                      description)
        self.assertEqual(absolute_links(description, 'v' + version), description)

    def test_the_readme_links_to_its_own_files_relatively(self):
        # Absolute links to this repository's files would bypass the rewrite above,
        # and would keep pointing at whatever branch they name.
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        self.assertEqual(
            re.findall(r'github(?:usercontent)?\.com/NatLee/eagle-wrapper/(?:blob|tree|raw|main)/', readme), [])


if __name__ == '__main__':
    unittest.main()
