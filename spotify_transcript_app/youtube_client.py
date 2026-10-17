"""YouTube-Linkpruefung und gekapselter Transkriptabruf."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from .models import Transcript, TranscriptSegment


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
}
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")
LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")


class YouTubeTranscriptError(ValueError):
    """Verstaendlicher Fehler beim Pruefen oder Abrufen eines YouTube-Links."""


@dataclass(frozen=True)
class YouTubeVideoReference:
    original_url: str
    video_id: str
    canonical_url: str


def parse_youtube_url(value: str) -> YouTubeVideoReference:
    """Akzeptiert normale YouTube-Links, Kurzlinks, Shorts und Live-Links."""

    raw = value.strip()
    if not raw:
        raise YouTubeTranscriptError("Bitte einen YouTube-Link eingeben.")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise YouTubeTranscriptError("Der YouTube-Link ist nicht gueltig.") from exc
    if parsed.scheme.lower() != "https":
        raise YouTubeTranscriptError("YouTube-Links muessen mit https:// beginnen.")
    if parsed.username or parsed.password or port is not None:
        raise YouTubeTranscriptError("Der YouTube-Link enthaelt unzulaessige Zugangsdaten oder Ports.")

    host = (parsed.hostname or "").lower().rstrip(".")
    path_parts = [part for part in parsed.path.split("/") if part]
    video_id = ""
    if host == "youtu.be":
        if path_parts:
            video_id = path_parts[0]
    elif host in YOUTUBE_HOSTS:
        if parsed.path.rstrip("/") == "/watch":
            video_id = parse_qs(parsed.query).get("v", [""])[0]
        elif len(path_parts) >= 2 and path_parts[0] in {"shorts", "live", "embed"}:
            video_id = path_parts[1]
    else:
        raise YouTubeTranscriptError(
            "Unterstuetzt werden Links von youtube.com und youtu.be."
        )

    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise YouTubeTranscriptError(
            "Der Link enthaelt keine gueltige YouTube-Video-ID."
        )
    return YouTubeVideoReference(
        original_url=raw,
        video_id=video_id,
        canonical_url=f"https://www.youtube.com/watch?v={video_id}",
    )


def is_youtube_host(value: str) -> bool:
    """Erkennt nur den Host, damit die GUI den passenden Client waehlen kann."""

    try:
        host = (urlsplit(value.strip()).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == "youtu.be" or host in YOUTUBE_HOSTS


def _new_api() -> Any:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:  # pragma: no cover - nur bei unvollstaendiger Installation
        raise YouTubeTranscriptError(
            "Die YouTube-Komponente fehlt. Bitte die vollstaendige App erneut installieren."
        ) from exc
    return YouTubeTranscriptApi()


def _friendly_error(exc: Exception) -> str:
    messages = {
        "TranscriptsDisabled": "Fuer dieses YouTube-Video sind keine Untertitel aktiviert.",
        "NoTranscriptFound": "Fuer dieses YouTube-Video wurde kein Transkript gefunden.",
        "VideoUnavailable": "Das YouTube-Video ist nicht verfuegbar oder nicht oeffentlich.",
        "VideoUnplayable": "Das YouTube-Video kann derzeit nicht abgespielt werden.",
        "AgeRestricted": (
            "Das Video ist altersbeschraenkt. Die verwendete YouTube-Bibliothek "
            "unterstuetzt dafuer derzeit keine Anmeldung."
        ),
        "RequestBlocked": (
            "YouTube hat den automatischen Abruf von dieser Internetverbindung blockiert. "
            "Bitte spaeter erneut versuchen."
        ),
        "IpBlocked": (
            "YouTube hat den automatischen Abruf von dieser IP-Adresse blockiert. "
            "Bitte spaeter erneut versuchen."
        ),
        "PoTokenRequired": (
            "YouTube verlangt fuer dieses Video einen zusaetzlichen Zugriffsnachweis, "
            "den diese App nicht umgeht."
        ),
        "YouTubeDataUnparsable": (
            "YouTube hat sein internes Datenformat geaendert. "
            "Die YouTube-Komponente muss voraussichtlich aktualisiert werden."
        ),
        "YouTubeRequestFailed": "Die Anfrage an YouTube ist fehlgeschlagen.",
    }
    return messages.get(
        type(exc).__name__,
        "Das YouTube-Transkript konnte nicht abgerufen werden.",
    )


class YouTubeTranscriptClient:
    """Waehlt bevorzugt ein deutsches Transkript und normalisiert dessen Zeitcodes."""

    def __init__(self, api_factory: Callable[[], Any] | None = None) -> None:
        self._api_factory = api_factory or _new_api

    def fetch(
        self,
        youtube_url: str,
        preferred_language: str | None = None,
    ) -> Transcript:
        reference = parse_youtube_url(youtube_url)
        language_choice = (preferred_language or "").strip().lower()
        if language_choice and not LANGUAGE_CODE_PATTERN.fullmatch(language_choice):
            raise YouTubeTranscriptError("Die gewählte YouTube-Sprache ist nicht gültig.")
        try:
            available = list(self._api_factory().list(reference.video_id))
        except YouTubeTranscriptError:
            raise
        except Exception as exc:
            if type(exc).__module__.startswith(
                ("youtube_transcript_api", "requests", "urllib3")
            ):
                raise YouTubeTranscriptError(_friendly_error(exc)) from exc
            raise

        if not available:
            raise YouTubeTranscriptError(
                "Fuer dieses YouTube-Video wurde kein Transkript gefunden."
            )

        # Die Bibliothek liefert manuelle Spuren vor automatisch erzeugten. Unsere
        # Sortierung setzt die Nutzerwahl beziehungsweise deutsche Varianten davor.
        indexed = list(enumerate(available))

        def language_priority(track: Any) -> int:
            code = str(getattr(track, "language_code", "")).lower()
            if code == "de" or code.startswith("de-"):
                return 0
            if code == "en" or code.startswith("en-"):
                return 1
            return 2

        if language_choice:
            matching = [
                item
                for item in indexed
                if (
                    str(getattr(item[1], "language_code", "")).lower()
                    == language_choice
                    or str(getattr(item[1], "language_code", "")).lower().startswith(
                        language_choice + "-"
                    )
                )
            ]
            if not matching:
                available_labels: list[str] = []
                for track in available:
                    code = str(getattr(track, "language_code", "")).strip()
                    name = str(getattr(track, "language", "")).strip()
                    label = f"{name} ({code})" if name and code else name or code
                    if label and label not in available_labels:
                        available_labels.append(label)
                summary = ", ".join(available_labels[:12]) or "unbekannt"
                raise YouTubeTranscriptError(
                    f"Die gewählte Sprache „{language_choice}“ ist für dieses Video "
                    f"nicht verfügbar. Verfügbar: {summary}."
                )
            matching.sort(
                key=lambda item: (
                    1 if bool(getattr(item[1], "is_generated", False)) else 0,
                    item[0],
                )
            )
            selected = matching[0][1]
        else:
            indexed.sort(
                key=lambda item: (
                    language_priority(item[1]),
                    1 if bool(getattr(item[1], "is_generated", False)) else 0,
                    item[0],
                )
            )
            selected = indexed[0][1]
        try:
            fetched = selected.fetch(preserve_formatting=False)
        except Exception as exc:
            if type(exc).__module__.startswith(
                ("youtube_transcript_api", "requests", "urllib3")
            ):
                raise YouTubeTranscriptError(_friendly_error(exc)) from exc
            raise

        segments: list[TranscriptSegment] = []
        for snippet in fetched:
            text = " ".join(str(getattr(snippet, "text", "")).split())
            if not text:
                continue
            try:
                start_seconds = max(0.0, float(getattr(snippet, "start")))
                duration_seconds = max(0.0, float(getattr(snippet, "duration")))
            except (TypeError, ValueError) as exc:
                raise YouTubeTranscriptError(
                    "YouTube lieferte einen ungueltigen Zeitcode."
                ) from exc
            start_ms = round(start_seconds * 1000)
            end_ms = max(start_ms + 500, round((start_seconds + duration_seconds) * 1000))
            segments.append(TranscriptSegment(start_ms, end_ms, text))

        if not segments:
            raise YouTubeTranscriptError(
                "YouTube lieferte ein Transkript, aber keine lesbaren Textabschnitte."
            )

        language_code = str(
            getattr(fetched, "language_code", None)
            or getattr(selected, "language_code", "")
        ).strip()
        language_name = str(
            getattr(fetched, "language", None) or getattr(selected, "language", "")
        ).strip()
        generated = bool(
            getattr(fetched, "is_generated", getattr(selected, "is_generated", False))
        )
        kind = "automatisch erzeugt" if generated else "vom Herausgeber bereitgestellt"
        language_notice = language_name or language_code or "unbekannte Sprache"
        return Transcript(
            title=f"YouTube-Video {reference.video_id}",
            show="YouTube",
            source_url=reference.canonical_url,
            language=language_code or language_name,
            segments=tuple(segments),
            notice=(
                f"Vorhandenes YouTube-Transkript ({language_notice}, {kind}) ueber die "
                "inoffizielle Web-Schnittstelle abgerufen; der Text kann Fehler enthalten."
            ),
            timing_origin="provided",
        )
