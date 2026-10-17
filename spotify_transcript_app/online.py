"""Explizit bestaetigte, eingeschraenkte HTTPS-Zugriffe fuer Online-Importe."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)


USER_AGENT = "Podcast-Transkript-Exporter/0.4 (+lokale Windows-App)"
MAX_REDIRECTS = 3


class RemoteUrlError(ValueError):
    """Eine externe URL verletzt die Sicherheitsregeln."""


class NetworkFetchError(RuntimeError):
    """Ein bestaetigter Netzwerkabruf ist fehlgeschlagen."""


@dataclass(frozen=True)
class RemoteUrl:
    url: str
    host: str


@dataclass(frozen=True)
class DownloadedResource:
    body: bytes
    final_url: str
    content_type: str


def validate_public_https_url(value: str) -> RemoteUrl:
    """Prueft eine URL rein lokal; DNS wird erst nach Einwilligung aufgeloest."""

    candidate = value.strip()
    if not candidate:
        raise RemoteUrlError("Bitte eine HTTPS-Adresse eingeben.")
    if len(candidate) > 2048:
        raise RemoteUrlError("Die Adresse ist ungewoehnlich lang.")
    if "\\" in candidate or any(char.isspace() or ord(char) < 32 for char in candidate):
        raise RemoteUrlError("Die Adresse enthaelt unzulaessige Zeichen.")

    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise RemoteUrlError("Die Adresse ist nicht gueltig.") from exc
    if parsed.scheme.lower() != "https":
        raise RemoteUrlError("Aus Sicherheitsgruenden werden nur HTTPS-Adressen abgerufen.")
    if not parsed.hostname:
        raise RemoteUrlError("In der Adresse fehlt ein Servername.")
    if parsed.username is not None or parsed.password is not None:
        raise RemoteUrlError("Zugangsdaten duerfen nicht Bestandteil der Adresse sein.")
    if parsed.fragment:
        raise RemoteUrlError("Bitte den Teil nach dem #-Zeichen aus der Adresse entfernen.")
    if port not in (None, 443):
        raise RemoteUrlError("Online-Importe sind nur ueber den HTTPS-Standardport 443 erlaubt.")

    raw_host = parsed.hostname.rstrip(".")
    try:
        host = raw_host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise RemoteUrlError("Der Servername ist nicht gueltig.") from exc
    if not host or host == "localhost" or host.endswith((".localhost", ".local")):
        raise RemoteUrlError("Lokale Serveradressen werden nicht abgerufen.")

    try:
        literal_address = ipaddress.ip_address(host)
    except ValueError:
        literal_address = None
    if literal_address is not None and not literal_address.is_global:
        raise RemoteUrlError("Private, lokale oder reservierte IP-Adressen werden nicht abgerufen.")

    normalized_host = f"[{host}]" if ":" in host else host
    normalized_url = urlunsplit(("https", normalized_host, parsed.path or "/", parsed.query, ""))
    return RemoteUrl(normalized_url, host)


def _ensure_public_destination(
    host: str,
    resolver: Callable[..., list[tuple]],
) -> None:
    try:
        results = resolver(host, 443, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise NetworkFetchError(f"Der Server {host} konnte nicht gefunden werden.") from exc
    if not results:
        raise NetworkFetchError(f"Der Server {host} lieferte keine Netzwerkadresse.")

    addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for result in results:
        address_text = str(result[4][0]).split("%", 1)[0]
        try:
            addresses.add(ipaddress.ip_address(address_text))
        except ValueError as exc:
            raise NetworkFetchError("Die DNS-Antwort enthielt eine ungueltige IP-Adresse.") from exc
    if not addresses or any(not address.is_global for address in addresses):
        raise NetworkFetchError(
            "Der Servername verweist auf eine private, lokale oder reservierte Adresse. "
            "Der Abruf wurde blockiert."
        )


class SameHostRedirectHandler(HTTPRedirectHandler):
    """Erlaubt wenige HTTPS-Weiterleitungen, aber keinen Wechsel der Domain."""

    def __init__(self, original_host: str, resolver: Callable[..., list[tuple]]) -> None:
        super().__init__()
        self.original_host = original_host
        self.resolver = resolver
        self.redirect_count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        target = validate_public_https_url(urljoin(req.full_url, newurl))
        if target.host != self.original_host:
            raise NetworkFetchError(
                "Der Server wollte zu einer anderen Domain weiterleiten. "
                "Bitte diese Zieladresse separat eingeben und bestaetigen."
            )
        self.redirect_count += 1
        if self.redirect_count > MAX_REDIRECTS:
            raise NetworkFetchError("Zu viele Weiterleitungen; der Abruf wurde beendet.")
        _ensure_public_destination(target.host, self.resolver)
        return super().redirect_request(req, fp, code, msg, headers, target.url)


class SafeHttpClient:
    """Kleiner HTTP-Client ohne Cookies, Proxy-Automatik oder Fremddomain-Redirects."""

    def __init__(self, *, resolver=socket.getaddrinfo, opener=None) -> None:
        self.resolver = resolver
        self.opener = opener

    def fetch(self, url: str, *, max_bytes: int, accept: str) -> DownloadedResource:
        target = validate_public_https_url(url)
        _ensure_public_destination(target.host, self.resolver)
        if max_bytes <= 0:
            raise ValueError("max_bytes muss positiv sein")

        opener = self.opener
        if opener is None:
            opener = build_opener(
                ProxyHandler({}),
                HTTPSHandler(),
                SameHostRedirectHandler(target.host, self.resolver),
            )
        request = Request(
            target.url,
            method="GET",
            headers={
                "Accept": accept,
                "Accept-Encoding": "identity",
                "Cache-Control": "no-cache",
                "User-Agent": USER_AGENT,
            },
        )

        try:
            with opener.open(request, timeout=12) as response:
                status = getattr(response, "status", 200)
                if not 200 <= status < 300:
                    raise NetworkFetchError(f"Der Server antwortete mit HTTP-Status {status}.")

                final = validate_public_https_url(response.geturl())
                if final.host != target.host:
                    raise NetworkFetchError(
                        "Die Antwort kam von einer nicht bestaetigten Domain und wurde verworfen."
                    )

                encoding = (response.headers.get("Content-Encoding") or "identity").lower()
                if encoding not in {"", "identity"}:
                    raise NetworkFetchError("Komprimierte HTTP-Antworten werden nicht verarbeitet.")

                length_header = response.headers.get("Content-Length")
                if length_header:
                    try:
                        declared_length = int(length_header)
                    except ValueError:
                        declared_length = 0
                    if declared_length > max_bytes:
                        raise NetworkFetchError("Die angegebene Datei ist groesser als das erlaubte Limit.")

                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise NetworkFetchError("Die Datei ist groesser als das erlaubte Limit.")
                raw_content_type = response.headers.get("Content-Type") or "application/octet-stream"
                content_type = raw_content_type.split(";", 1)[0].strip().lower()
                return DownloadedResource(body, final.url, content_type)
        except NetworkFetchError:
            raise
        except HTTPError as exc:
            raise NetworkFetchError(f"Der Server antwortete mit HTTP-Status {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            raise NetworkFetchError(f"Der HTTPS-Abruf ist fehlgeschlagen: {reason}") from exc


def filename_from_url(url: str, fallback: str) -> str:
    name = unquote(urlsplit(url).path.rsplit("/", 1)[-1]).strip()
    if not name or len(name) > 160 or any(char in name for char in '<>:"/\\|?*'):
        return fallback
    return name


def infer_transcript_format(url: str, content_type: str, declared_type: str = "") -> str:
    supported_types = {
        "text/vtt": ".vtt",
        "application/srt": ".srt",
        "application/x-subrip": ".srt",
        "text/srt": ".srt",
        "text/plain": ".txt",
    }
    for media_type in (declared_type, content_type):
        normalized = media_type.split(";", 1)[0].strip().lower()
        if normalized in supported_types:
            return supported_types[normalized]

    path = urlsplit(url).path.lower()
    for extension in (".vtt", ".srt", ".txt"):
        if path.endswith(extension):
            return extension
    raise NetworkFetchError("Der Link liefert kein unterstuetztes VTT-, SRT- oder TXT-Format.")
