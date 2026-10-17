"""Richtet die YouTube-Abhaengigkeit lokal ein und startet danach die App."""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


REQUIRED_VERSION = "1.2.4"
APP_DIRECTORY = Path(__file__).resolve().parent
LOCAL_PACKAGES = APP_DIRECTORY / "packages"


def _activate_local_packages() -> None:
    value = str(LOCAL_PACKAGES)
    if value not in sys.path:
        sys.path.insert(0, value)
    importlib.invalidate_caches()


def _installed_version() -> str | None:
    _activate_local_packages()
    try:
        return importlib.metadata.version("youtube-transcript-api")
    except importlib.metadata.PackageNotFoundError:
        return None


def _dependency_ready() -> bool:
    if _installed_version() != REQUIRED_VERSION:
        return False
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        return callable(getattr(YouTubeTranscriptApi(), "list", None))
    except (ImportError, OSError):
        return False


def _install_dependency(parent: tk.Misc) -> bool:
    approved = messagebox.askyesno(
        "YouTube-Komponente einmalig einrichten",
        (
            "Für den YouTube-Abruf benötigt die Python-Version einmalig "
            f"youtube-transcript-api {REQUIRED_VERSION} samt Hilfspaketen.\n\n"
            "Die Dateien werden direkt vom Python Package Index (PyPI) geladen und "
            "nur im Unterordner 'packages' dieser App gespeichert. Es sind keine "
            "Administratorrechte nötig.\n\n"
            "Dabei werden keine Spotify-Cookies, Links oder Transkripte übertragen. "
            "Die Einrichtung kann einige Sekunden dauern. Jetzt installieren?"
        ),
        parent=parent,
    )
    if not approved:
        return False

    LOCAL_PACKAGES.mkdir(exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "--target",
        str(LOCAL_PACKAGES),
        f"youtube-transcript-api=={REQUIRED_VERSION}",
    ]
    creation_flags = 0x08000000 if sys.platform == "win32" else 0
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            creationflags=creation_flags,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        messagebox.showerror(
            "Einrichtung fehlgeschlagen",
            f"Python konnte die YouTube-Komponente nicht installieren:\n\n{exc}",
            parent=parent,
        )
        return False

    _activate_local_packages()
    if completed.returncode != 0 or not _dependency_ready():
        details = (completed.stderr or completed.stdout or "Keine Details verfügbar.").strip()
        if len(details) > 1200:
            details = details[-1200:]
        messagebox.showerror(
            "Einrichtung fehlgeschlagen",
            (
                "Die YouTube-Komponente konnte nicht vollständig eingerichtet werden. "
                "Bitte prüfen Sie die Internetverbindung.\n\nDetails:\n" + details
            ),
            parent=parent,
        )
        return False

    messagebox.showinfo(
        "Einrichtung abgeschlossen",
        "Die YouTube-Komponente wurde lokal installiert. Die App wird jetzt gestartet.",
        parent=parent,
    )
    return True


def main() -> int:
    if "--check-only" in sys.argv:
        return 0 if _dependency_ready() else 1

    prompt_root = tk.Tk()
    prompt_root.withdraw()
    try:
        ready = _dependency_ready()
        if not ready:
            ready = _install_dependency(prompt_root)
            if not ready:
                continue_without_youtube = messagebox.askyesno(
                    "Ohne YouTube starten?",
                    (
                        "Die App kann weiterhin für Spotify und lokale Dateien gestartet "
                        "werden. Ohne eingerichtete Komponente funktioniert nur der "
                        "YouTube-Abruf nicht. Trotzdem starten?"
                    ),
                    parent=prompt_root,
                )
                if not continue_without_youtube:
                    return 1
    finally:
        prompt_root.destroy()

    _activate_local_packages()
    from spotify_transcript_app.gui import main as start_app

    start_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
