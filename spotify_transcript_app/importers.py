"""Sicherer lokaler Import von VTT-, SRT- und TXT-Dateien."""

from __future__ import annotations

import html
import re
from dataclasses import replace
from pathlib import Path

from .models import Transcript, TranscriptSegment


SUPPORTED_IMPORT_FORMATS = (".vtt", ".srt", ".txt")
MAX_IMPORT_BYTES = 10 * 1024 * 1024
TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d{1,3}):)?(?P<minutes>\d{2}):(?P<seconds>\d{2})"
    r"[.,](?P<millis>\d{3})$"
)
VOICE_TAG_RE = re.compile(r"<v(?:\.[^ >]+)*(?:\s+([^>]+))?>", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")
SPEAKER_RE = re.compile(r"^([^:\n]{1,40}):\s+(.+)$", re.DOTALL)


class TranscriptImportError(ValueError):
    """Eine lokale Datei ist nicht lesbar oder hat kein passendes Format."""


def import_transcript_file(path: Path) -> Transcript:
    """Liest eine lokale Transkriptdatei ohne Netzwerkzugriff."""

    source = Path(path)
    if not source.exists():
        raise TranscriptImportError("Die ausgewaehlte Datei wurde nicht gefunden.")
    if not source.is_file():
        raise TranscriptImportError("Bitte eine Datei und keinen Ordner auswaehlen.")

    extension = source.suffix.lower()
    if extension not in SUPPORTED_IMPORT_FORMATS:
        raise TranscriptImportError("Unterstuetzt werden nur VTT-, SRT- und TXT-Dateien.")

    try:
        size = source.stat().st_size
    except OSError as exc:
        raise TranscriptImportError(f"Die Datei konnte nicht geprueft werden: {exc}") from exc
    if size > MAX_IMPORT_BYTES:
        raise TranscriptImportError("Die Datei ist groesser als 10 MB und wird nicht importiert.")

    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise TranscriptImportError(f"Die Datei konnte nicht gelesen werden: {exc}") from exc
    return import_transcript_bytes(
        raw,
        extension,
        filename=source.name,
        source_url=f"Lokale Datei: {source.name}",
        notice_prefix="",
    )


def import_transcript_bytes(
    raw: bytes,
    format_hint: str,
    *,
    filename: str = "transkript.txt",
    source_url: str = "",
    title: str = "",
    show: str = "",
    language: str = "",
    notice_prefix: str = "Über einen ausdrücklich bestätigten öffentlichen Link importiert.",
) -> Transcript:
    """Verarbeitet bereits geladene Transkriptdaten ohne weitere Zugriffe."""

    if len(raw) > MAX_IMPORT_BYTES:
        raise TranscriptImportError("Die Datei ist groesser als 10 MB und wird nicht importiert.")

    normalized_hint = format_hint.strip().lower().split(";", 1)[0]
    hint_map = {
        ".vtt": ".vtt",
        "vtt": ".vtt",
        "text/vtt": ".vtt",
        ".srt": ".srt",
        "srt": ".srt",
        "application/srt": ".srt",
        "application/x-subrip": ".srt",
        "text/srt": ".srt",
        ".txt": ".txt",
        "txt": ".txt",
        "text/plain": ".txt",
    }
    extension = hint_map.get(normalized_hint)
    if extension is None:
        raise TranscriptImportError("Unterstuetzt werden online nur VTT, SRT und Klartext.")

    text = _decode_text(raw)
    if not text.strip():
        raise TranscriptImportError("Die Transkriptdatei ist leer.")
    if "\x00" in text:
        raise TranscriptImportError("Die Datei scheint keine Textdatei zu sein.")

    if extension == ".vtt":
        transcript = parse_vtt(text, filename)
    elif extension == ".srt":
        transcript = parse_srt(text, filename)
    else:
        transcript = parse_txt(text, filename)

    if not source_url:
        source_url = transcript.source_url
    detail_notice = transcript.notice
    if notice_prefix.strip() and extension in {".vtt", ".srt"}:
        detail_notice = "Zeitcodes wurden aus der veröffentlichten Datei übernommen."
    return replace(
        transcript,
        title=title.strip() or transcript.title,
        show=show.strip(),
        language=language.strip(),
        source_url=source_url,
        notice=f"{notice_prefix.strip()} {detail_notice}".strip(),
    )


def _decode_text(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise TranscriptImportError("Die UTF-16-Datei ist beschaedigt.") from exc
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise TranscriptImportError("Die Zeichenkodierung der Datei wird nicht erkannt.") from exc


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _parse_timestamp(value: str) -> int:
    match = TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise TranscriptImportError(f"Ungueltiger Zeitstempel: {value}")
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    millis = int(match.group("millis"))
    if minutes > 59 or seconds > 59:
        raise TranscriptImportError(f"Ungueltiger Zeitstempel: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def _parse_timing_line(line: str) -> tuple[int, int]:
    if "-->" not in line:
        raise TranscriptImportError("In einem Untertitelblock fehlt der Zeitbereich.")
    left, right = line.split("-->", 1)
    end_token = right.strip().split(maxsplit=1)[0] if right.strip() else ""
    start_ms = _parse_timestamp(left.strip())
    end_ms = _parse_timestamp(end_token)
    if end_ms <= start_ms:
        raise TranscriptImportError("Ein Endzeitpunkt liegt nicht nach dem Startzeitpunkt.")
    return start_ms, end_ms


def _clean_cue_text(lines: list[str]) -> tuple[str | None, str]:
    raw_text = " ".join(line.strip() for line in lines if line.strip())
    voice_match = VOICE_TAG_RE.search(raw_text)
    speaker = html.unescape(voice_match.group(1)).strip() if voice_match and voice_match.group(1) else None
    cleaned = html.unescape(TAG_RE.sub("", raw_text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not speaker:
        speaker_match = SPEAKER_RE.fullmatch(cleaned)
        if speaker_match:
            speaker = speaker_match.group(1).strip()
            cleaned = speaker_match.group(2).strip()
    if not cleaned:
        raise TranscriptImportError("Ein Untertitelblock enthaelt keinen lesbaren Text.")
    return speaker, cleaned


def _parse_cue_blocks(text: str, *, is_vtt: bool) -> tuple[TranscriptSegment, ...]:
    normalized = _normalize_newlines(text).strip()
    blocks = re.split(r"\n\s*\n", normalized)
    segments: list[TranscriptSegment] = []

    for block in blocks:
        lines = [line.strip("\ufeff") for line in block.split("\n")]
        if not lines:
            continue
        first = lines[0].strip()
        if is_vtt and first.upper().startswith("WEBVTT"):
            continue
        if is_vtt and first.upper().startswith(("NOTE", "STYLE", "REGION")):
            continue

        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            if all(not line.strip() for line in lines):
                continue
            raise TranscriptImportError("Ein Untertitelblock enthaelt keine Zeitangabe.")

        start_ms, end_ms = _parse_timing_line(lines[timing_index])
        speaker, cue_text = _clean_cue_text(lines[timing_index + 1 :])
        segments.append(TranscriptSegment(start_ms, end_ms, cue_text, speaker))

    if not segments:
        raise TranscriptImportError("In der Datei wurden keine Untertitel gefunden.")
    return tuple(segments)


def parse_vtt(text: str, filename: str = "transkript.vtt") -> Transcript:
    normalized = _normalize_newlines(text).lstrip("\ufeff")
    if not normalized.lstrip().upper().startswith("WEBVTT"):
        raise TranscriptImportError("Eine VTT-Datei muss mit WEBVTT beginnen.")
    return Transcript(
        title=Path(filename).stem,
        show="",
        source_url=f"Lokale Datei: {Path(filename).name}",
        language="",
        segments=_parse_cue_blocks(normalized, is_vtt=True),
        notice="Aus einer lokalen VTT-Datei importiert; Zeitcodes wurden uebernommen.",
        timing_origin="provided",
    )


def parse_srt(text: str, filename: str = "transkript.srt") -> Transcript:
    return Transcript(
        title=Path(filename).stem,
        show="",
        source_url=f"Lokale Datei: {Path(filename).name}",
        language="",
        segments=_parse_cue_blocks(text, is_vtt=False),
        notice="Aus einer lokalen SRT-Datei importiert; Zeitcodes wurden uebernommen.",
        timing_origin="provided",
    )


def _split_text_blocks(text: str, *, structured: bool) -> list[str]:
    normalized = _normalize_newlines(text).strip()
    if structured:
        return [line.strip() for line in normalized.split("\n") if line.strip()]
    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    if len(blocks) == 1 and "\n" in blocks[0]:
        return [line.strip() for line in blocks[0].split("\n") if line.strip()]
    return [re.sub(r"\s+", " ", block) for block in blocks]


def parse_txt(text: str, filename: str = "transkript.txt") -> Transcript:
    normalized = _normalize_newlines(text).lstrip("\ufeff")
    lines = normalized.split("\n")
    title = Path(filename).stem
    show = ""
    language = ""
    original_source = f"Lokale Datei: {Path(filename).name}"
    body = normalized

    header_limit = min(len(lines), 8)
    structured = bool(lines and any(line.startswith("Quelle: ") for line in lines[1:header_limit]))
    if structured:
        title = lines[0].strip() or title
        body_start = header_limit
        for index, line in enumerate(lines[1:header_limit], start=1):
            stripped = line.strip()
            if stripped.startswith("Podcast: "):
                show = stripped.removeprefix("Podcast: ").strip()
            elif stripped.startswith("Quelle: "):
                original_source = stripped.removeprefix("Quelle: ").strip() or original_source
            elif stripped.startswith("Sprache: "):
                language = stripped.removeprefix("Sprache: ").strip()
            elif stripped.startswith("Hinweis: "):
                pass
            elif not stripped:
                body_start = index + 1
                break
        body = "\n".join(lines[body_start:])

    blocks = _split_text_blocks(body, structured=structured)
    if not blocks:
        raise TranscriptImportError("Die TXT-Datei enthaelt keinen Transkripttext.")

    cursor = 0
    segments: list[TranscriptSegment] = []
    for block in blocks:
        speaker = None
        content = block
        match = SPEAKER_RE.fullmatch(block)
        if match:
            speaker = match.group(1).strip()
            content = match.group(2).strip()
        word_count = max(1, len(content.split()))
        duration = max(2_000, min(30_000, word_count * 450))
        segments.append(TranscriptSegment(cursor, cursor + duration, content, speaker))
        cursor += duration

    return Transcript(
        title=title,
        show=show,
        source_url=original_source,
        language=language,
        segments=tuple(segments),
        notice=(
            "TXT enthaelt keine verlaesslichen Zeitcodes. Fuer Vorschau und SRT-Export "
            "werden gut sichtbare Schaetzzeiten erzeugt."
        ),
        timing_origin="estimated",
    )
