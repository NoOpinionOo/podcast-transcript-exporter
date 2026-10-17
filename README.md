# Podcast-Transkript-Exporter – Version 0.9

Die lokale Windows-App ruft vorhandene Transkripte zu Spotify-Episoden und YouTube-Videos ab, zeigt sie an und exportiert sie als TXT, Markdown oder SRT. Für YouTube wird `youtube-transcript-api` 1.2.4 verwendet; der Spotify-Abruf basiert auf `glebo309/spotify-transcript`.

Version 0.9 ergänzt eine gezielte YouTube-Sprachauswahl, verstellbare Schriftgröße und bequemere Exportaktionen. Nach dem Export kann die Datei oder ihr Ordner unmittelbar geöffnet werden; der zuletzt verwendete Exportordner wird für den nächsten Start vorgemerkt.

Version 0.8 ergänzte den vollständigen Hell-/Dunkelmodus. Die Einstellungsdatei speichert nun Farbschema, Schriftgröße, YouTube-Sprachauswahl und letzten Exportordner lokal in `settings.json`. Sie enthält keine Links, Cookies oder Transkripte.

Die in Version 0.7 überarbeitete Oberfläche bleibt erhalten: Plattformen werden automatisch erkannt, Spotify-Anmeldung und Zusatzimporte erscheinen nur bei Bedarf, Abrufe besitzen eine Fortschrittsanzeige und die Vorschau bietet Metadaten, Suche, Treffer-Navigation und Kopieren.

## Start ohne Kommandozeile

Der empfohlene Start für Version 0.9 erfolgt über das Python-Startpaket, weil Windows die unsignierte EXE je nach Sicherheitsrichtlinie blockieren kann.

Wenn Windows die EXE blockiert, entpacken Sie stattdessen das Python-Startpaket und öffnen Sie **`1-Einrichten-und-starten.pyw` mit Python**. Beim ersten Start:

1. Die App erklärt den Download der YouTube-Komponente und fragt um Zustimmung.
2. Nach Ihrer Zustimmung wird `youtube-transcript-api` 1.2.4 nur in den lokalen App-Unterordner `packages` installiert.
3. Danach und bei späteren Starts öffnet sich die App direkt. Es sind keine Administratorrechte und keine Kommandozeile nötig.

Anschließend:

1. Fügen Sie oben einen Spotify- oder YouTube-Link ein.
2. Bei YouTube können Sie die gewünschte Sprache auswählen oder **Automatisch** verwenden.
3. Klicken Sie auf **Transkript abrufen**.
4. Ändern Sie die Schriftgröße bei Bedarf mit **A−** und **A+**.
5. Wählen Sie unten TXT, Markdown oder SRT und klicken Sie auf **Exportieren …**.

YouTube benötigt keine Anmeldung. Im Automatikmodus bevorzugt die App vorhandene deutsche Untertitel, danach Englisch und anschließend eine andere verfügbare Sprache. Bei einer gezielten Auswahl verwendet sie nur die gewünschte Sprache und zeigt andernfalls die verfügbaren Alternativen an. Sie übersetzt den Text nicht künstlich.

## Spotify-Anmeldung

Spotify benötigt weiterhin den Wert Ihres Cookies `sp_dc`:

1. Öffnen Sie [open.spotify.com](https://open.spotify.com/) in Chrome oder Edge und melden Sie sich an.
2. Drücken Sie `F12` und öffnen Sie **Application/Anwendung**.
3. Wählen Sie **Storage/Speicher > Cookies > https://open.spotify.com**.
4. Suchen Sie `sp_dc`, kopieren Sie nur dessen **Value/Wert** und geben Sie ihn im maskierten Fenster der App ein.

Das Cookie ist so vertraulich wie eine Anmeldung. Es wird nicht automatisch aus dem Browser gelesen, nicht gespeichert und nur an `open.spotify.com/api/token` gesendet. Beim Beenden der App wird es verworfen.

## Unterstützte Links und Funktionen

- Spotify-Episodenlinks von `open.spotify.com/episode/...`;
- normale YouTube-Links, `youtu.be`-Kurzlinks sowie YouTube-Shorts- und Live-Links;
- deutsche Transkripte bevorzugt, Englisch als erste Alternative;
- gezielte Auswahl häufiger YouTube-Transkriptsprachen;
- manuell bereitgestellte und automatisch erzeugte YouTube-Untertitel;
- verstellbare und gespeicherte Schriftgröße der Vorschau;
- optional sichtbare Zeitstempel in Vorschau, TXT und Markdown;
- Export als TXT, Markdown und SRT;
- Exportabschluss mit „Datei öffnen“ und „Ordner öffnen“;
- lokaler Import von VTT, SRT und TXT;
- öffentlicher Podcasting-2.0-RSS-Import und direkte Transkriptlinks.

## Netzwerkzugriffe

- Spotify: `open.spotify.com`, `spclient.wg.spotify.com` sowie optional die öffentliche TOTP-Secret-Liste auf `raw.githubusercontent.com`; das Spotify-Cookie wird nur an den Token-Endpunkt gesendet.
- YouTube: `youtube.com` sowie die von YouTube gelieferten Untertiteladressen. Die Bibliothek lädt die Videoseite, fragt die interne Player-Schnittstelle ab und lädt die ausgewählte Untertitelspur.
- YouTube erhält dabei die übliche IP-Adresse und HTTP-Header, aber weder das Spotify-Cookie noch andere Anmeldedaten aus dieser App.

## Einschränkungen und Einwilligung

- Beide automatischen Abrufe verwenden nicht offiziell dokumentierte Web-Schnittstellen. Spotify oder YouTube können sie jederzeit ändern oder blockieren.
- Nicht jede Episode und nicht jedes Video hat ein Transkript. Private, altersbeschränkte oder regional gesperrte Videos können scheitern.
- YouTube kann bei zu vielen Anfragen eine IP-Adresse zeitweise blockieren. Diese App integriert bewusst weder Proxys noch eine YouTube-Cookie-Anmeldung.
- Automatisch erzeugte Transkripte können Erkennungsfehler enthalten.
- Prüfen Sie vor Nutzung oder Veröffentlichung die Plattformbedingungen und die Rechte der Inhalte. Der Abruf bedeutet nicht automatisch, dass eine Weiterveröffentlichung erlaubt ist.
- Die Anwendung ist nicht digital signiert. Windows SmartScreen kann deshalb warnen.
- Eine Windows-Anwendungssteuerungsrichtlinie kann eine unsignierte PyInstaller-EXE vollständig blockieren. Der Python-Startweg ist dafür die vorgesehene Alternative; die Richtlinie wird nicht deaktiviert oder umgangen.

Mit **Transkript abrufen** veranlassen Sie den beschriebenen direkten Netzwerkzugriff an Spotify beziehungsweise YouTube.

## Tests und Quellstart

Die Version enthält 48 Offline-Unit-Tests. Der zusätzliche GUI-Selbsttest prüft Ressourcen, Hell- und Dunkelmodus, Schriftgröße, Sprachauswahl, Kopfzeile, Suche, dynamische Spotify-/YouTube-Ansicht und den einklappbaren Importbereich. Zusätzlich wurden echte Abrufe mit dem vom Nutzer geprüften Spotify-Link und zwei öffentlichen YouTube-Videos getestet: Deutsch wurde bevorzugt, Englisch korrekt als Alternative gewählt.

```powershell
py -3 -m pip install -r requirements.txt
py -3 -m unittest discover -s tests -v
py -3 run_app.pyw
```

## Projektaufbau

```text
run_app.pyw                              Startpunkt
spotify_transcript_app/gui.py            gemeinsame Benutzeroberfläche
spotify_transcript_app/spotify_client.py Spotify-Abruf und Anmeldung
spotify_transcript_app/youtube_client.py YouTube-URL, Sprachauswahl und Abruf
spotify_transcript_app/models.py         neutrales Datenmodell
spotify_transcript_app/exporters.py      TXT/Markdown/SRT
tests/                                   Offline-Tests
```

Technische Details und Netzwerkziele stehen in `TECHNISCHE_ANALYSE.md`; Hinweise zu eingebautem Drittcode in `THIRD_PARTY_NOTICES.md`.

## Datenschutz beim Entwickeln

`settings.json`, der lokale Ordner `packages/`, Build-Ausgaben und Selbsttestdateien sind durch `.gitignore` ausgeschlossen. Spotify-Cookie und Zugriffstoken werden von der App nicht auf die Festplatte geschrieben. Vor einem öffentlichen Commit sollte trotzdem mit `git status` geprüft werden, dass keine persönlichen Exporte oder Screenshots hinzugefügt wurden.

## Lizenz

Der eigene Quellcode dieses Projekts steht unter der MIT-Lizenz. Abhängigkeiten und übernommene Bestandteile behalten ihre jeweiligen Lizenzen; Einzelheiten stehen in `THIRD_PARTY_NOTICES.md`.
