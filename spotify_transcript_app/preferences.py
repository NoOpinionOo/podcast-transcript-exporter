"""Kleine, lokale und bewusst nicht sensible App-Einstellungen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


VALID_THEMES = frozenset({"light", "dark"})
VALID_YOUTUBE_LANGUAGES = frozenset(
    {"auto", "de", "en", "fr", "es", "it", "nl", "pl", "pt", "tr"}
)
MIN_FONT_SIZE = 8
MAX_FONT_SIZE = 20


@dataclass(frozen=True)
class Preferences:
    """Einstellungen, die gefahrlos zwischen App-Starts gespeichert werden."""

    theme: str = "light"
    font_size: int = 10
    youtube_language: str = "auto"
    export_directory: str = ""


def load_preferences(path: Path) -> Preferences:
    """Liest Einstellungen fehlertolerant; beschädigte Dateien werden ignoriert."""

    try:
        if path.stat().st_size > 16_384:
            return Preferences()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return Preferences()

    if not isinstance(value, dict):
        return Preferences()

    theme = value.get("theme", "light")
    if not isinstance(theme, str) or theme not in VALID_THEMES:
        theme = "light"
    font_size = value.get("font_size", 10)
    if isinstance(font_size, bool) or not isinstance(font_size, int):
        font_size = 10
    font_size = min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, font_size))
    youtube_language = value.get("youtube_language", "auto")
    if (
        not isinstance(youtube_language, str)
        or youtube_language not in VALID_YOUTUBE_LANGUAGES
    ):
        youtube_language = "auto"
    export_directory = value.get("export_directory", "")
    if not isinstance(export_directory, str) or len(export_directory) > 4096:
        export_directory = ""
    return Preferences(
        theme=theme,
        font_size=font_size,
        youtube_language=youtube_language,
        export_directory=export_directory,
    )


def save_preferences(path: Path, preferences: Preferences) -> None:
    """Speichert ausschließlich die Theme-Auswahl atomar im App-Ordner."""

    if not isinstance(preferences.theme, str) or preferences.theme not in VALID_THEMES:
        raise ValueError("Unbekanntes Farbschema.")
    if not MIN_FONT_SIZE <= preferences.font_size <= MAX_FONT_SIZE:
        raise ValueError("Unzulässige Schriftgröße.")
    if (
        not isinstance(preferences.youtube_language, str)
        or preferences.youtube_language not in VALID_YOUTUBE_LANGUAGES
    ):
        raise ValueError("Unbekannte YouTube-Sprache.")
    if len(preferences.export_directory) > 4096:
        raise ValueError("Der Exportordner ist zu lang.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            {
                "theme": preferences.theme,
                "font_size": preferences.font_size,
                "youtube_language": preferences.youtube_language,
                "export_directory": preferences.export_directory,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
