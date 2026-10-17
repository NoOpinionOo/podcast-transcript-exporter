import json
import time
import unittest

from spotify_transcript_app.spotify_client import (
    BUNDLED_SECRETS,
    HttpResult,
    SpotifyTranscriptClient,
    SpotifyTranscriptError,
    generate_totp,
    validate_sp_dc,
)


EPISODE_ID = "6jJ5d9puZD5hMG6T2PsmJz"
EPISODE_URL = f"https://open.spotify.com/episode/{EPISODE_ID}?si=test"
COOKIE = "A" * 80


def response(url: str, status: int, value) -> HttpResult:
    body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
    return HttpResult(status, body, url)


class FakeSpotifyTransport:
    def __init__(self, *, transcript_status: int = 200) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.transcript_status = transcript_status
        self.token_counter = 0

    def __call__(self, url, headers, _timeout, _max_bytes):
        self.calls.append((url, dict(headers)))
        if "secretDict.json" in url:
            return response(url, 500, {})
        if url.endswith("/api/server-time"):
            return response(url, 200, {"serverTime": 1_725_537_600})
        if "/api/token?" in url:
            self.token_counter += 1
            return response(
                url,
                200,
                {
                    "accessToken": f"token-{self.token_counter}",
                    "isAnonymous": False,
                    "accessTokenExpirationTimestampMs": int((time.time() + 3600) * 1000),
                },
            )
        if "transcript-read-along" in url:
            if self.transcript_status != 200:
                return response(url, self.transcript_status, {})
            return response(
                url,
                200,
                {
                    "language": "de",
                    "episodeName": "33 Regeln",
                    "showName": "Intueas Philosophy",
                    "section": [
                        {"title": {"title": "Speaker 1"}, "startMs": 0},
                        {
                            "text": {"sentence": {"text": "Erster Satz.", "startMs": 1000}}
                        },
                        {
                            "text": {"sentence": {"text": "Zweiter Satz.", "startMs": 3000}}
                        },
                    ],
                },
            )
        if "/embed/episode/" in url:
            payload = {
                "props": {
                    "pageProps": {
                        "state": {
                            "data": {
                                "entity": {
                                    "name": "33 Regeln, die dein Leben radikal vereinfachen",
                                    "subtitle": "Intueas Philosophy",
                                    "duration": 5000,
                                }
                            }
                        }
                    }
                }
            }
            html = f'<script id="__NEXT_DATA__">{json.dumps(payload)}</script>'.encode()
            return HttpResult(200, html, url)
        raise AssertionError(f"Unerwartete URL: {url}")


class SpotifyClientTests(unittest.TestCase):
    def test_cookie_validation_and_totp_vector(self):
        self.assertEqual(validate_sp_dc("sp_dc=" + COOKIE), COOKIE)
        with self.assertRaises(SpotifyTranscriptError):
            validate_sp_dc("zu-kurz")
        self.assertEqual(generate_totp(1_725_537_600, BUNDLED_SECRETS[61]), "005549")

    def test_fetch_normalizes_spotify_json(self):
        transport = FakeSpotifyTransport()
        client = SpotifyTranscriptClient(transport)

        transcript = client.fetch(EPISODE_URL, COOKIE)

        self.assertEqual(transcript.title, "33 Regeln, die dein Leben radikal vereinfachen")
        self.assertEqual(transcript.show, "Intueas Philosophy")
        self.assertEqual(transcript.language, "de")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].speaker, "Speaker 1")
        self.assertEqual(transcript.segments[0].end_ms, 3000)
        self.assertEqual(transcript.segments[1].end_ms, 6000)

    def test_cookie_is_sent_only_to_token_endpoint(self):
        transport = FakeSpotifyTransport()
        client = SpotifyTranscriptClient(transport)

        client.fetch(EPISODE_URL, COOKIE)

        cookie_calls = [url for url, headers in transport.calls if "Cookie" in headers]
        self.assertTrue(cookie_calls)
        self.assertTrue(all("open.spotify.com/api/token" in url for url in cookie_calls))
        for url, headers in transport.calls:
            if "secretDict.json" in url or "transcript-read-along" in url:
                self.assertNotIn("Cookie", headers)

    def test_reports_missing_transcript(self):
        client = SpotifyTranscriptClient(FakeSpotifyTransport(transcript_status=404))
        with self.assertRaisesRegex(SpotifyTranscriptError, "kein abrufbares Transkript"):
            client.fetch(EPISODE_URL, COOKIE)

    def test_retries_one_rejected_access_token(self):
        class RetryTransport(FakeSpotifyTransport):
            def __init__(self):
                super().__init__()
                self.transcript_counter = 0

            def __call__(self, url, headers, timeout, max_bytes):
                if "transcript-read-along" in url:
                    self.transcript_counter += 1
                    if self.transcript_counter == 1:
                        self.calls.append((url, dict(headers)))
                        return response(url, 401, {})
                return super().__call__(url, headers, timeout, max_bytes)

        transport = RetryTransport()
        transcript = SpotifyTranscriptClient(transport).fetch(EPISODE_URL, COOKIE)
        self.assertEqual(transcript.language, "de")
        self.assertEqual(transport.token_counter, 2)

    def test_rejects_cross_host_redirect(self):
        def redirected(url, headers, timeout, max_bytes):
            return HttpResult(200, b"{}", "https://example.com/intercept")

        client = SpotifyTranscriptClient(redirected, refresh_secrets=False)
        with self.assertRaisesRegex(SpotifyTranscriptError, "Weiterleitung"):
            client.fetch(EPISODE_URL, COOKIE)


if __name__ == "__main__":
    unittest.main()
