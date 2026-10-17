import tempfile
import unittest
from pathlib import Path

from spotify_transcript_app.service import TranscriptService
from spotify_transcript_app.sources import ExampleTranscriptSource


VALID_URL = "https://open.spotify.com/episode/0123456789ABCDEFGHIJKL"


class ServiceTests(unittest.TestCase):
    def test_example_source_is_explicitly_offline(self):
        source = ExampleTranscriptSource()
        self.assertFalse(source.network_access)

    def test_service_loads_local_example(self):
        transcript = TranscriptService(ExampleTranscriptSource()).fetch_from_url(VALID_URL)
        self.assertEqual(transcript.language, "de")
        self.assertEqual(transcript.source_url, VALID_URL)
        self.assertGreaterEqual(len(transcript.segments), 4)
        self.assertIn("kein Spotify-Inhalt", transcript.notice)

    def test_service_imports_local_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "folge.srt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\nLokaler Test.\n",
                encoding="utf-8",
            )
            service = TranscriptService(ExampleTranscriptSource())
            transcript = service.import_file(path)
            self.assertEqual(transcript.segments[0].text, "Lokaler Test.")
            self.assertEqual(transcript.timing_origin, "provided")


if __name__ == "__main__":
    unittest.main()
