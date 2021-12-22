#!/usr/bin/env python
"""
Test the RequestsClient with actual HTTP requests.

:author: Doug Skrypa
"""

import asyncio
import logging
import os
import socket
import sys
import unittest
from concurrent.futures import as_completed, ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from typing import ContextManager

from flask import Flask, request

sys.path.append(Path(__file__).parents[1].as_posix())
from requests_client.client import RequestsClient
from requests_client.async_client import AsyncRequestsClient

log = logging.getLogger(__name__)


def find_free_port():
    s = socket.socket()
    s.bind(('', 0))
    return s, s.getsockname()[1]


@contextmanager
def flask_server() -> ContextManager[int]:
    print()
    response = 'Test app response'
    app = Flask(__name__)
    os.environ['FLASK_ENV'] = 'dev'

    @app.route('/')
    def root():
        return response

    @app.route('/shutdown')
    def shutdown_server():
        request.environ.get('werkzeug.server.shutdown')()
        return ''  # Prevents: TypeError: The view function did not return a valid response...

    sock, port = find_free_port()
    try:
        app_thread = Thread(target=app.run, args=('localhost', port))
        app_thread.start()

        yield port

        app_thread.join()
    finally:
        sock.close()


class RequestsClientFlaskTest(unittest.TestCase):
    def test_requests(self):
        expected = 'Test app response'
        with flask_server() as port:
            client = RequestsClient('localhost', port)
            threads = 5
            with ThreadPoolExecutor(max_workers=threads) as exectuor:
                _futures = [exectuor.submit(client.get, '/') for _ in range(threads)]
                for future in as_completed(_futures):
                    resp = future.result()
                    log.debug(f'Result: {resp}')
                    self.assertEqual(resp.text, expected)

            client.get('/shutdown', raise_errors=False)

    async def _test_async_requests(self, port: int):
        expected = 'Test app response'
        async with AsyncRequestsClient('localhost', port) as client:
            reqs = 5
            results = await asyncio.gather(*(client.get('/') for _ in range(reqs)))
            self.assertEqual(len(results), reqs)
            for resp in results:
                log.debug(f'Result: {resp}')
                self.assertEqual(resp.text, expected)
            await client.get('/shutdown', raise_errors=False)

    def test_async_requests(self):
        with flask_server() as port:
            asyncio.run(self._test_async_requests(port))


if __name__ == '__main__':
    try:
        unittest.main(warnings='ignore', verbosity=2, exit=False)
    except KeyboardInterrupt:
        print()
