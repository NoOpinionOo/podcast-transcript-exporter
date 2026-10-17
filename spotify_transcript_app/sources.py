"""Austauschbare Quellen fuer Transkriptdaten.

Version 0.1 enthaelt absichtlich nur eine lokale Beispieldatenquelle. Es gibt
hier keinen Netzwerkcode und keine Verarbeitung von Zugangsdaten oder Cookies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import EpisodeReference, Transcript


class TranscriptSourceError(RuntimeError):
    """Eine Transkriptquelle konnte keine Daten liefern."""


class TranscriptSource(Protocol):
    """Schnittstelle fuer spaetere, separat pruefbare Datenquellen."""

    display_name: str
    network_access: bool

    def fetch(self, episode: EpisodeReference) -> Transcript:
        """Liefert ein normalisiertes Transkript."""


class ExampleTranscriptSource:
    """Laedt ein frei erfundenes Beispiel aus dem Installationsordner."""

    display_name = "Lokale Beispieldaten"
    network_access = False

    def __init__(self, sample_path: Path | None = None) -> None:
        self._sample_path = sample_path or (
            Path(__file__).resolve().parent / "samples" / "example_transcript.json"
        )

    def fetch(self, episode: EpisodeReference) -> Transcript:
        try:
            with self._sample_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError) as exc:
            raise TranscriptSourceError(
                f"Die lokalen Beispieldaten konnten nicht gelesen werden: {exc}"
            ) from exc

        try:
            return Transcript.from_mapping(data, source_url=episode.canonical_url)
        except (KeyError, TypeError, ValueError) as exc:
            raise TranscriptSourceError(
                f"Die lokalen Beispieldaten sind ungueltig: {exc}"
            ) from exc

