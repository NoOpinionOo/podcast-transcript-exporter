"""Strikte, rein lokale Validierung von Spotify-Episodenlinks."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .models import EpisodeReference


EPISODE_ID_RE = re.compile(r"^[A-Za-z0-9]{22}$")
LOCALE_RE = re.compile(r"^intl-[A-Za-z]{2}(?:-[A-Za-z]{2})?$")


class EpisodeUrlError(ValueError):
    """Die Eingabe ist kein unterstuetzter Spotify-Episodenlink."""


def parse_episode_url(value: str) -> EpisodeReference:
    """Prueft eine Spotify-Episoden-URL ohne Netzwerkzugriff.

    Unterstuetzt werden die regulaere und die lokalisierte URL-Form, zum
    Beispiel ``/episode/<id>`` und ``/intl-de/episode/<id>``.
    """

    original = (value or "").strip()
    if not original:
        raise EpisodeUrlError("Bitte einen Spotify-Episodenlink eingeben.")

    try:
        parsed = urlsplit(original)
        port = parsed.port
    except ValueError as exc:
        raise EpisodeUrlError("Der Link ist syntaktisch ungueltig.") from exc

    if parsed.scheme.lower() != "https":
        raise EpisodeUrlError("Der Link muss mit https:// beginnen.")
    if (parsed.hostname or "").lower() != "open.spotify.com":
        raise EpisodeUrlError("Erlaubt sind nur Links von open.spotify.com.")
    if parsed.username or parsed.password or port is not None:
        raise EpisodeUrlError("Der Link enthaelt unzulaessige Anmelde- oder Portangaben.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) == 2 and parts[0] == "episode":
        episode_id = parts[1]
    elif len(parts) == 3 and LOCALE_RE.fullmatch(parts[0]) and parts[1] == "episode":
        episode_id = parts[2]
    else:
        raise EpisodeUrlError("Der Link muss direkt zu einer Spotify-Episode fuehren.")

    if not EPISODE_ID_RE.fullmatch(episode_id):
        raise EpisodeUrlError("Die Spotify-Episoden-ID muss genau 22 Zeichen lang sein.")

    canonical = f"https://open.spotify.com/episode/{episode_id}"
    return EpisodeReference(original, episode_id, canonical)

