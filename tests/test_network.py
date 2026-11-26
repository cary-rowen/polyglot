# Copyright (C) 2025-2026 cary-rowen <cary-rowen@outlook.com>
# This file is covered by the GNU General Public License version 3 or later.
# See the file COPYING.txt for more details.

"""Small runnable checks for HTTP connection reuse."""

import unittest
from http.client import HTTPMessage
from unittest.mock import Mock, patch

try:
	from tests._nvdaStubs import installNvdaStubs
except ImportError:
	from _nvdaStubs import installNvdaStubs

installNvdaStubs()

import requests  # noqa: E402
from requests.cookies import extract_cookies_to_jar  # noqa: E402

from polyglot.common import network  # noqa: E402


class SharedSessionTest(unittest.TestCase):
	"""Check that engine requests share one pooled, cookie-free session."""

	def setUp(self) -> None:
		"""Start each check without a cached session."""
		network.closeSession()
		self.addCleanup(network.closeSession)

	def test_sessionUsesConnectionPool(self) -> None:
		"""Both schemes are mounted on an adapter that keeps connections alive."""
		session = network.getSession()
		for prefix in ("https://", "http://"):
			adapter = session.get_adapter(prefix + "example.com")
			self.assertEqual(adapter._pool_connections, network._POOL_CONNECTIONS)
			self.assertEqual(adapter._pool_maxsize, network._POOL_MAXSIZE)

	def test_sessionRejectsCookies(self) -> None:
		"""A shared session must not carry cookies between requests."""
		session = network.getSession()
		headers = HTTPMessage()
		headers["Set-Cookie"] = "session=value; Domain=example.com; Path=/"
		preparedRequest = requests.Request(method="GET", url="https://example.com/").prepare()
		rawResponse = Mock(_original_response=Mock(msg=headers))
		extract_cookies_to_jar(session.cookies, preparedRequest, rawResponse)
		self.assertEqual(len(session.cookies), 0)

	def test_closeSessionReleasesConnections(self) -> None:
		"""Closing releases the pool and the next caller gets a fresh session."""
		session = network.getSession()
		with patch.object(session, "close") as close:
			network.closeSession()
			close.assert_called_once()
		self.assertIsNot(network.getSession(), session)

	def test_sendRequestUsesTheSharedSession(self) -> None:
		"""Consecutive requests go through one shared session so connections are reused."""
		response = Mock(text="translated")
		with patch.object(requests.Session, "request", autospec=True, return_value=response) as request:
			for _unused in range(2):
				self.assertEqual(
					network.sendRequest(method="POST", url="https://example.com/api"),
					"translated",
				)
		self.assertEqual(request.call_count, 2)
		firstSession, secondSession = (call.args[0] for call in request.call_args_list)
		self.assertIs(firstSession, secondSession)
		self.assertIs(firstSession, network.getSession())

	def test_sendRequestKeepsCallerHeaders(self) -> None:
		"""Caller headers win while a default User-Agent is still supplied."""
		response = Mock(text="ok")
		with patch.object(requests.Session, "request", autospec=True, return_value=response) as request:
			network.sendRequest(
				method="GET",
				url="https://example.com/api",
				headers={"Authorization": "Bearer key"},
			)
		sentHeaders = request.call_args.kwargs["headers"]
		self.assertEqual(sentHeaders["Authorization"], "Bearer key")
		self.assertIn("User-Agent", sentHeaders)


if __name__ == "__main__":
	unittest.main()
