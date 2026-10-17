# Projektspezifische Entwicklungsregeln

Diese Regeln ergänzen die globalen Entwicklungsregeln für den
`podcast-transcript-exporter`. Bei Widersprüchen gelten die globalen Regeln.

## Technischer Rahmen

- Die Anwendung ist eine lokale Windows-Desktop-App auf Basis von Python 3.10+
  und Tkinter. Sie soll ohne Webserver und unabhängig von einem Launcher
  funktionieren.
- `1-Einrichten-und-starten.pyw` ist der empfohlene interaktive Einstieg. Der
  Helfer installiert `youtube-transcript-api==1.2.4` nach Zustimmung
  ausschließlich in den lokalen, nicht versionierten Ordner `packages/`.
- `run_app.pyw` ist der direkte Einstieg für Entwicklung und ProjectHub. Mit
  `--self-test` führt er den GUI-Selbsttest aus.
- Die eigentliche Anwendung liegt in `spotify_transcript_app/`; Offline-Tests
  liegen in `tests/`.
- Die Versionsnummer muss zwischen `spotify_transcript_app/__init__.py`,
  `windows_version_info.txt`, `README.md`, `BUILD_INFO.md` und
  `projecthub.json` konsistent bleiben.

## Sicherheit und Datenschutz

- Niemals Spotify-Cookies, Zugriffstoken, Transkripte, persönliche Exportpfade
  oder andere Zugangsdaten protokollieren, versionieren oder in Tests ablegen.
- `settings.json` enthält nur unkritische UI-Einstellungen und bleibt lokal.
- Die Hostbindung von Cookie und Bearer-Token sowie der Schutz gegen private
  Netzwerkziele und fremde Weiterleitungen dürfen nicht abgeschwächt werden.
- Neue Netzwerkziele, Abhängigkeiten oder automatische Downloads müssen vor der
  Umsetzung dokumentiert und ausdrücklich begründet werden.
- Echte Online-Tests dürfen nur mit ausdrücklicher Zustimmung und niemals mit
  fest im Projekt gespeicherten Zugangsdaten erfolgen.

## Änderungen und Tests

- Änderungen an Import, Export, URL-Prüfung oder Netzwerkcode benötigen passende
  Offline-Tests.
- Vor Abschluss mindestens ausführen:

  ```powershell
  py -3 -m unittest discover -s tests -v
  py -3 run_app.pyw --self-test
  ```

- Der GUI-Selbsttest benötigt eine funktionierende Windows-Desktop-Sitzung und
  die lokale oder in der aktiven Python-Umgebung installierte YouTube-Abhängigkeit.
- Live-Abrufe sind ergänzende Praxistests und ersetzen die Offline-Tests nicht.
- Nach wesentlichen Änderungen `PROJECT_STATUS.md` aktualisieren; bei geänderten
  Funktionen, Voraussetzungen oder Startwegen auch `README.md` und
  `projecthub.json` anpassen.

## Build und Auslieferung

- Der optionale Windows-Build wird über `build_windows.ps1` und
  `Podcast-Transkript-Exporter.spec` erzeugt. `build/`, `dist/`, lokale Pakete
  und erzeugte Archive bleiben unversioniert.
- Eine erfolgreiche lokale EXE-Erzeugung ist keine Codesignatur. Keine
  Veröffentlichung, Signierung oder GitHub-Aktion ohne vorherige Zustimmung.
- Die lokalen Sicherungsverzeichnisse `.git-backup-initial/` und
  `.git-original-incorrect/` sowie `packages/` und `settings.json` nicht
  verschieben, löschen oder als Quellbestand behandeln.

## ProjectHub

- `projecthub.json` ist der maschinenlesbare Projektsteckbrief. Startbefehle
  müssen relativ zum stabilen Projektordner funktionieren.
- Der normale ProjectHub-Start soll den Einrichtungshelfer verwenden, damit eine
  fehlende YouTube-Abhängigkeit verständlich und mit Zustimmung ergänzt wird.
- Das Projekt muss jederzeit auch direkt über seine `.pyw`-Startdateien nutzbar
  bleiben.
