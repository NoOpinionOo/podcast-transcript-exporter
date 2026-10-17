# Projektstatus

Stand: 17. Oktober 2026  
Version: 0.9.0  
Status: Funktionsfähige lokale Windows-Desktop-App

## Kurzüberblick

Der Podcast-Transkript-Exporter kann vorhandene Transkripte von Spotify-Episoden
und YouTube-Videos abrufen, lokale VTT-/SRT-/TXT-Dateien importieren,
Podcasting-2.0-RSS-Transkripte laden und das Ergebnis als TXT, Markdown oder SRT
exportieren. Die Oberfläche bietet Vorschau, Suche, Zeitstempel, Hell-/Dunkelmodus,
Schriftgrößensteuerung und eine gespeicherte Auswahl unkritischer Einstellungen.

## Technischer Stand

- Python 3.10+ mit Tkinter; aktuell lokal geprüft mit Python 3.14.4.
- Anwendungsversion und Windows-Dateiversion stehen auf 0.9.0.
- Einzige direkte Laufzeitabhängigkeit: `youtube-transcript-api==1.2.4`.
- Die Abhängigkeit ist im lokalen, ignorierten Ordner `packages/` vollständig
  eingerichtet; eine globale Installation ist nicht erforderlich.
- Empfohlener Nutzerstart: `1-Einrichten-und-starten.pyw`.
- Direkter Entwicklungsstart: `py -3 run_app.pyw`.
- Repository: <https://github.com/NoOpinionOo/podcast-transcript-exporter>
- Branch: `main`; vor den hier dokumentierten Änderungen entsprach der lokale
  Commit `06ec608a30e66dcede3cb6288bd5e2b8d4b3df88` dem lokalen
  `origin/main`-Verweis.

## Verifizierter Stand

Am 17. Oktober 2026 wurden im bestehenden Projektordner ausgeführt:

| Prüfung | Ergebnis |
| --- | --- |
| `py -3 -m unittest discover -s tests -v` | 48 von 48 Tests bestanden |
| `py -3 1-Einrichten-und-starten.pyw --check-only` | Abhängigkeit einsatzbereit |
| `py -3 run_app.pyw --self-test` | GUI-Selbsttest bestanden |

Die Prüfungen verwenden keine Spotify-Zugangsdaten und führen keine echten
Spotify- oder YouTube-Abrufe aus.

## Bekannte Fehler und Einschränkungen

- Derzeit ist kein reproduzierbarer Fehler in den Offline-Tests oder im
  GUI-Selbsttest bekannt.
- Spotify- und YouTube-Abrufe verwenden nicht offiziell dokumentierte
  Web-Schnittstellen. Änderungen, Sperren oder Rate Limits der Plattformen
  können den Abruf jederzeit beeinträchtigen.
- Spotify benötigt ein manuell eingegebenes `sp_dc`-Cookie. Nicht jede Episode
  bietet ein Transkript; das Cookie wird bewusst nicht gespeichert.
- YouTube kann Untertitel für private, altersbeschränkte oder regional gesperrte
  Videos verweigern und IP-Adressen vorübergehend blockieren.
- Live-Abrufe gegen die externen Dienste wurden bei dieser Statusaktualisierung
  nicht erneut ausgeführt. Die letzten dokumentierten Praxistests stammen aus
  der Vorbereitung von Version 0.9.
- Die PyInstaller-EXE ist nicht digital signiert und kann deshalb von Windows
  SmartScreen oder einer Anwendungssteuerungsrichtlinie blockiert werden. Der
  Python-Startweg ist die vorgesehene Alternative.
- Es gibt noch keine automatisierte CI-Pipeline; die Tests werden derzeit lokal
  ausgeführt.

## Nächste sinnvolle Aufgaben

1. Das `projecthub.json` an das endgültige ProjectHub-Schema anbinden, sobald
   dessen verbindliche Spezifikation feststeht.
2. Eine CI-Prüfung für die 48 Offline-Tests auf unterstützten Python-Versionen
   einrichten.
3. Die inoffiziellen Spotify- und YouTube-Integrationen regelmäßig mit
   ausdrücklich freigegebenen öffentlichen Testinhalten prüfen.
4. Für eine breitere EXE-Auslieferung Codesignatur oder Microsoft-Store-Weg
   bewerten.
5. Abhängigkeitsupdates separat prüfen und erst nach vollständigem Test sowie
   aktualisierter Drittanbieter-Dokumentation übernehmen.

## Lokaler Arbeitsstand

Diese Projektvorbereitung ergänzt Dokumentation, Projektregeln, Ignore-Regeln
und ProjectHub-Metadaten. Sie enthält keine Änderung der Anwendungslogik und ist
noch nicht committed oder gepusht.
