"""Anwendungslogik zwischen GUI, URL-Pruefung und Datenquelle."""

from __future__ import annotations

from pathlib import Path

from .importers import import_transcript_file
from .models import Transcript
from .sources import TranscriptSource
from .url_validation import parse_episode_url


class TranscriptService:
    def __init__(self, source: TranscriptSource) -> None:
        self.source = source

    def fetch_from_url(self, url: str) -> Transcript:
        episode = parse_episode_url(url)
        return self.source.fetch(episode)

    def import_file(self, path: Path) -> Transcript:
        return import_transcript_file(path)
