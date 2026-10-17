"""Auswertung veroeffentlichter podcast:transcript-Verweise aus RSS."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urljoin

from .online import RemoteUrlError, validate_public_https_url


PODCAST_NAMESPACE = "https://podcastindex.org/namespace/1.0"
MAX_FEED_BYTES = 2 * 1024 * 1024
MAX_TRANSCRIPT_OPTIONS = 500
SUPPORTED_MEDIA_TYPES = {
    "text/vtt",
    "application/srt",
    "application/x-subrip",
    "text/srt",
    "text/plain",
}


class FeedParseError(ValueError):
    """Der geladene Feed ist nicht sicher oder nicht auswertbar."""


@dataclass(frozen=True)
class PublishedTranscript:
    episode_title: str
    podcast_title: str
    url: str
    media_type: str
    language: str = ""
    relation: str = ""
    published: str = ""


@dataclass(frozen=True)
class FeedDiscovery:
    podcast_title: str
    transcripts: tuple[PublishedTranscript, ...]
    skipped_count: int = 0


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") and "}" in tag else ""


def _child_text(parent: ET.Element, local_name: str) -> str:
    for child in parent:
        if _local_name(child.tag) == local_name:
            return " ".join("".join(child.itertext()).split())
    return ""


def parse_podcast_feed(data: bytes, source_url: str) -> FeedDiscovery:
    if not data.strip():
        raise FeedParseError("Der RSS-Feed ist leer.")
    if len(data) > MAX_FEED_BYTES:
        raise FeedParseError("Der RSS-Feed ist groesser als 2 MB.")
    upper = data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise FeedParseError("RSS-Feeds mit DTD- oder Entity-Deklarationen werden nicht verarbeitet.")

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise FeedParseError(f"Der RSS-Feed enthaelt ungueltiges XML: {exc}") from exc

    channel = next((node for node in root.iter() if _local_name(node.tag) == "channel"), None)
    if channel is None:
        raise FeedParseError("Das Dokument enthaelt keinen RSS-Kanal.")

    podcast_title = _child_text(channel, "title") or "Unbenannter Podcast"
    feed_language = _child_text(channel, "language")
    options: list[PublishedTranscript] = []
    skipped = 0
    seen: set[tuple[str, str, str]] = set()

    for item in (child for child in channel if _local_name(child.tag) == "item"):
        episode_title = _child_text(item, "title") or "Unbenannte Episode"
        published = _child_text(item, "pubDate")
        for child in item:
            if _local_name(child.tag) != "transcript" or _namespace(child.tag) != PODCAST_NAMESPACE:
                continue
            raw_url = (child.attrib.get("url") or "").strip()
            media_type = (child.attrib.get("type") or "").split(";", 1)[0].strip().lower()
            if not raw_url or media_type not in SUPPORTED_MEDIA_TYPES:
                skipped += 1
                continue
            try:
                remote = validate_public_https_url(urljoin(source_url, raw_url))
            except RemoteUrlError:
                skipped += 1
                continue

            language = (child.attrib.get("language") or feed_language).strip()
            relation = (child.attrib.get("rel") or "").strip().lower()
            identity = (episode_title, remote.url, media_type)
            if identity in seen:
                continue
            seen.add(identity)
            options.append(
                PublishedTranscript(
                    episode_title=episode_title,
                    podcast_title=podcast_title,
                    url=remote.url,
                    media_type=media_type,
                    language=language,
                    relation=relation,
                    published=published,
                )
            )
            if len(options) >= MAX_TRANSCRIPT_OPTIONS:
                skipped += 1
                break
        if len(options) >= MAX_TRANSCRIPT_OPTIONS:
            break

    return FeedDiscovery(podcast_title, tuple(options), skipped)
