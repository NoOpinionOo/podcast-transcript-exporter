import unittest
from dataclasses import dataclass

from spotify_transcript_app.youtube_client import (
    YouTubeTranscriptClient,
    YouTubeTranscriptError,
    is_youtube_host,
    parse_youtube_url,
)


VIDEO_ID = "dQw4w9WgXcQ"


@dataclass
class FakeSnippet:
    text: str
    start: float
    duration: float


class FakeFetched(list):
    def __init__(self, snippets, language, language_code, is_generated):
        super().__init__(snippets)
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated


class FakeTrack:
    def __init__(self, language, language_code, is_generated, snippets=None):
        self.language = language
        self.language_code = language_code
        self.is_generated = is_generated
        self.snippets = snippets or [FakeSnippet("Hallo Welt", 1.25, 2.5)]
        self.fetch_calls = []

    def fetch(self, preserve_formatting=False):
        self.fetch_calls.append(preserve_formatting)
        return FakeFetched(
            self.snippets,
            self.language,
            self.language_code,
            self.is_generated,
        )


class FakeApi:
    def __init__(self, tracks):
        self.tracks = tracks
        self.video_ids = []

    def list(self, video_id):
        self.video_ids.append(video_id)
        return self.tracks


class YouTubeClientTests(unittest.TestCase):
    def test_parses_normal_short_and_shorts_links(self):
        urls = [
            f"https://www.youtube.com/watch?v={VIDEO_ID}&t=20s",
            f"https://youtu.be/{VIDEO_ID}?si=test",
            f"https://youtube.com/shorts/{VIDEO_ID}",
            f"https://m.youtube.com/live/{VIDEO_ID}?feature=share",
        ]
        for url in urls:
            with self.subTest(url=url):
                parsed = parse_youtube_url(url)
                self.assertEqual(parsed.video_id, VIDEO_ID)
                self.assertEqual(
                    parsed.canonical_url,
                    f"https://www.youtube.com/watch?v={VIDEO_ID}",
                )

    def test_rejects_lookalike_hosts_and_invalid_ids(self):
        for url in (
            f"https://youtube.com.example.org/watch?v={VIDEO_ID}",
            "http://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=too-short",
        ):
            with self.subTest(url=url), self.assertRaises(YouTubeTranscriptError):
                parse_youtube_url(url)
        self.assertTrue(is_youtube_host(f"https://youtu.be/{VIDEO_ID}"))
        self.assertFalse(is_youtube_host("https://open.spotify.com/episode/test"))

    def test_prefers_german_even_when_english_is_manual(self):
        english = FakeTrack("English", "en", False)
        german = FakeTrack("Deutsch (automatisch)", "de", True)
        api = FakeApi([english, german])

        transcript = YouTubeTranscriptClient(lambda: api).fetch(
            f"https://youtu.be/{VIDEO_ID}"
        )

        self.assertEqual(api.video_ids, [VIDEO_ID])
        self.assertEqual(transcript.language, "de")
        self.assertEqual(transcript.segments[0].start_ms, 1250)
        self.assertEqual(transcript.segments[0].end_ms, 3750)
        self.assertEqual(english.fetch_calls, [])
        self.assertEqual(german.fetch_calls, [False])

    def test_falls_back_to_first_manual_non_german_track(self):
        arabic = FakeTrack("Arabic", "ar", False)
        english = FakeTrack("English", "en", False)
        french_generated = FakeTrack("Francais", "fr", True)
        api = FakeApi([arabic, english, french_generated])

        transcript = YouTubeTranscriptClient(lambda: api).fetch(
            f"https://www.youtube.com/watch?v={VIDEO_ID}"
        )

        self.assertEqual(transcript.language, "en")
        self.assertEqual(arabic.fetch_calls, [])
        self.assertEqual(english.fetch_calls, [False])
        self.assertEqual(french_generated.fetch_calls, [])

    def test_explicit_language_overrides_automatic_preference(self):
        german = FakeTrack("Deutsch", "de", False)
        french = FakeTrack("Français", "fr-FR", False)
        api = FakeApi([german, french])

        transcript = YouTubeTranscriptClient(lambda: api).fetch(
            f"https://youtu.be/{VIDEO_ID}",
            preferred_language="fr",
        )

        self.assertEqual(transcript.language, "fr-FR")
        self.assertEqual(german.fetch_calls, [])
        self.assertEqual(french.fetch_calls, [False])

    def test_unavailable_explicit_language_lists_alternatives(self):
        api = FakeApi(
            [FakeTrack("Deutsch", "de", False), FakeTrack("English", "en", False)]
        )
        with self.assertRaisesRegex(
            YouTubeTranscriptError,
            r"nicht verfügbar.*Deutsch \(de\).*English \(en\)",
        ):
            YouTubeTranscriptClient(lambda: api).fetch(
                f"https://youtu.be/{VIDEO_ID}",
                preferred_language="fr",
            )

    def test_empty_track_list_has_clear_error(self):
        api = FakeApi([])
        with self.assertRaisesRegex(YouTubeTranscriptError, "kein Transkript"):
            YouTubeTranscriptClient(lambda: api).fetch(f"https://youtu.be/{VIDEO_ID}")


if __name__ == "__main__":
    unittest.main()
