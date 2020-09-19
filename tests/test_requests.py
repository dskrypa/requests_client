#!/usr/bin/env python
"""
Test the RequestsClient with actual HTTP requests.

:author: Doug Skrypa
"""

import logging
import os
import socket
import sys
import unittest
from concurrent.futures import as_completed, ThreadPoolExecutor
from pathlib import Path
from threading import Thread

from flask import Flask, request

sys.path.append(Path(__file__).parents[1].as_posix())
from requests_client import RequestsClient

log = logging.getLogger(__name__)


def find_free_port():
    s = socket.socket()
    s.bind(('', 0))
    return s.getsockname()[1]


class RequestsClientFlaskTest(unittest.TestCase):
    def test_requests(self):
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

        port = find_free_port()
        app_thread = Thread(target=app.run, args=('localhost', port))
        app_thread.start()

        client = RequestsClient('localhost', port)
        threads = 5
        with ThreadPoolExecutor(max_workers=threads) as exectuor:
            _futures = [exectuor.submit(client.get, '/') for _ in range(threads)]
            for future in as_completed(_futures):
                resp = future.result()
                log.debug('Result: {}'.format(resp))
                self.assertEqual(resp.text, response)

        client.get('/shutdown', raise_errors=False)
        app_thread.join()


if __name__ == '__main__':
    try:
        unittest.main(warnings='ignore', verbosity=2, exit=False)
    except KeyboardInterrupt:
        print()
