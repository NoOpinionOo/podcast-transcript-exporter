import unittest

from spotify_transcript_app.importers import import_transcript_bytes
from spotify_transcript_app.online import DownloadedResource
from spotify_transcript_app.online_service import OnlineImportService
from spotify_transcript_app.rss_transcripts import FeedParseError, parse_podcast_feed


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>Beispielpodcast</title>
    <language>de</language>
    <item>
      <title>Folge Eins</title>
      <pubDate>Fri, 16 Oct 2026 12:00:00 GMT</pubDate>
      <podcast:transcript url="https://media.example.com/folge-1.vtt"
                          type="text/vtt" language="de" rel="captions" />
      <podcast:transcript url="https://media.example.com/folge-1.json"
                          type="application/json" />
    </item>
    <item>
      <title>Folge Zwei</title>
      <podcast:transcript url="/transkripte/folge-2.srt" type="application/srt" />
      <podcast:transcript url="http://unsafe.example.com/folge-2.txt" type="text/plain" />
    </item>
  </channel>
</rss>
"""


class RssTranscriptTests(unittest.TestCase):
    def test_discovers_supported_publisher_links(self):
        result = parse_podcast_feed(FEED, "https://feeds.example.org/show/feed.xml")
        self.assertEqual(result.podcast_title, "Beispielpodcast")
        self.assertEqual(len(result.transcripts), 2)
        self.assertEqual(result.skipped_count, 2)

        first = result.transcripts[0]
        self.assertEqual(first.episode_title, "Folge Eins")
        self.assertEqual(first.language, "de")
        self.assertEqual(first.relation, "captions")

        second = result.transcripts[1]
        self.assertEqual(second.url, "https://feeds.example.org/transkripte/folge-2.srt")
        self.assertEqual(second.language, "de")

    def test_rejects_dtd_entities_and_invalid_xml(self):
        dangerous = b'<!DOCTYPE rss [<!ENTITY x "Text">]><rss><channel/></rss>'
        with self.assertRaises(FeedParseError):
            parse_podcast_feed(dangerous, "https://example.com/feed.xml")
        with self.assertRaises(FeedParseError):
            parse_podcast_feed(b"<rss>", "https://example.com/feed.xml")

    def test_imports_downloaded_bytes_without_temporary_file(self):
        transcript = import_transcript_bytes(
            b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nSprecher: Hallo online.\n",
            "text/vtt",
            filename="folge.vtt",
            source_url="https://media.example.com/folge.vtt",
            title="Veroeffentlichte Folge",
            show="Mein Podcast",
            language="de",
        )
        self.assertEqual(transcript.title, "Veroeffentlichte Folge")
        self.assertEqual(transcript.show, "Mein Podcast")
        self.assertEqual(transcript.segments[0].speaker, "Sprecher")
        self.assertIn("ausdrücklich bestätigten", transcript.notice)

    def test_online_service_keeps_discovery_and_download_separate(self):
        class FakeClient:
            def __init__(self):
                self.urls = []

            def fetch(self, url, *, max_bytes, accept):
                self.urls.append(url)
                if url.endswith("feed.xml"):
                    return DownloadedResource(FEED, url, "application/rss+xml")
                return DownloadedResource(
                    b"WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHallo.\n",
                    url,
                    "text/vtt",
                )

        client = FakeClient()
        service = OnlineImportService(client)
        discovery = service.discover_feed("https://feeds.example.org/feed.xml")
        self.assertEqual(client.urls, ["https://feeds.example.org/feed.xml"])

        transcript = service.download_published(discovery.transcripts[0])
        self.assertEqual(len(client.urls), 2)
        self.assertEqual(transcript.title, "Folge Eins")
        self.assertEqual(transcript.source_url, "https://media.example.com/folge-1.vtt")


if __name__ == "__main__":
    unittest.main()
