# Technische Analyse und Umsetzung des Spotify-Abrufs

Stand: 17. Oktober 2026. Dies ist eine technische Risikobewertung und keine Rechtsberatung.

Die Projektanforderung wurde nach Version 0.4 ausdrücklich geändert: Die inoffizielle Spotify-Schnittstelle und eine manuelle Sitzungsauthentifizierung sollen nun trotz der dokumentierten Stabilitäts- und Nutzungsbedingungen-Risiken unterstützt werden. Version 0.5 setzt diese Entscheidung als getrenntes Modul um.

## 1. Geprueftes Referenzprojekt

Referenz: <https://github.com/glebo309/spotify-transcript>

Der fremde Quellcode wurde statisch gelesen, aber weder installiert noch ausgefuehrt. Das Repository ist sehr klein: ein einzelnes Python-Skript mit Kommandozeilen-/Dialoglogik, Plattform-Starter und Offline-Tests. Laut Repository wird nur die Python-Standardbibliothek benoetigt; `yt-dlp` ist eine optionale externe Abhaengigkeit fuer das automatische Auslesen eines Browser-Cookies. Die MIT-Lizenz erlaubt grundsaetzlich Wiederverwendung, beseitigt aber keine Rechte oder Bedingungen von Spotify beziehungsweise Rechteinhabern.

### Architektur

Das Referenzskript vereint mehrere Aufgaben in einer Datei:

1. Spotify-Link beziehungsweise ID parsen.
2. `sp_dc`-Sitzungscookie automatisch ueber `yt-dlp` aus einem Browserprofil lesen oder manuell entgegennehmen.
3. Aus Cookie, Spotify-Serverzeit und einem nachgebildeten TOTP-Verfahren ein kurzlebiges Zugriffstoken erzeugen.
4. Einen privaten Web-Player-Endpunkt fuer das Transkript abfragen.
5. Metadaten aus der oeffentlichen Spotify-Embed-Seite extrahieren.
6. Daten als Markdown, TXT, SRT oder JSON speichern.
7. Cookie, Einstellungen, TOTP-Geheimnisse und Zugriffstoken lokal zwischenspeichern.

Die Renderer und die Linkpruefung sind konzeptionell brauchbar. Authentifizierung, Netzwerkzugriff und Benutzeroberflaeche sind jedoch eng gekoppelt. Fuer eine wartbare Windows-App ist eine Trennung in GUI, Datenquelle, neutrales Modell und Export sinnvoller; die vorliegende Anwendung setzt diese Trennung um.

### Netzwerkzugriffe des Referenzprojekts

- `raw.githubusercontent.com/CycloneAddons/spotify-token-generator/.../secretDict.json` zum taeglichen Aktualisieren der TOTP-Geheimnisse;
- `open.spotify.com/api/server-time` fuer die Serverzeit;
- `open.spotify.com/api/token` mit dem `sp_dc`-Cookie und berechnetem TOTP-Code;
- `spclient.wg.spotify.com/transcript-read-along/v2/episode/<id>?format=json` fuer das Transkript;
- `open.spotify.com/embed/episode/<id>` zum Auslesen von Metadaten.

Der eigentliche Transkript-Endpunkt und der Token-Handshake sind nicht Teil der dokumentierten Spotify Web API. Das Skript gibt sich mit einem fest codierten Browser-User-Agent und Web-Player-Headern als Web-Player-Client aus.

### Authentifizierung und Datenschutzrisiken

- `sp_dc` ist ein langlebiges Sitzungskriterium und damit wie ein Zugangsschluessel zu behandeln.
- Die automatische Browserextraktion greift auf sensible Profildaten zu. Das widerspricht der Vorgabe dieses Projekts und wird nicht uebernommen.
- Die manuelle Uebergabe per Kommandozeilenparameter kann das Cookie in Shell-Verlauf oder Prozesslisten sichtbar machen.
- Das Cookie und das Zugriffstoken werden im Referenzprojekt als Klartextdateien gespeichert. `chmod(0600)` ist unter Windows kein gleichwertiger Ersatz fuer gezielt gesetzte NTFS-Zugriffsrechte.
- Rotierende TOTP-Geheimnisse werden aus einem fremden GitHub-Repository nachgeladen. Das schafft eine zusaetzliche Lieferketten- und Verfuegbarkeitsabhaengigkeit.

### Zuverlaessigkeits- und Wartungsrisiken

- Private Endpunkte, Antwortformate und TOTP-Geheimnisse koennen jederzeit ohne Ankuendigung wechseln.
- Es gibt keinen vertraglich dokumentierten Stabilitaetsrahmen fuer den Transkript-Endpunkt.
- Nicht jede Episode, jedes Land oder jedes Konto hat Zugriff auf ein Transkript.
- Das kleine, junge Repository hat nur wenig Nutzungssignale; Tests koennen die reale private Schnittstelle nicht absichern.
- Ein fest codierter User-Agent, HTML-Scraping der Embed-Seite und fehlende ausgefeilte Behandlung von Rate Limits machen den Abruf zusaetzlich fragil.

## 2. Offiziell zulaessige Schnittstellen

Die dokumentierte Spotify Web API bietet fuer Episoden Metadaten, aber keinen Transkript-Endpunkt: <https://developer.spotify.com/documentation/web-api/reference/get-an-episode>

Die Spotify Developer Terms untersagen unter anderem Reverse Engineering, unautorisierten Zugriff und Funktionen, die dauerhafte Kopien von Spotify-Inhalten erleichtern: <https://developer.spotify.com/terms>

Die Developer Policy fordert Transparenz, Datenschutz und die Beachtung der Rechte von Urhebern: <https://developer.spotify.com/policy>

Fuer eigene Podcasts koennen berechtigte Urheber ihr Transkript offiziell in Spotify for Creators als VTT herunterladen. Diese Moeglichkeit gilt nicht als allgemeine Hoerer-API und steht nicht fuer alle Creator zur Verfuegung: <https://support.spotify.com/ga-en/creators/article/managing-episode-transcripts-on-spotify/>

Aus diesen Quellen folgt: Fuer beliebige Spotify-Episoden existiert nach der geprueften offiziellen Dokumentation kein allgemeiner, dokumentierter und stabiler Transkript-Abruf fuer Drittanbieter-Apps. Version 0.5 verwendet deshalb auf ausdrücklichen Wunsch des Nutzers die inoffizielle Variante und kennzeichnet sie entsprechend.

## 3. Saubere Alternativen

1. **Eigene Folgen:** Der Nutzer laedt sein VTT in Spotify for Creators herunter und importiert es lokal in die App. Das ist der klarste offizielle Weg fuer Rechteinhaber.
2. **Vom Herausgeber veroeffentlichte Transkripte:** Offene RSS-Feeds koennen ueber den Podcasting-2.0-Tag `<podcast:transcript>` direkt auf TXT, VTT, SRT oder JSON verweisen. Spezifikation: <https://github.com/Podcastindex-org/podcast-namespace/blob/main/podcast.xsd>
3. **Direkter Datei-/URL-Import mit Einwilligung:** Der Nutzer gibt selbst eine vom Herausgeber freigegebene Transkriptdatei oder -URL an. Vor einem Download muessen Host, Zweck und Datenfluss angezeigt werden.

Ein Spotify-Episodenlink allein laesst sich nicht ueber eine dokumentierte Spotify-API zuverlaessig auf den urspruenglichen RSS-Feed und dessen konkrete Episode abbilden. Ein externer Podcast-Index waere eine weitere Partei, benoetigte eigene Bedingungen und je nach Dienst API-Zugangsdaten. Er sollte daher nur als deutlich gekennzeichnete, freiwillige Erweiterung kommen.

## 4. Sicherheitsgrenzen der inoffiziellen Integration

- Das Browserprofil wird nicht automatisch gelesen. Der Nutzer kopiert `sp_dc` bewusst in ein maskiertes Eingabefeld.
- Cookie und Zugriffstoken werden weder protokolliert noch auf die Festplatte geschrieben.
- Das Cookie wird im Code technisch auf das Ziel `open.spotify.com/api/token` beschränkt.
- Der Bearer-Token wird technisch auf `spclient.wg.spotify.com` beschränkt.
- Weiterleitungen auf fremde Hosts werden blockiert.
- Die von einem Drittprojekt geladene Secret-Liste wird streng als kleine Zuordnung aus Versionsnummern und Byte-Listen validiert. Sie erhält keine Spotify-Anmeldedaten.
- Netzwerkfehler zeigen keine Anfrageheader, Cookies oder Tokens an.
- Mit **Vergessen** oder beim Beenden der App werden die Sitzungswerte aus dem App-Zustand entfernt.

## 5. Ergebnis der Spotify-Testversion 0.5

Der relevante Kern des MIT-lizenzierten Referenzprojekts wurde in `spotify_client.py` adaptiert. UI, Spotify-Netzwerkcode, neutrales Transkriptmodell und Export bleiben getrennt. Die automatische Browser-Cookie-Auslese, Klartext-Konfigurationsdatei und Kommandozeilenübergabe sensibler Werte wurden nicht übernommen.

35 Offline-Tests prüfen den bisherigen Import/Export und zusätzlich Cookieformat, einen festen TOTP-Testvektor, Spotify-Antwortnormalisierung, fehlende Transkripte, Fremdhost-Weiterleitungen sowie die Zielbindung von Cookie und Zugriffstoken. Ein echter Ende-zu-Ende-Abruf benötigt das persönliche Cookie des Nutzers und muss deshalb lokal durch den Nutzer erfolgen. Erst nach diesem Praxistest wird die YouTube-Integration ergänzt.
# YouTube-Integration (Version 0.6)

Als Referenz und Laufzeitabhängigkeit dient `jdepoix/youtube-transcript-api` 1.2.4. Die statische Prüfung ergab:

- Python-Unterstützung 3.8 bis 3.14, MIT-Lizenz;
- direkte Abhängigkeiten `requests` und `defusedxml`;
- eine eigene `requests.Session` pro API-Instanz;
- GET der YouTube-Videoseite, POST an YouTubes interne Innertube-Player-Schnittstelle und GET der ausgewählten Untertitelspur;
- kein offizieller YouTube-API-Schlüssel und kein Browser erforderlich;
- Cookie-Authentifizierung ist laut Projekt derzeit durch YouTube-Änderungen außer Funktion;
- bekannte Fehlerfälle: deaktivierte Untertitel, nicht verfügbares oder altersbeschränktes Video, IP-/Bot-Blockade und geändertes internes Datenformat.

Unsere Kapselung in `youtube_client.py` prüft Links lokal, übergibt nur die elfstellige Video-ID, bevorzugt `de`/`de-*`, danach `en`/`en-*` und dann eine andere vorhandene Spur. Innerhalb einer Sprache wird eine manuelle Spur vor einer automatisch erzeugten gewählt. Eine Übersetzung, Anmeldung oder Proxy-Umgehung findet nicht statt.

Version 0.9 erlaubt zusätzlich eine ausdrückliche Sprachauswahl. Dabei wird nur eine vorhandene Spur mit dem gewählten Sprachcode geladen; fehlt sie, nennt die App die von YouTube gemeldeten Alternativen. Der Automatikmodus behält die bisherige Reihenfolge bei.

Der Abruf ist zuverlässig, solange YouTubes aktuelle Web-Schnittstelle und die jeweilige Untertitelspur verfügbar sind. Er besitzt wegen der undokumentierten Schnittstelle keine Stabilitätsgarantie. Die restliche Anwendung bleibt durch das gemeinsame `Transcript`-Datenmodell unabhängig davon.
