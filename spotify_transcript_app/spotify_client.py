"""Inoffizieller Spotify-Transkriptabruf.

Der Token- und Transkriptablauf ist aus dem MIT-lizenzierten Projekt
``glebo309/spotify-transcript`` adaptiert. Anders als das Referenzprogramm
liest dieses Modul keine Browserprofile und speichert kein ``sp_dc``-Cookie.

Referenz: https://github.com/glebo309/spotify-transcript
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import struct
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Mapping
from urllib.parse import urlsplit

from .models import Transcript, TranscriptSegment
from .url_validation import parse_episode_url


SECRETS_URL = (
    "https://raw.githubusercontent.com/CycloneAddons/"
    "spotify-token-generator/main/secrets/secretDict.json"
)
SERVER_TIME_URL = "https://open.spotify.com/api/server-time"
TOKEN_URL = "https://open.spotify.com/api/token"
TRANSCRIPT_URL = (
    "https://spclient.wg.spotify.com/"
    "transcript-read-along/v2/episode/{episode_id}?format=json"
)
EMBED_URL = "https://open.spotify.com/embed/episode/{episode_id}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/136.0.0.0 Safari/537.36"
)
MAX_RESPONSE_BYTES = 20 * 1024 * 1024

# Aus der Referenzversion 1.0.0, dort zuletzt am 05.09.2026 verifiziert.
BUNDLED_SECRETS: dict[int, list[int]] = {
    59: [123, 105, 79, 70, 110, 59, 52, 125, 60, 49, 80, 70, 89, 75, 80, 86, 63, 53, 123, 37, 117, 49, 52, 93, 77, 62, 47, 86, 48, 104, 68, 72],
    60: [79, 109, 69, 123, 90, 65, 46, 74, 94, 34, 58, 48, 70, 71, 92, 92, 85, 122, 63, 91, 64, 87, 87],
    61: [44, 55, 47, 42, 70, 40, 34, 114, 76, 74, 50, 111, 120, 97, 75, 76, 94, 102, 43, 69, 49, 120, 118, 80, 64, 78],
}


class SpotifyTranscriptError(RuntimeError):
    """Verstaendlicher Fehler beim Spotify-Abruf."""


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: bytes
    final_url: str


Transport = Callable[[str, Mapping[str, str], int, int], HttpResult]


def validate_sp_dc(value: str) -> str:
    """Validiert einen manuell eingegebenen Cookiewert ohne Netzwerkzugriff."""

    cookie = (value or "").strip()
    if cookie.lower().startswith("sp_dc="):
        cookie = cookie[6:].strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,2048}", cookie):
        raise SpotifyTranscriptError(
            "Der Wert sieht nicht wie ein Spotify-sp_dc-Cookie aus. "
            "Bitte nur den Wert der Cookie-Zeile sp_dc einfuegen."
        )
    return cookie


def generate_totp(timestamp: int, secret: list[int]) -> str:
    """TOTP-Verfahren des Spotify-Webplayers aus dem Referenzprojekt."""

    key = "".join(str(byte ^ ((index % 33) + 9)) for index, byte in enumerate(secret)).encode()
    digest = hmac.new(key, struct.pack(">Q", timestamp // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (
        ((digest[offset] & 0x7F) << 24)
        | (digest[offset + 1] << 16)
        | (digest[offset + 2] << 8)
        | digest[offset + 3]
    )
    return f"{code % 1_000_000:06d}"


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    timeout: int,
    max_bytes: int,
) -> HttpResult:
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/html, */*",
        "Origin": "https://open.spotify.com",
        "Referer": "https://open.spotify.com/",
        **headers,
    }
    request = urllib.request.Request(url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise SpotifyTranscriptError("Die Spotify-Antwort ist unerwartet gross.")
            return HttpResult(response.status, body, response.geturl())
    except urllib.error.HTTPError as exc:
        body = exc.read(max_bytes + 1)
        return HttpResult(exc.code, body[:max_bytes], exc.geturl())
    except urllib.error.URLError as exc:
        raise SpotifyTranscriptError(
            f"Spotify konnte nicht erreicht werden: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise SpotifyTranscriptError("Zeitueberschreitung beim Spotify-Abruf.") from exc


def _decode_json(result: HttpResult, description: str) -> dict:
    try:
        value = json.loads(result.body.decode("utf-8", "replace"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SpotifyTranscriptError(
            f"{description} lieferte keine gueltigen JSON-Daten."
        ) from exc
    if not isinstance(value, dict):
        raise SpotifyTranscriptError(f"{description} lieferte ein unerwartetes Datenformat.")
    return value


def _validated_secrets(value: object) -> dict[int, list[int]]:
    if not isinstance(value, dict) or len(value) > 100:
        return {}
    result: dict[int, list[int]] = {}
    for raw_version, raw_secret in value.items():
        try:
            version = int(raw_version)
        except (TypeError, ValueError):
            continue
        if not 1 <= version <= 10_000 or not isinstance(raw_secret, list):
            continue
        if not 8 <= len(raw_secret) <= 128:
            continue
        if not all(isinstance(item, int) and 0 <= item <= 255 for item in raw_secret):
            continue
        result[version] = list(raw_secret)
    return result


class SpotifyTranscriptClient:
    """Ruft ein vorhandenes Spotify-Transkript mit einem sp_dc-Cookie ab.

    Cookie und Zugriffstoken existieren ausschliesslich im Arbeitsspeicher.
    Das Cookie wird technisch nur an ``open.spotify.com/api/token`` gesendet.
    """

    def __init__(
        self,
        transport: Transport | None = None,
        *,
        refresh_secrets: bool = True,
    ) -> None:
        self._transport = transport or _default_transport
        self._refresh_secrets = refresh_secrets
        self._secrets_loaded = False
        self._secrets = {version: list(secret) for version, secret in BUNDLED_SECRETS.items()}
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._cookie_fingerprint: str | None = None

    def clear_session(self) -> None:
        self._token = None
        self._token_expires_at = 0.0
        self._cookie_fingerprint = None

    def fetch(self, spotify_url: str, sp_dc: str) -> Transcript:
        episode = parse_episode_url(spotify_url)
        cookie = validate_sp_dc(sp_dc)
        token = self._get_token(cookie)
        try:
            transcript_data = self._fetch_transcript(token, episode.episode_id)
        except _ExpiredTokenError:
            token = self._get_token(cookie, force=True)
            try:
                transcript_data = self._fetch_transcript(token, episode.episode_id)
            except _ExpiredTokenError as exc:
                raise SpotifyTranscriptError(
                    "Spotify hat die Anmeldung abgewiesen. Bitte einen frischen sp_dc-Wert eingeben."
                ) from exc
        if transcript_data is None:
            raise SpotifyTranscriptError(
                "Spotify meldet fuer diese Episode kein abrufbares Transkript."
            )
        metadata = self._fetch_metadata(episode.episode_id)
        return self._normalize(transcript_data, metadata, episode.canonical_url, episode.episode_id)

    def _request(
        self,
        url: str,
        headers: Mapping[str, str] | None = None,
        *,
        timeout: int = 30,
        max_bytes: int = MAX_RESPONSE_BYTES,
    ) -> HttpResult:
        sent_headers = dict(headers or {})
        host = (urlsplit(url).hostname or "").lower()
        if "Cookie" in sent_headers and not (
            host == "open.spotify.com" and url.startswith(TOKEN_URL)
        ):
            raise SpotifyTranscriptError("Interne Schutzregel: Cookie-Ziel wurde abgelehnt.")
        if "Authorization" in sent_headers and host != "spclient.wg.spotify.com":
            raise SpotifyTranscriptError("Interne Schutzregel: Token-Ziel wurde abgelehnt.")
        result = self._transport(url, sent_headers, timeout, max_bytes)
        final_host = (urlsplit(result.final_url).hostname or "").lower()
        if final_host != host:
            raise SpotifyTranscriptError("Eine unerwartete Weiterleitung wurde blockiert.")
        return result

    def _load_secrets(self) -> None:
        if self._secrets_loaded:
            return
        self._secrets_loaded = True
        if not self._refresh_secrets:
            return
        try:
            result = self._request(SECRETS_URL, timeout=10, max_bytes=128 * 1024)
            if result.status == 200:
                remote = _validated_secrets(json.loads(result.body.decode("utf-8")))
                self._secrets.update(remote)
        except (SpotifyTranscriptError, UnicodeError, json.JSONDecodeError):
            # Die eingebauten, geprueften Werte bleiben als Rueckfall erhalten.
            return

    def _mint_token(self, cookie: str) -> tuple[str, float]:
        time_result = self._request(SERVER_TIME_URL, max_bytes=64 * 1024)
        if time_result.status != 200:
            raise SpotifyTranscriptError(
                f"Spotifys Zeitschnittstelle antwortete mit HTTP {time_result.status}."
            )
        time_data = _decode_json(time_result, "Spotifys Zeitschnittstelle")
        try:
            timestamp = int(time_data["serverTime"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SpotifyTranscriptError("Spotify lieferte keine gueltige Serverzeit.") from exc

        self._load_secrets()
        last_status = 0
        for version in sorted(self._secrets, reverse=True):
            code = generate_totp(timestamp, self._secrets[version])
            url = (
                f"{TOKEN_URL}?reason=init&productType=web-player"
                f"&totp={code}&totpVer={version}&totpServer={code}"
            )
            result = self._request(url, {"Cookie": f"sp_dc={cookie}"}, max_bytes=512 * 1024)
            last_status = result.status
            if result.status != 200:
                continue
            try:
                data = _decode_json(result, "Spotify-Anmeldung")
            except SpotifyTranscriptError:
                continue
            token = data.get("accessToken")
            if not isinstance(token, str) or not token:
                continue
            if data.get("isAnonymous"):
                raise SpotifyTranscriptError(
                    "Spotify behandelt das Cookie als abgemeldet. Bitte neu bei "
                    "open.spotify.com anmelden und einen frischen sp_dc-Wert verwenden."
                )
            expires_ms = data.get("accessTokenExpirationTimestampMs", 0)
            try:
                expires_at = float(expires_ms) / 1000
            except (TypeError, ValueError):
                expires_at = time.time() + 300
            return token, expires_at
        raise SpotifyTranscriptError(
            "Die Spotify-Anmeldung ist fehlgeschlagen. Das Cookie kann abgelaufen sein "
            f"oder Spotify hat den internen Ablauf geaendert (HTTP {last_status})."
        )

    def _get_token(self, cookie: str, *, force: bool = False) -> str:
        fingerprint = hashlib.sha256(cookie.encode()).hexdigest()[:16]
        if (
            not force
            and self._token
            and self._cookie_fingerprint == fingerprint
            and self._token_expires_at - time.time() > 120
        ):
            return self._token
        token, expires_at = self._mint_token(cookie)
        self._token = token
        self._token_expires_at = expires_at
        self._cookie_fingerprint = fingerprint
        return token

    def _fetch_transcript(self, token: str, episode_id: str) -> dict | None:
        url = TRANSCRIPT_URL.format(episode_id=episode_id)
        headers = {"Authorization": f"Bearer {token}", "App-Platform": "WebPlayer"}
        result = self._request(url, headers)
        if result.status in (401, 403):
            # Der Aufrufer beschafft mit demselben Cookie genau einmal einen neuen Token.
            self._token_expires_at = 0
            raise _ExpiredTokenError
        if result.status == 404:
            return None
        if result.status != 200:
            raise SpotifyTranscriptError(
                f"Spotifys Transkriptschnittstelle antwortete mit HTTP {result.status}."
            )
        return _decode_json(result, "Spotifys Transkriptschnittstelle")

    def _fetch_metadata(self, episode_id: str) -> dict:
        try:
            result = self._request(
                EMBED_URL.format(episode_id=episode_id),
                {"Accept": "text/html"},
                max_bytes=2 * 1024 * 1024,
            )
        except SpotifyTranscriptError:
            return {}
        if result.status != 200:
            return {}
        html = result.body.decode("utf-8", "replace")
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not match:
            return {}
        try:
            entity = json.loads(match.group(1))["props"]["pageProps"]["state"]["data"]["entity"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return {}
        if not isinstance(entity, dict):
            return {}
        return {
            "name": entity.get("name") or entity.get("title"),
            "show": entity.get("subtitle"),
            "duration_ms": entity.get("duration") or 0,
        }

    def _normalize(
        self,
        data: dict,
        metadata: dict,
        source_url: str,
        episode_id: str,
    ) -> Transcript:
        raw_sentences: list[tuple[int, str | None, str]] = []
        speaker: str | None = None
        sections = data.get("section")
        if not isinstance(sections, list):
            sections = []
        for section in sections:
            if not isinstance(section, dict):
                continue
            title_data = section.get("title")
            if isinstance(title_data, dict):
                title = str(title_data.get("title") or "").strip()
                if re.fullmatch(r"Speaker \d+", title):
                    speaker = title
                continue
            text_data = section.get("text")
            if not isinstance(text_data, dict):
                continue
            sentence = text_data.get("sentence")
            if not isinstance(sentence, dict):
                continue
            text = str(sentence.get("text") or "").strip()
            if not text:
                continue
            try:
                start_ms = int(sentence.get("startMs", section.get("startMs", 0)))
            except (TypeError, ValueError):
                start_ms = 0
            raw_sentences.append((max(0, start_ms), speaker, text))

        if not raw_sentences:
            raise SpotifyTranscriptError(
                "Spotify lieferte ein Transkript, aber keine lesbaren Textabschnitte."
            )

        segments: list[TranscriptSegment] = []
        for index, (start_ms, sentence_speaker, text) in enumerate(raw_sentences):
            if index + 1 < len(raw_sentences):
                end_ms = max(start_ms + 500, raw_sentences[index + 1][0])
            else:
                end_ms = start_ms + 3000
            segments.append(
                TranscriptSegment(start_ms, end_ms, text, sentence_speaker)
            )

        language_value = data.get("language") or ""
        language = language_value if isinstance(language_value, str) else str(language_value)
        title = str(metadata.get("name") or data.get("episodeName") or f"Spotify-Episode {episode_id}")
        show = str(metadata.get("show") or data.get("showName") or "")
        return Transcript(
            title=title.strip(),
            show=show.strip(),
            source_url=source_url,
            language=language.strip(),
            segments=tuple(segments),
            notice=(
                "Vorhandenes Spotify-Transkript ueber eine inoffizielle Schnittstelle abgerufen; "
                "automatisch erzeugter Text kann Fehler enthalten."
            ),
            timing_origin="provided",
        )

class _ExpiredTokenError(Exception):
    pass
