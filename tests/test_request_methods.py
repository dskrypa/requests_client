#!/usr/bin/env python

import logging
import sys
import unittest
from argparse import ArgumentParser
from unittest.mock import MagicMock

from requests_client.client import RequestsClient

log = logging.getLogger(__name__)


class RequestsClientTest(unittest.TestCase):
    def test_subclass_request_override(self):
        class TestRequestsClient(RequestsClient):
            request = MagicMock()

        client = TestRequestsClient('https://localhost:1234/test')
        client.get('/')
        self.assertTrue(TestRequestsClient.request.called)
        self.assertEqual(TestRequestsClient.request.call_args[0], ('GET', '/'))
        client.post('/test', data='test')
        self.assertEqual(TestRequestsClient.request.call_args[0], ('POST', '/test'))
        self.assertDictEqual(TestRequestsClient.request.call_args[1], {'data': 'test'})


if __name__ == '__main__':
    parser = ArgumentParser(description='Request Method Unit Tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Increase logging verbosity')
    args = parser.parse_args()
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log.addHandler(logging.StreamHandler(sys.stdout))

    try:
        unittest.main(warnings='ignore', verbosity=2, exit=False)
    except KeyboardInterrupt:
        print()
