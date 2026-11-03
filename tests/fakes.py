"""Shared fakes for the tests: a mocked HTTP layer instead of a running Eagle."""
import os
import unittest
from unittest import mock

HOST = 'http://localhost:41595'
SUCCESS = {'status': 'success', 'data': {'ok': True}}
ERROR = {'status': 'error', 'message': 'Item not found'}


def fake_response(payload=None, status_code=200, content=b'', content_type='application/json', not_json=False):
    """A stand-in for requests.Response carrying ``payload`` as its JSON body."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.headers = {'Content-Type': content_type}
    resp.content = content
    resp.text = content.decode('utf-8', 'replace')
    if not_json:
        resp.json.side_effect = ValueError('Expecting value: line 1 column 1 (char 0)')
    else:
        resp.json.return_value = payload
    return resp


class MockedHTTP(unittest.TestCase):
    """Replaces requests.get/post, and clears EAGLE_API_TOKEN, for each test."""

    #: Where requests.get/post are patched. Both names point at the same requests module.
    patched_requests = 'eaglewrapper.client.requests'

    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('EAGLE_API_TOKEN', None)
        self.get = mock.patch(self.patched_requests + '.get').start()
        self.post = mock.patch(self.patched_requests + '.post').start()
        self.addCleanup(mock.patch.stopall)
        self.reply(SUCCESS)

    def reply(self, payload=None, **kwargs):
        self.get.return_value = fake_response(payload, **kwargs)
        self.post.return_value = fake_response(payload, **kwargs)
