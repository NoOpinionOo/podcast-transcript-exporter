import socket
import unittest
from email.message import Message

from spotify_transcript_app.online import (
    NetworkFetchError,
    RemoteUrlError,
    SafeHttpClient,
    validate_public_https_url,
)


def public_resolver(host, port, *, type):
    return [(socket.AF_INET, type, 6, "", ("93.184.216.34", port))]


def private_resolver(host, port, *, type):
    return [(socket.AF_INET, type, 6, "", ("127.0.0.1", port))]


class FakeResponse:
    def __init__(self, body, url, content_type="text/plain", **headers):
        self.body = body
        self.url = url
        self.status = 200
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        for name, value in headers.items():
            self.headers[name.replace("_", "-")] = str(value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, limit):
        return self.body[:limit]

    def geturl(self):
        return self.url


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return self.response


class OnlineSafetyTests(unittest.TestCase):
    def test_accepts_and_normalizes_public_https_url(self):
        remote = validate_public_https_url(" https://EXAMPLE.com/feed.xml?x=1 ")
        self.assertEqual(remote.host, "example.com")
        self.assertEqual(remote.url, "https://example.com/feed.xml?x=1")

    def test_rejects_unsafe_url_forms(self):
        values = [
            "http://example.com/feed.xml",
            "https://name:secret@example.com/feed.xml",
            "https://localhost/feed.xml",
            "https://127.0.0.1/feed.xml",
            "https://example.com:8443/feed.xml",
            "https://example.com/feed.xml#teil",
            "https://example.com\\feed.xml",
        ]
        for value in values:
            with self.subTest(value=value), self.assertRaises(RemoteUrlError):
                validate_public_https_url(value)

    def test_blocks_dns_results_that_are_not_global(self):
        opener = FakeOpener(FakeResponse(b"Text", "https://example.com/t.txt"))
        client = SafeHttpClient(resolver=private_resolver, opener=opener)
        with self.assertRaises(NetworkFetchError):
            client.fetch("https://example.com/t.txt", max_bytes=100, accept="text/plain")
        self.assertIsNone(opener.request)

    def test_fetch_has_limits_and_sends_no_credentials(self):
        response = FakeResponse(
            b"Ein veroeffentlichtes Transkript",
            "https://example.com/transkript.txt",
            Content_Length=34,
        )
        opener = FakeOpener(response)
        client = SafeHttpClient(resolver=public_resolver, opener=opener)
        resource = client.fetch(
            "https://example.com/transkript.txt",
            max_bytes=100,
            accept="text/plain",
        )
        self.assertEqual(resource.content_type, "text/plain")
        self.assertEqual(opener.timeout, 12)
        headers = {name.lower(): value for name, value in opener.request.header_items()}
        self.assertNotIn("authorization", headers)
        self.assertNotIn("cookie", headers)
        self.assertEqual(headers["accept-encoding"], "identity")

    def test_rejects_oversized_body_and_cross_domain_final_url(self):
        large = SafeHttpClient(
            resolver=public_resolver,
            opener=FakeOpener(FakeResponse(b"123456", "https://example.com/t.txt")),
        )
        with self.assertRaises(NetworkFetchError):
            large.fetch("https://example.com/t.txt", max_bytes=5, accept="text/plain")

        redirected = SafeHttpClient(
            resolver=public_resolver,
            opener=FakeOpener(FakeResponse(b"Text", "https://cdn.example.net/t.txt")),
        )
        with self.assertRaises(NetworkFetchError):
            redirected.fetch("https://example.com/t.txt", max_bytes=100, accept="text/plain")


if __name__ == "__main__":
    unittest.main()
