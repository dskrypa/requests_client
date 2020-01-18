#!/usr/bin/env python

__version__ = '2020.01.18-1'
__url__ = 'hxxp://example.org'
__author_email__ = 'example@fake.org'

import logging
import sys
import unittest
from argparse import ArgumentParser
from pathlib import Path

sys.path.append(Path(__file__).parents[1].as_posix())
from requests_client.user_agent import (
    generate_user_agent, USER_AGENT_SCRIPT_OS, USER_AGENT_SCRIPT_CONTACT_OS, USER_AGENT_SCRIPT_URL_OS
)

log = logging.getLogger(__name__)


class UserAgentTest(unittest.TestCase):
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
