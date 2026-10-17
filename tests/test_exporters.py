import tempfile
import unittest
from pathlib import Path

from spotify_transcript_app.exporters import (
    ExportError,
    export_transcript,
    format_clock,
    render_markdown,
    render_srt,
    render_txt,
    safe_filename,
)
from spotify_transcript_app.models import Transcript, TranscriptSegment


def make_transcript() -> Transcript:
    return Transcript(
        title='Folge: "Test"?',
        show="Beispiel-Podcast",
        source_url="https://open.spotify.com/episode/0123456789ABCDEFGHIJKL",
        language="de",
        notice="Lokale Testdaten",
        segments=(
            TranscriptSegment(0, 1250, "Guten Morgen.", "Person 1"),
            TranscriptSegment(1250, 62000, "Schoen, dass Sie da sind.", "Person 2"),
        ),
    )


class ExporterTests(unittest.TestCase):
    def test_clock_formats(self):
        self.assertEqual(format_clock(62_345), "01:02")
        self.assertEqual(format_clock(3_662_345), "01:01:02")
        self.assertEqual(format_clock(62_345, srt=True), "00:01:02,345")

    def test_txt_timestamps_are_optional(self):
        without = render_txt(make_transcript(), False)
        with_timestamps = render_txt(make_transcript(), True)
        self.assertNotIn("[00:00]", without)
        self.assertIn("[00:00] Person 1: Guten Morgen.", with_timestamps)

    def test_markdown_contains_metadata_and_speaker(self):
        result = render_markdown(make_transcript(), True)
        self.assertIn("# Folge: \"Test\"?", result)
        self.assertIn("**Podcast:** Beispiel-Podcast", result)
        self.assertIn("**Person 2:**", result)

    def test_srt_always_contains_timecodes(self):
        result = render_srt(make_transcript())
        self.assertIn("00:00:00,000 --> 00:00:01,250", result)
        self.assertIn("2\n00:00:01,250 --> 00:01:02,000", result)

    def test_windows_safe_filename(self):
        self.assertEqual(safe_filename('A/B: "C"?', "txt"), "A B C.txt")
        self.assertEqual(safe_filename("CON", "md"), "_CON.md")
        with self.assertRaises(ExportError):
            safe_filename("Test", "exe")

    def test_writes_utf8_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ausgabe.txt"
            export_transcript(make_transcript(), target, "txt", True)
            self.assertIn("Schoen", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

