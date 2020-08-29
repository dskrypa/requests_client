#!/usr/bin/env python

__version__ = '2020.01.18-1'
__url__ = 'hxxp://example.org'
__author_email__ = 'example@fake.org'

import logging
import platform
import sys
import unittest
from argparse import ArgumentParser
from pathlib import Path

sys.path.append(Path(__file__).parents[1].as_posix())
from requests_client.user_agent import (
    generate_user_agent,
    USER_AGENT_SCRIPT_OS,
    USER_AGENT_SCRIPT_CONTACT_OS,
    USER_AGENT_SCRIPT_URL_OS,
    USER_AGENT_FIREFOX,
    OS_SUMMARIES,
)
from requests_client.client import RequestsClient

log = logging.getLogger(__name__)

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'en-US,en;q=0.5',
    # 'Connection': 'keep-alive',
    'Dnt': '1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0'
}


class UserAgentTest(unittest.TestCase):
    def test_ua_header_preserved(self):
        # noinspection PyTypeChecker
        client = RequestsClient(None, headers=HEADERS)
        self.assertEqual(client._headers['User-Agent'], HEADERS['User-Agent'])

    def test_ua_file_version_set(self):
        expected = '{}/{}'.format(Path(__file__).stem, __version__)
        user_agent = generate_user_agent(USER_AGENT_SCRIPT_OS)
        log.debug('\nUser-Agent: {}'.format(user_agent))
        self.assertTrue(user_agent.startswith(expected))

    def test_ua_file_version_unset(self):
        global __version__
        orig = __version__
        del __version__
        expected = '{}/{}'.format(Path(__file__).stem, '1.0')
        user_agent = generate_user_agent(USER_AGENT_SCRIPT_OS)
        log.debug('\nUser-Agent: {}'.format(user_agent))
        try:
            self.assertTrue(user_agent.startswith(expected))
        finally:
            __version__ = orig

    def test_ua_downgrade(self):
        email = 'example@fake.org'
        url = 'hxxp://example.org'
        base = generate_user_agent(USER_AGENT_SCRIPT_OS)
        med_email = generate_user_agent(USER_AGENT_SCRIPT_URL_OS, url=email)
        med_url = generate_user_agent(USER_AGENT_SCRIPT_URL_OS, url=url)
        full = generate_user_agent(USER_AGENT_SCRIPT_CONTACT_OS, email=email, url=url)
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_CONTACT_OS), full)
        global __author_email__, __url__
        del __author_email__
        del __url__
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_CONTACT_OS), base)
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_URL_OS), base)
        __url__ = url
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_CONTACT_OS), med_url)
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_URL_OS), med_url)
        del __url__
        __author_email__ = email
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_CONTACT_OS), med_email)
        self.assertEqual(generate_user_agent(USER_AGENT_SCRIPT_URL_OS), med_email)

    def test_firefox_ua(self):
        ua = generate_user_agent(USER_AGENT_FIREFOX, firefox_ver=80.0)
        expected = 'Mozilla/5.0 ({}; rv:80.0) Gecko/20100101 Firefox/80.0'.format(OS_SUMMARIES[platform.system()])
        self.assertEqual(expected, ua)


if __name__ == '__main__':
    parser = ArgumentParser(description='Utils Unit Tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Increase logging verbosity')
    args = parser.parse_args()
    log.setLevel(logging.DEBUG if args.verbose else logging.INFO)
    log.addHandler(logging.StreamHandler(sys.stdout))

    try:
        unittest.main(warnings='ignore', verbosity=2, exit=False)
    except KeyboardInterrupt:
        print()
