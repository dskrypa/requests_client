#!/usr/bin/env python

import asyncio
import logging
import socket
import sys
import time
import unittest
from argparse import ArgumentParser
from concurrent import futures
from contextlib import suppress
from pathlib import Path
from unittest.mock import MagicMock

from httpx import AsyncClient
from requests import RequestException

sys.path.append(Path(__file__).parents[1].as_posix())
from requests_client import RequestsClient, AsyncRequestsClient

log = logging.getLogger(__name__)


class RequestsClientTest(unittest.TestCase):
    def test_init_with_base_url(self):
        client = RequestsClient('https://localhost:1234/test')
        self.assertEqual(client.scheme, 'https')
        self.assertEqual(client.host, 'localhost')
        self.assertEqual(client.port, 1234)
        self.assertEqual(client.path_prefix, 'test/')

    def test_init_with_base_url_overrides(self):
        client = RequestsClient('https://localhost:1234/test', port=3456, path_prefix='/api/v1', scheme='http')
        self.assertEqual(client.scheme, 'http')
        self.assertEqual(client.host, 'localhost')
        self.assertEqual(client.port, 3456)
        self.assertEqual(client.path_prefix, 'api/v1/')

    def test_url_absolute_path(self):
        client = RequestsClient('localhost', path_prefix='/api/v1')
        expected = 'http://localhost/api/v2/test'
        self.assertEqual(client.url_for('/api/v2/test', relative=False), expected)
        self.assertEqual(client.url_for('api/v2/test', relative=False), expected)

    def test_url_relative_path(self):
        client = RequestsClient('localhost', path_prefix='/api/v1')
        expected = 'http://localhost/api/v1/test'
        self.assertEqual(client.url_for('test'), expected)
        self.assertEqual(client.url_for('/test'), expected)

    def test_update_url_parts(self):
        expected = 'https://localhost:1234/api/v1/'
        client = RequestsClient(expected)
        self.assertEqual(client.url_for(''), expected)
        client.port = 3456
        self.assertEqual(client.url_for(''), 'https://localhost:3456/api/v1/')

    def test_validator_on_multiple_sets(self):
        expected = 'https://localhost:1234/api/v1/'
        client = RequestsClient(expected)
        self.assertEqual(client.url_for(''), expected)
        client.port = 3456
        self.assertEqual(client.url_for(''), 'https://localhost:3456/api/v1/')
        with self.assertRaises(ValueError):
            client.port = 'test'
        self.assertEqual(client.url_for(''), 'https://localhost:3456/api/v1/')

    def test_explicit_user_agent(self):
        client = RequestsClient('localhost', headers={'User-Agent': 'test'})
        self.assertEqual(client._headers['User-Agent'], 'test')

    def test_threads_get_same_session(self):
        client = RequestsClient('localhost')
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            _futures = [executor.submit(_id_session, client), executor.submit(_id_session, client)]
            results = set(f.result() for f in futures.as_completed(_futures))

        self.assertEqual(len(results), 1)

    def test_threads_get_different_sessions(self):
        client = RequestsClient('localhost', local_sessions=True)
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            _futures = [executor.submit(_id_session, client), executor.submit(_id_session, client)]
            results = set(f.result() for f in futures.as_completed(_futures))

        self.assertEqual(len(results), 2)

    def test_threads_reuse_different_sessions(self):
        client = RequestsClient('localhost', local_sessions=True)
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            _futures = [executor.submit(_id_session, client) for _ in range(4)]
            results = set(f.result() for f in futures.as_completed(_futures))

        self.assertEqual(len(results), 2)

    def test_conflicting_args(self):
        with self.assertRaises(ValueError):
            RequestsClient('localhost:1234', port=3456)

    def test_logging(self):
        sock, port = find_free_port()
        expected = [
            (11, f'GET -> http://localhost:{port}/test?a=1'),
            (11, f'GET -> http://localhost:{port}/test'),
            (10, f'GET -> http://localhost:{port}/test'),
        ]
        try:
            with self.assertLogs('requests_client.base', level=logging.DEBUG) as captured:
                client = RequestsClient('localhost', port=port, log_lvl=11)
                with suppress(RequestException):
                    client.get('test', params={'a': 1}, timeout=0.01)
                with suppress(RequestException):
                    client.get('test', params={'a': 1}, timeout=0.01, log_params=False)
                with suppress(RequestException):
                    client.get('test', params={'a': 1}, timeout=0.01, log=False)
                client = RequestsClient('localhost', port=port, log_params=False)
                with suppress(RequestException):
                    client.get('test', params={'a': 1}, timeout=0.01)

            results = [(r.levelno, r.message) for r in captured.records]
            self.assertListEqual(results, expected)
        finally:
            sock.close()

    def test_new_session_after_close(self):
        client = RequestsClient('http://localhost:1234/', session_fn=MagicMock)
        with client:
            client.get('/')
            session_1 = client._RequestsClient__session  # type: MagicMock  # noqa
            self.assertTrue(session_1.request.called)
            self.assertFalse(session_1.close.called)
        self.assertTrue(session_1.close.called)
        client.get('/')
        session_2 = client._RequestsClient__session  # type: MagicMock  # noqa
        self.assertNotEqual(session_1, session_2)
        self.assertTrue(session_2.request.called)
        self.assertFalse(session_2.close.called)

    async def _test_async_session_set(self):
        client = AsyncRequestsClient('localhost:1234')
        session_a = await client.session  # noqa
        self.assertIsInstance(session_a, AsyncClient)
        with self.assertRaises(AttributeError):
            client.session = MagicMock()  # noqa

        await client.set_session(AsyncClient())
        session_b = await client.session  # noqa
        self.assertNotEqual(session_a, session_b)

    def test_async_session_set(self):
        asyncio.run(self._test_async_session_set())


def _id_session(client):
    time.sleep(0.01)  # Without a sleep, this returns fast enough for the executor to re-use the same thread
    return id(client.session), hash(client.session)


def find_free_port():
    s = socket.socket()
    s.bind(('', 0))
    return s, s.getsockname()[1]


if __name__ == '__main__':
    parser = ArgumentParser(description='Requests Client Unit Tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Increase logging verbosity')
    args = parser.parse_args()
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log.addHandler(logging.StreamHandler(sys.stdout))

    try:
        unittest.main(warnings='ignore', verbosity=2, exit=False)
    except KeyboardInterrupt:
        print()
