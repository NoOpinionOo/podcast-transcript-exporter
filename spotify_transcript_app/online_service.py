"""Ablaufsteuerung fuer bewusst gestartete Online-Importe."""

from __future__ import annotations

from pathlib import Path

from .importers import MAX_IMPORT_BYTES, import_transcript_bytes
from .models import Transcript
from .online import (
    RemoteUrl,
    SafeHttpClient,
    filename_from_url,
    infer_transcript_format,
    validate_public_https_url,
)
from .rss_transcripts import (
    MAX_FEED_BYTES,
    FeedDiscovery,
    PublishedTranscript,
    parse_podcast_feed,
)


class OnlineImportService:
    def __init__(self, client: SafeHttpClient | None = None) -> None:
        self.client = client or SafeHttpClient()

    def prepare_url(self, value: str) -> RemoteUrl:
        return validate_public_https_url(value)

    def discover_feed(self, feed_url: str) -> FeedDiscovery:
        resource = self.client.fetch(
            feed_url,
            max_bytes=MAX_FEED_BYTES,
            accept="application/rss+xml, application/xml, text/xml;q=0.9",
        )
        return parse_podcast_feed(resource.body, resource.final_url)

    def download_published(self, option: PublishedTranscript) -> Transcript:
        resource = self.client.fetch(
            option.url,
            max_bytes=MAX_IMPORT_BYTES,
            accept=f"{option.media_type}, text/vtt;q=0.9, text/plain;q=0.8",
        )
        format_hint = infer_transcript_format(
            resource.final_url,
            resource.content_type,
            option.media_type,
        )
        filename = filename_from_url(resource.final_url, f"transkript{format_hint}")
        return import_transcript_bytes(
            resource.body,
            format_hint,
            filename=filename,
            source_url=resource.final_url,
            title=option.episode_title,
            show=option.podcast_title,
            language=option.language,
        )

    def download_direct(self, transcript_url: str) -> Transcript:
        resource = self.client.fetch(
            transcript_url,
            max_bytes=MAX_IMPORT_BYTES,
            accept="text/vtt, application/srt, application/x-subrip, text/srt, text/plain;q=0.9",
        )
        format_hint = infer_transcript_format(resource.final_url, resource.content_type)
        filename = filename_from_url(resource.final_url, f"transkript{format_hint}")
        return import_transcript_bytes(
            resource.body,
            format_hint,
            filename=filename,
            source_url=resource.final_url,
            title=Path(filename).stem,
        )
