# Hinweise zu Drittcode

## spotify-transcript

- Projekt: https://github.com/glebo309/spotify-transcript
- Lizenz: MIT
- Übernommen beziehungsweise adaptiert: Cookievalidierung, Spotify-Webplayer-TOTP, Tokenabruf, `transcript-read-along`-Abruf und Interpretation der Spotify-Transkriptabschnitte.
- Nicht übernommen: automatische Browser-Cookie-Auslese, Kommandozeilenoberfläche und dauerhafte Speicherung des Cookies.

Die ursprüngliche `LICENSE`-Datei ist im verlinkten Repository maßgeblich. Die MIT-Lizenz erlaubt Nutzung und Änderung unter Beibehaltung des Copyright- und Lizenzhinweises und schließt Gewährleistung aus.

## spotify-token-generator – Secret-Liste

- Datenquelle: https://github.com/CycloneAddons/spotify-token-generator
- Verwendete Datei: `secrets/secretDict.json`
- Zweck: Aktualisierung der von Spotifys Webplayer verwendeten TOTP-Versionen.
- Es wird ausschließlich eine kleine JSON-Datei abgerufen. Cookie und Spotify-Zugriffstoken werden bei dieser Anfrage nicht mitgesendet.

## youtube-transcript-api 1.2.4

- Projekt: https://github.com/jdepoix/youtube-transcript-api
- Copyright: © 2018 Jonas Depoix
- Lizenz: MIT
- Zweck: Abruf vorhandener manueller oder automatisch erzeugter YouTube-Untertitel.
- Direkte Abhängigkeiten: `requests` und `defusedxml`.
- Die App nutzt keine Proxy-Funktion, keine YouTube-Cookies und keine Übersetzungsfunktion.

MIT License

Copyright (c) 2018 Jonas Depoix

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
