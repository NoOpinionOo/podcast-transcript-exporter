"""Formatierung und Dateiexport fuer TXT, Markdown und SRT."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Transcript, TranscriptSegment


SUPPORTED_FORMATS = ("txt", "md", "srt")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}


class ExportError(ValueError):
    """Das gewuenschte Exportformat oder Ziel ist ungueltig."""


def format_clock(milliseconds: int, *, srt: bool = False) -> str:
    total_seconds, millis = divmod(int(milliseconds), 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if srt:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _segment_line(segment: TranscriptSegment, include_timestamps: bool) -> str:
    parts: list[str] = []
    if include_timestamps:
        parts.append(f"[{format_clock(segment.start_ms)}]")
    if segment.speaker:
        parts.append(f"{segment.speaker}:")
    parts.append(" ".join(segment.text.splitlines()))
    return " ".join(parts)


def render_txt(transcript: Transcript, include_timestamps: bool = False) -> str:
    header = [transcript.title]
    if transcript.show:
        header.append(f"Podcast: {transcript.show}")
    header.append(f"Quelle: {transcript.source_url}")
    if transcript.language:
        header.append(f"Sprache: {transcript.language}")
    if transcript.notice:
        header.append(f"Hinweis: {transcript.notice}")
    header.append("")
    body = [_segment_line(segment, include_timestamps) for segment in transcript.segments]
    return "\n".join(header + body).rstrip() + "\n"


def render_markdown(transcript: Transcript, include_timestamps: bool = False) -> str:
    lines = [f"# {transcript.title}", ""]
    if transcript.show:
        lines.append(f"**Podcast:** {transcript.show}")
    lines.append(f"**Quelle:** {transcript.source_url}")
    if transcript.language:
        lines.append(f"**Sprache:** {transcript.language}")
    if transcript.notice:
        lines.extend(["", f"> {transcript.notice}"])
    lines.extend(["", "---", ""])

    for segment in transcript.segments:
        prefix = ""
        if include_timestamps:
            prefix += f"[{format_clock(segment.start_ms)}] "
        if segment.speaker:
            prefix += f"**{segment.speaker}:** "
        text = " ".join(segment.text.splitlines())
        lines.extend([prefix + text, ""])
    return "\n".join(lines).rstrip() + "\n"


def render_srt(transcript: Transcript) -> str:
    """Erzeugt SRT; Zeitcodes sind in diesem Format zwingend."""

    cues: list[str] = []
    for index, segment in enumerate(transcript.segments, start=1):
        speaker = f"{segment.speaker}: " if segment.speaker else ""
        text = " ".join(segment.text.splitlines())
        cues.extend(
            [
                str(index),
                f"{format_clock(segment.start_ms, srt=True)} --> "
                f"{format_clock(segment.end_ms, srt=True)}",
                speaker + text,
                "",
            ]
        )
    return "\n".join(cues)


def render_transcript(
    transcript: Transcript,
    file_format: str,
    include_timestamps: bool = False,
) -> str:
    normalized = file_format.lower().lstrip(".")
    if normalized == "txt":
        return render_txt(transcript, include_timestamps)
    if normalized == "md":
        return render_markdown(transcript, include_timestamps)
    if normalized == "srt":
        return render_srt(transcript)
    raise ExportError(f"Nicht unterstuetztes Exportformat: {file_format}")


def safe_filename(title: str, extension: str) -> str:
    extension = extension.lower().lstrip(".")
    if extension not in SUPPORTED_FORMATS:
        raise ExportError(f"Nicht unterstuetztes Exportformat: {extension}")
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")[:120]
    if not cleaned:
        cleaned = "transkript"
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = "_" + cleaned
    return f"{cleaned}.{extension}"


def export_transcript(
    transcript: Transcript,
    destination: Path,
    file_format: str,
    include_timestamps: bool = False,
) -> Path:
    destination = Path(destination)
    if destination.exists() and destination.is_dir():
        raise ExportError("Als Ziel muss eine Datei ausgewaehlt werden.")
    content = render_transcript(transcript, file_format, include_timestamps)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")
    return destination
