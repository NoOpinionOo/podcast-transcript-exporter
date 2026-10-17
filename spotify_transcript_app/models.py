"""Datenmodelle fuer Episoden-Referenzen und Transkripte."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class EpisodeReference:
    """Eine lokal validierte Spotify-Episoden-URL."""

    original_url: str
    episode_id: str
    canonical_url: str


@dataclass(frozen=True)
class TranscriptSegment:
    """Ein zeitlich begrenzter Textabschnitt."""

    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms darf nicht negativ sein")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms muss groesser als start_ms sein")
        if not self.text.strip():
            raise ValueError("Ein Segment braucht Text")


@dataclass(frozen=True)
class Transcript:
    """Normalisierte, von der Datenquelle unabhaengige Transkriptdaten."""

    title: str
    show: str
    source_url: str
    language: str
    segments: tuple[TranscriptSegment, ...]
    notice: str = ""
    timing_origin: str = "provided"

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("Ein Transkript braucht einen Titel")
        if not self.segments:
            raise ValueError("Ein Transkript braucht mindestens ein Segment")
        if self.timing_origin not in {"provided", "estimated"}:
            raise ValueError("timing_origin muss 'provided' oder 'estimated' sein")

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        source_url: str,
    ) -> "Transcript":
        raw_segments: Sequence[Mapping[str, Any]] = data.get("segments", ())
        segments = tuple(
            TranscriptSegment(
                start_ms=int(item["start_ms"]),
                end_ms=int(item["end_ms"]),
                text=str(item["text"]).strip(),
                speaker=(str(item["speaker"]).strip() if item.get("speaker") else None),
            )
            for item in raw_segments
        )
        return cls(
            title=str(data.get("title", "")).strip(),
            show=str(data.get("show", "")).strip(),
            source_url=source_url,
            language=str(data.get("language", "")).strip(),
            segments=segments,
            notice=str(data.get("notice", "")).strip(),
            timing_origin=str(data.get("timing_origin", "provided")).strip(),
        )

