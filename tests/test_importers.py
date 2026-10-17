import tempfile
import unittest
from pathlib import Path

from spotify_transcript_app.exporters import render_srt, render_txt
from spotify_transcript_app.importers import (
    TranscriptImportError,
    import_transcript_file,
    parse_srt,
    parse_txt,
    parse_vtt,
)


class ImporterTests(unittest.TestCase):
    def test_parses_srt_with_speaker_and_comma_timestamps(self):
        transcript = parse_srt(
            """1
00:00:01,250 --> 00:00:03,500
Anna: Guten Morgen.

2
00:00:03,500 --> 00:00:06,000
Willkommen zum Test.
""",
            "folge.srt",
        )
        self.assertEqual(transcript.title, "folge")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].speaker, "Anna")
        self.assertEqual(transcript.segments[0].start_ms, 1250)
        self.assertEqual(transcript.segments[1].end_ms, 6000)
        self.assertEqual(transcript.timing_origin, "provided")

    def test_parses_vtt_voice_tags_settings_and_notes(self):
        transcript = parse_vtt(
            """WEBVTT

NOTE Dieser Block wird ignoriert.

erste-marke
00:01.000 --> 00:04.250 align:start
<v Dr. Beispiel><b>Hallo</b> &amp; willkommen.</v>

00:04.250 --> 00:07.000
Zweite Zeile
""",
            "folge.vtt",
        )
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].speaker, "Dr. Beispiel")
        self.assertEqual(transcript.segments[0].text, "Hallo & willkommen.")
        self.assertEqual(transcript.segments[0].start_ms, 1000)

    def test_rejects_vtt_without_header(self):
        with self.assertRaises(TranscriptImportError):
            parse_vtt("00:00.000 --> 00:01.000\nText")

    def test_rejects_backwards_time_range(self):
        with self.assertRaises(TranscriptImportError):
            parse_srt("1\n00:00:05,000 --> 00:00:03,000\nText")

    def test_plain_txt_gets_estimated_timings(self):
        transcript = parse_txt(
            "Anna: Erster Absatz.\n\nZweiter Absatz ohne Sprecher.",
            "notizen.txt",
        )
        self.assertEqual(transcript.title, "notizen")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].speaker, "Anna")
        self.assertEqual(transcript.timing_origin, "estimated")
        self.assertIn("Schaetzzeiten", transcript.notice)

    def test_imports_own_txt_metadata_without_treating_it_as_body(self):
        transcript = parse_txt(
            """Titel der Folge
Podcast: Mein Podcast
Quelle: https://open.spotify.com/episode/0123456789ABCDEFGHIJKL
Sprache: de
Hinweis: Alte Notiz

Person 1: Erster Satz.
Person 2: Zweiter Satz.
""",
            "export.txt",
        )
        self.assertEqual(transcript.title, "Titel der Folge")
        self.assertEqual(transcript.show, "Mein Podcast")
        self.assertEqual(transcript.language, "de")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[1].speaker, "Person 2")

        reimported = parse_txt(render_txt(transcript, False), "erneut.txt")
        self.assertEqual(len(reimported.segments), 2)
        self.assertEqual(reimported.segments[0].text, "Erster Satz.")

    def test_srt_export_can_be_imported_again(self):
        original = parse_srt(
            "1\n00:00:00,000 --> 00:00:02,500\nPerson: Rundlauf.\n",
            "runde.srt",
        )
        reimported = parse_srt(render_srt(original), "runde-neu.srt")
        self.assertEqual(reimported.segments, original.segments)

    def test_file_loader_supports_utf16_and_rejects_other_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            txt_path = folder / "utf16.txt"
            txt_path.write_bytes("Eine lokale Zeile".encode("utf-16"))
            transcript = import_transcript_file(txt_path)
            self.assertEqual(transcript.segments[0].text, "Eine lokale Zeile")

            wrong_path = folder / "daten.json"
            wrong_path.write_text("{}", encoding="utf-8")
            with self.assertRaises(TranscriptImportError):
                import_transcript_file(wrong_path)

    def test_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "leer.txt"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(TranscriptImportError):
                import_transcript_file(path)


if __name__ == "__main__":
    unittest.main()
