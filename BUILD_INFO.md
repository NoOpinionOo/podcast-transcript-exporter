# Build-Informationen für Version 0.9

## Empfohlene Auslieferung

- Name: `Podcast-Transkript-Exporter-v0.9-Python-Startpaket.zip`
- Plattform: Windows mit vorhandener Python-Installation und Tkinter
- Startdatei: `1-Einrichten-und-starten.pyw`
- YouTube-Komponente: `youtube-transcript-api==1.2.4`

Der Starthelfer installiert die YouTube-Komponente nach ausdrücklicher Zustimmung nur in den lokalen App-Unterordner `packages`. Eine systemweite Installation und Administratorrechte sind nicht erforderlich.

## Geprüfte Funktionen

1. Alle 48 Offline-Unit-Tests laufen erfolgreich.
2. Der GUI-Selbsttest initialisiert Tkinter und alle eingebetteten Ressourcen.
3. Der Selbsttest prüft Hell-/Dunkelmodus, Schriftgröße, YouTube-Sprachauswahl, Plattformumschaltung, Transkriptsuche und den einklappbaren Importbereich.
4. Spotify-Abruf und YouTube-Sprachauswahl werden mit simulierten Antworten ohne echte Zugangsdaten getestet.
5. Echte öffentliche YouTube-Transkripte wurden in Deutsch und mit englischem Sprach-Fallback abgerufen.
6. Der Spotify-Praxistest wurde vom Nutzer erfolgreich durchgeführt.

## EXE-Hinweis

Eine neue unsignierte EXE würde von derselben Windows-Anwendungsrichtlinie blockiert. Deshalb wird Version 0.9 zunächst als geprüftes Python-Startpaket ausgeliefert. Für eine allgemein akzeptierte EXE ist später eine öffentliche Codesignatur oder eine Microsoft-Store-Auslieferung erforderlich.
