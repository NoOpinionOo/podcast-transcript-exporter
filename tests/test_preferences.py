import json
import tempfile
import unittest
from pathlib import Path

from spotify_transcript_app.preferences import (
    Preferences,
    load_preferences,
    save_preferences,
)


class PreferencesTests(unittest.TestCase):
    def test_missing_file_uses_light_theme(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            self.assertEqual(load_preferences(path), Preferences(theme="light"))

    def test_invalid_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"theme": "neon", "secret": "ignore"}', encoding="utf-8")
            self.assertEqual(load_preferences(path), Preferences())

    def test_round_trip_stores_only_non_sensitive_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            preferences = Preferences(
                theme="dark",
                font_size=14,
                youtube_language="fr",
                export_directory=str(Path(directory)),
            )
            save_preferences(path, preferences)
            self.assertEqual(load_preferences(path), preferences)
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {
                    "theme": "dark",
                    "font_size": 14,
                    "youtube_language": "fr",
                    "export_directory": str(Path(directory)),
                },
            )

    def test_invalid_values_fall_back_or_are_clamped(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "theme": "neon",
                        "font_size": 200,
                        "youtube_language": "xx",
                        "export_directory": 42,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                load_preferences(path),
                Preferences(theme="light", font_size=20),
            )

    def test_unknown_theme_cannot_be_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            with self.assertRaises(ValueError):
                save_preferences(path, Preferences(theme="neon"))


if __name__ == "__main__":
    unittest.main()
