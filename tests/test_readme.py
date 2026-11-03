"""The README tells users which Eagle APIs and builds this release covers; it must agree with the package.

eaglewrapper.SUPPORTED_APIS is the one place those facts live. When it changes (say a release wraps a
newer Eagle build), this test fails until the README says the same.
"""
import os
import unittest

from eaglewrapper import SUPPORTED_APIS

README = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'README.md')


class TestReadmeMatchesSupportedApis(unittest.TestCase):

    def setUp(self):
        with open(README, 'r', encoding='utf-8') as f:
            self.readme = f.read()

    def test_every_supported_api_fact_is_in_the_readme(self):
        for api in SUPPORTED_APIS:
            for fact in (api.name, api.prefix, 'Eagle ' + api.since, 'Eagle ' + api.covered_up_to, api.docs):
                with self.subTest(api=api.name, fact=fact):
                    self.assertIn(fact, self.readme)

    def test_printed_example_matches_the_package(self):
        # The Versioning section shows what this loop prints.
        for api in SUPPORTED_APIS:
            line = '{}: {}... needs Eagle {}+, wrapped up to Eagle {}'.format(
                api.name, api.prefix, api.since, api.covered_up_to)
            with self.subTest(api=api.name):
                self.assertIn(line, self.readme)


if __name__ == '__main__':
    unittest.main()
