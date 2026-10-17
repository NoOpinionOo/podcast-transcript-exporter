"""Tkinter-Benutzeroberflaeche des Podcast-Transkript-Exporters."""

from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

from .exporters import export_transcript, format_clock, render_txt, safe_filename
from .importers import TranscriptImportError
from .models import Transcript
from .online import NetworkFetchError, RemoteUrl, RemoteUrlError
from .online_service import OnlineImportService
from .preferences import (
    MAX_FONT_SIZE,
    MIN_FONT_SIZE,
    Preferences,
    VALID_THEMES,
    load_preferences,
    save_preferences,
)
from .rss_transcripts import FeedDiscovery, FeedParseError, PublishedTranscript, parse_podcast_feed
from .service import TranscriptService
from .sources import ExampleTranscriptSource
from .spotify_client import SpotifyTranscriptClient, SpotifyTranscriptError, validate_sp_dc
from .url_validation import EpisodeUrlError, parse_episode_url
from .youtube_client import (
    YouTubeTranscriptClient,
    YouTubeTranscriptError,
    is_youtube_host,
    parse_youtube_url,
)


EXAMPLE_URL = "https://open.spotify.com/episode/6jJ5d9puZD5hMG6T2PsmJz"

YOUTUBE_LANGUAGE_OPTIONS = (
    ("Automatisch (Deutsch bevorzugt)", "auto"),
    ("Deutsch", "de"),
    ("Englisch", "en"),
    ("Französisch", "fr"),
    ("Spanisch", "es"),
    ("Italienisch", "it"),
    ("Niederländisch", "nl"),
    ("Polnisch", "pl"),
    ("Portugiesisch", "pt"),
    ("Türkisch", "tr"),
)
YOUTUBE_LANGUAGE_BY_LABEL = dict(YOUTUBE_LANGUAGE_OPTIONS)
YOUTUBE_LANGUAGE_BY_CODE = {code: label for label, code in YOUTUBE_LANGUAGE_OPTIONS}

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "window": "#F4F6F8",
        "card": "#FFFFFF",
        "text": "#17202A",
        "body": "#27313D",
        "muted": "#637083",
        "border": "#DCE2E8",
        "input": "#FFFFFF",
        "input_disabled": "#EEF1F4",
        "preview": "#FBFCFD",
        "button": "#E9EDF2",
        "button_hover": "#DCE3EA",
        "primary": "#2367D1",
        "primary_hover": "#1854B0",
        "primary_disabled": "#9BB6DE",
        "selection": "#B8D8FF",
        "match": "#FFF0A8",
        "match_active": "#FFC857",
        "spotify_bg": "#DCF7E7",
        "spotify_fg": "#087A3E",
        "youtube_bg": "#FDE5E5",
        "youtube_fg": "#B42318",
        "unknown_bg": "#E9EDF2",
        "unknown_fg": "#526071",
        "trough": "#E2E7EC",
    },
    "dark": {
        "window": "#111827",
        "card": "#1F2937",
        "text": "#F3F4F6",
        "body": "#E5E7EB",
        "muted": "#AAB4C3",
        "border": "#3A4658",
        "input": "#111827",
        "input_disabled": "#283343",
        "preview": "#151D2B",
        "button": "#2B3749",
        "button_hover": "#3A4960",
        "primary": "#3B82F6",
        "primary_hover": "#2563EB",
        "primary_disabled": "#415B80",
        "selection": "#315D8C",
        "match": "#665310",
        "match_active": "#A66E00",
        "spotify_bg": "#123C2B",
        "spotify_fg": "#74E0A3",
        "youtube_bg": "#4A1C1C",
        "youtube_fg": "#FF9A9A",
        "unknown_bg": "#303B4C",
        "unknown_fg": "#D4DCE8",
        "trough": "#111827",
    },
}


def _settings_path() -> Path:
    """Legt die Einstellung neben die jeweils gestartete App-Datei."""

    return Path(sys.argv[0]).resolve().parent / "settings.json"


class TranscriptChoiceDialog(simpledialog.Dialog):
    """Laesst den Nutzer einen veroeffentlichten RSS-Verweis auswaehlen."""

    def __init__(self, parent: tk.Misc, discovery: FeedDiscovery) -> None:
        self.discovery = discovery
        self.result: PublishedTranscript | None = None
        self.tree: ttk.Treeview
        super().__init__(parent, title="Veröffentlichtes Transkript auswählen")

    def body(self, master: tk.Misc):  # noqa: ANN201
        ttk.Label(
            master,
            text=(
                f"Podcast: {self.discovery.podcast_title}\n"
                "Wählen Sie eine Episode und ein veröffentlichtes Format aus."
            ),
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        frame = ttk.Frame(master)
        frame.grid(row=1, column=0, sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            frame,
            columns=("episode", "format", "language", "host"),
            show="headings",
            height=11,
            selectmode="browse",
        )
        headings = {
            "episode": "Episode",
            "format": "Format",
            "language": "Sprache",
            "host": "Quelle",
        }
        widths = {"episode": 330, "format": 110, "language": 80, "host": 220}
        for column, heading in headings.items():
            self.tree.heading(column, text=heading)
            self.tree.column(column, width=widths[column], minwidth=60)
        for index, option in enumerate(self.discovery.transcripts):
            host = option.url.split("/", 3)[2]
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    option.episode_title,
                    option.media_type,
                    option.language or "–",
                    host,
                ),
            )
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _event: self.ok())
        if self.discovery.transcripts:
            self.tree.selection_set("0")
            self.tree.focus("0")

        if self.discovery.skipped_count:
            ttk.Label(
                master,
                text=(
                    f"{self.discovery.skipped_count} nicht unterstützte oder unsichere "
                    "Verweise wurden ausgelassen."
                ),
            ).grid(row=2, column=0, sticky="w", pady=(8, 0))
        return self.tree

    def validate(self) -> bool:
        if self.tree.selection():
            return True
        messagebox.showwarning(
            "Keine Auswahl",
            "Bitte zuerst ein Transkript auswählen.",
            parent=self,
        )
        return False

    def apply(self) -> None:
        selected = self.tree.selection()[0]
        self.result = self.discovery.transcripts[int(selected)]


class ExportCompleteDialog(simpledialog.Dialog):
    """Bietet nach einem Export direkte, verständliche Folgeaktionen an."""

    def __init__(self, parent: tk.Misc, saved: Path) -> None:
        self.saved = saved
        self.result: str | None = None
        super().__init__(parent, title="Export abgeschlossen")

    def body(self, master: tk.Misc):  # noqa: ANN201
        ttk.Label(
            master,
            text="Das Transkript wurde erfolgreich gespeichert.",
            font=("Segoe UI", 11, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            master,
            text=str(self.saved),
            wraplength=560,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))
        return None

    def buttonbox(self) -> None:
        box = ttk.Frame(self)
        ttk.Button(
            box,
            text="Datei öffnen",
            command=lambda: self._choose("file"),
            style="Primary.TButton",
        ).pack(side="left")
        ttk.Button(
            box,
            text="Ordner öffnen",
            command=lambda: self._choose("folder"),
            style="Action.TButton",
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            box,
            text="Schließen",
            command=self.cancel,
            style="Action.TButton",
        ).pack(side="left", padx=(8, 0))
        box.pack(padx=12, pady=(8, 12))
        self.bind("<Escape>", self.cancel)

    def _choose(self, choice: str) -> None:
        self.result = choice
        self.cancel()


class TranscriptApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=(24, 20), style="App.TFrame")
        self.master = master
        self.service = TranscriptService(ExampleTranscriptSource())
        self.online_service = OnlineImportService()
        self.spotify_client = SpotifyTranscriptClient()
        self.youtube_client = YouTubeTranscriptClient()
        self.spotify_cookie: str | None = None
        self.transcript: Transcript | None = None
        self.online_buttons: list[ttk.Button] = []
        self.search_match_index = 0
        self.preferences_path = _settings_path()
        preferences = load_preferences(self.preferences_path)

        self.url_var = tk.StringVar(value=EXAMPLE_URL)
        self.format_var = tk.StringVar(value="TXT")
        self.timestamps_var = tk.BooleanVar(value=False)
        self.advanced_open_var = tk.BooleanVar(value=False)
        self.search_var = tk.StringVar()
        self.theme_var = tk.StringVar(value=preferences.theme)
        self.theme_button_var = tk.StringVar()
        self.font_size_var = tk.IntVar(value=preferences.font_size)
        self.font_size_label_var = tk.StringVar(value=f"{preferences.font_size * 10} %")
        self.youtube_language_var = tk.StringVar(
            value=YOUTUBE_LANGUAGE_BY_CODE.get(
                preferences.youtube_language,
                YOUTUBE_LANGUAGE_BY_CODE["auto"],
            )
        )
        self.last_export_directory = preferences.export_directory
        self.source_var = tk.StringVar(value="Spotify")
        self.transcript_title_var = tk.StringVar(value="Noch kein Transkript geladen")
        self.transcript_meta_var = tk.StringVar(
            value="Fügen Sie oben einen Spotify- oder YouTube-Link ein."
        )
        self.search_result_var = tk.StringVar(value="")
        self.spotify_login_var = tk.StringVar(
            value="Spotify: noch nicht angemeldet (Cookie wird nicht gespeichert)."
        )
        self.status_var = tk.StringVar(
            value="Bereit für einen Spotify- oder YouTube-Link."
        )

        self._configure_window()
        self._build_widgets()
        self._apply_theme(persist=False)
        self.url_var.trace_add("write", self._on_url_changed)
        self.search_var.trace_add("write", self._on_search_changed)
        self._on_url_changed()

    def _configure_window(self) -> None:
        self.master.title("Podcast-Transkript-Exporter – Spotify und YouTube")
        self.master.geometry("1080x780")
        self.master.minsize(820, 620)
        self.master.option_add("*Font", ("Segoe UI", 10))
        self.pack(fill="both", expand=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.style = ttk.Style(self.master)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self._configure_theme_styles(THEMES[self.theme_var.get()])

    def _configure_theme_styles(self, colors: dict[str, str]) -> None:
        style = self.style
        style.configure("App.TFrame", background=colors["window"])
        style.configure("Card.TFrame", background=colors["card"])
        style.configure(
            "Card.TLabel", background=colors["card"], foreground=colors["body"]
        )
        style.configure(
            "Title.TLabel",
            background=colors["window"],
            foreground=colors["text"],
            font=("Segoe UI", 21, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=colors["window"],
            foreground=colors["muted"],
            font=("Segoe UI", 10),
        )
        style.configure(
            "SectionTitle.TLabel",
            background=colors["card"],
            foreground=colors["text"],
            font=("Segoe UI", 12, "bold"),
        )
        style.configure(
            "TranscriptTitle.TLabel",
            background=colors["card"],
            foreground=colors["text"],
            font=("Segoe UI", 14, "bold"),
        )
        style.configure(
            "Muted.Card.TLabel",
            background=colors["card"],
            foreground=colors["muted"],
        )
        style.configure(
            "Primary.TButton",
            background=colors["primary"],
            foreground="#FFFFFF",
            bordercolor=colors["primary"],
            lightcolor=colors["primary"],
            darkcolor=colors["primary"],
            font=("Segoe UI", 10, "bold"),
            padding=(16, 9),
        )
        style.map(
            "Primary.TButton",
            background=[
                ("disabled", colors["primary_disabled"]),
                ("active", colors["primary_hover"]),
                ("pressed", colors["primary_hover"]),
            ],
            foreground=[("disabled", "#E5E7EB"), ("!disabled", "#FFFFFF")],
        )
        for button_style, padding in (("Action.TButton", (12, 7)), ("Theme.TButton", (12, 7))):
            style.configure(
                button_style,
                background=colors["button"],
                foreground=colors["body"],
                bordercolor=colors["border"],
                lightcolor=colors["button"],
                darkcolor=colors["button"],
                padding=padding,
            )
            style.map(
                button_style,
                background=[
                    ("active", colors["button_hover"]),
                    ("pressed", colors["button_hover"]),
                ],
                foreground=[("disabled", colors["muted"]), ("!disabled", colors["body"])],
            )
        style.configure(
            "TButton",
            background=colors["button"],
            foreground=colors["body"],
            bordercolor=colors["border"],
        )
        style.map(
            "TButton",
            background=[("active", colors["button_hover"]), ("pressed", colors["button_hover"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["body"])],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["input"],
            foreground=colors["body"],
            insertcolor=colors["body"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
        )
        style.map(
            "TEntry",
            fieldbackground=[("disabled", colors["input_disabled"]), ("!disabled", colors["input"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["body"])],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["input"],
            background=colors["button"],
            foreground=colors["body"],
            arrowcolor=colors["body"],
            bordercolor=colors["border"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["input"])],
            foreground=[("readonly", colors["body"])],
            selectbackground=[("readonly", colors["input"])],
            selectforeground=[("readonly", colors["body"])],
        )
        style.configure(
            "TCheckbutton",
            background=colors["card"],
            foreground=colors["body"],
            indicatorbackground=colors["input"],
            indicatorforeground=colors["primary"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", colors["card"])],
            foreground=[("active", colors["body"])],
            indicatorbackground=[("selected", colors["primary"]), ("!selected", colors["input"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=colors["button"],
            troughcolor=colors["trough"],
            bordercolor=colors["border"],
            arrowcolor=colors["body"],
        )
        style.configure(
            "Horizontal.TProgressbar",
            background=colors["primary"],
            troughcolor=colors["trough"],
            bordercolor=colors["window"],
        )
        style.configure(
            "Source.Spotify.TLabel",
            background=colors["spotify_bg"],
            foreground=colors["spotify_fg"],
            font=("Segoe UI", 9, "bold"),
            padding=(9, 4),
        )
        style.configure(
            "Source.YouTube.TLabel",
            background=colors["youtube_bg"],
            foreground=colors["youtube_fg"],
            font=("Segoe UI", 9, "bold"),
            padding=(9, 4),
        )
        style.configure(
            "Source.Unknown.TLabel",
            background=colors["unknown_bg"],
            foreground=colors["unknown_fg"],
            font=("Segoe UI", 9, "bold"),
            padding=(9, 4),
        )
        style.configure(
            "Status.TLabel",
            background=colors["window"],
            foreground=colors["muted"],
        )
        style.configure("TFrame", background=colors["card"])
        style.configure("TLabel", background=colors["card"], foreground=colors["body"])
        style.configure("Treeview", background=colors["input"], fieldbackground=colors["input"], foreground=colors["body"])
        style.configure("Treeview.Heading", background=colors["button"], foreground=colors["body"])

    def _apply_theme(self, theme: str | None = None, *, persist: bool) -> bool:
        selected = theme or self.theme_var.get()
        if selected not in VALID_THEMES:
            selected = "light"
        self.theme_var.set(selected)
        colors = THEMES[selected]
        self._configure_theme_styles(colors)
        self.master.configure(background=colors["window"])
        self.master.option_add("*TCombobox*Listbox.background", colors["input"], "interactive")
        self.master.option_add("*TCombobox*Listbox.foreground", colors["body"], "interactive")
        self.master.option_add("*TCombobox*Listbox.selectBackground", colors["selection"], "interactive")
        self.master.option_add("*TCombobox*Listbox.selectForeground", colors["body"], "interactive")
        self.theme_button_var.set("☀  Hell" if selected == "dark" else "☾  Dunkel")

        if hasattr(self, "input_card"):
            self.input_card.configure(
                background=colors["card"], highlightbackground=colors["border"]
            )
            self.preview_card.configure(
                background=colors["card"], highlightbackground=colors["border"]
            )
            self.preview.configure(
                background=colors["preview"],
                foreground=colors["body"],
                insertbackground=colors["body"],
                selectbackground=colors["selection"],
                selectforeground=colors["body"],
                highlightbackground=colors["border"],
                highlightcolor=colors["primary"],
                font=("Segoe UI", self.font_size_var.get()),
            )
            self.preview.tag_configure("search_match", background=colors["match"])
            self.preview.tag_configure("search_active", background=colors["match_active"])

        if persist:
            if not self._save_current_preferences():
                return False
        return True

    def toggle_theme(self) -> None:
        selected = "dark" if self.theme_var.get() == "light" else "light"
        if self._apply_theme(selected, persist=True):
            label = "Dunkelmodus" if selected == "dark" else "Hellmodus"
            self.status_var.set(f"{label} aktiviert und für den nächsten Start gespeichert.")

    def _current_preferences(self) -> Preferences:
        return Preferences(
            theme=self.theme_var.get(),
            font_size=self.font_size_var.get(),
            youtube_language=YOUTUBE_LANGUAGE_BY_LABEL.get(
                self.youtube_language_var.get(), "auto"
            ),
            export_directory=self.last_export_directory,
        )

    def _save_current_preferences(self) -> bool:
        try:
            save_preferences(self.preferences_path, self._current_preferences())
        except (OSError, ValueError) as exc:
            self.status_var.set(f"Einstellung aktiv, aber nicht gespeichert: {exc}")
            return False
        return True

    def _selected_youtube_language(self) -> str | None:
        code = YOUTUBE_LANGUAGE_BY_LABEL.get(self.youtube_language_var.get(), "auto")
        return None if code == "auto" else code

    def _on_youtube_language_changed(self, _event: object | None = None) -> None:
        if self._save_current_preferences():
            selected = self.youtube_language_var.get()
            self.status_var.set(f"YouTube-Sprachauswahl gespeichert: {selected}.")

    def adjust_font_size(self, difference: int, *, persist: bool = True) -> None:
        selected = min(
            MAX_FONT_SIZE,
            max(MIN_FONT_SIZE, self.font_size_var.get() + difference),
        )
        self.font_size_var.set(selected)
        self.font_size_label_var.set(f"{selected * 10} %")
        self.preview.configure(font=("Segoe UI", selected))
        if not persist:
            return
        if self._save_current_preferences():
            self.status_var.set(
                f"Transkript-Schriftgröße auf {selected * 10} % eingestellt."
            )

    def _build_widgets(self) -> None:
        header = ttk.Frame(self, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="Podcast-Transkript-Exporter",
            style="Title.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Vorhandene Transkripte abrufen, lesen und als TXT, Markdown oder SRT speichern.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.theme_button = ttk.Button(
            header,
            textvariable=self.theme_button_var,
            command=self.toggle_theme,
            style="Theme.TButton",
        )
        self.theme_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))

        self.input_card = tk.Frame(
            self,
            background="#FFFFFF",
            highlightbackground="#DCE2E8",
            highlightthickness=1,
        )
        self.input_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        input_frame = ttk.Frame(self.input_card, padding=16, style="Card.TFrame")
        input_frame.pack(fill="both", expand=True)
        input_frame.columnconfigure(0, weight=1)
        ttk.Label(
            input_frame,
            text="SPOTIFY- ODER YOUTUBE-LINK",
            style="SectionTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        self.source_badge = ttk.Label(
            input_frame,
            textvariable=self.source_var,
            style="Source.Unknown.TLabel",
        )
        self.source_badge.grid(row=0, column=1, sticky="e")
        self.url_entry = ttk.Entry(input_frame, textvariable=self.url_var)
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(0, 10), pady=(10, 0), ipady=5)
        self.url_entry.bind("<Return>", lambda _event: self.fetch_transcript())
        self.fetch_button = ttk.Button(
            input_frame,
            text="Transkript abrufen",
            command=self.fetch_transcript,
            style="Primary.TButton",
        )
        self.fetch_button.grid(row=1, column=1, pady=(10, 0))
        self.online_buttons.append(self.fetch_button)

        self.source_help_var = tk.StringVar()
        ttk.Label(
            input_frame,
            textvariable=self.source_help_var,
            style="Muted.Card.TLabel",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(7, 0))

        self.spotify_login_frame = ttk.Frame(input_frame, style="Card.TFrame")
        self.spotify_login_frame.grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )
        ttk.Label(
            self.spotify_login_frame,
            textvariable=self.spotify_login_var,
            style="Card.TLabel",
        ).pack(side="left")
        ttk.Button(
            self.spotify_login_frame,
            text="Spotify-Anmeldung …",
            command=self.request_spotify_login,
            style="Action.TButton",
        ).pack(side="left", padx=(12, 0))
        ttk.Button(
            self.spotify_login_frame,
            text="Vergessen",
            command=self.forget_spotify_login,
            style="Action.TButton",
        ).pack(side="left", padx=(6, 0))
        ttk.Button(
            self.spotify_login_frame,
            text="Browser öffnen",
            command=lambda: webbrowser.open("https://open.spotify.com/"),
            style="Action.TButton",
        ).pack(side="left", padx=(6, 0))

        self.youtube_options_frame = ttk.Frame(input_frame, style="Card.TFrame")
        self.youtube_options_frame.grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )
        ttk.Label(
            self.youtube_options_frame,
            text="Transkriptsprache:",
            style="Card.TLabel",
        ).pack(side="left")
        self.youtube_language_combo = ttk.Combobox(
            self.youtube_options_frame,
            textvariable=self.youtube_language_var,
            values=tuple(label for label, _code in YOUTUBE_LANGUAGE_OPTIONS),
            state="readonly",
            width=31,
        )
        self.youtube_language_combo.pack(side="left", padx=(8, 0))
        self.youtube_language_combo.bind(
            "<<ComboboxSelected>>", self._on_youtube_language_changed
        )
        self.youtube_options_frame.grid_remove()

        self.advanced_button = ttk.Button(
            input_frame,
            text="Weitere Importmöglichkeiten  ▸",
            command=self.toggle_advanced_imports,
        )
        self.advanced_button.grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

        self.advanced_frame = ttk.Frame(input_frame, style="Card.TFrame")
        self.advanced_frame.grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0)
        )
        ttk.Button(
            self.advanced_frame,
            text="Lokale Datei öffnen …",
            command=self.import_local_file,
            style="Action.TButton",
        ).pack(side="left")
        rss_button = ttk.Button(
            self.advanced_frame,
            text="RSS-Feed prüfen …",
            command=self.request_rss_import,
            style="Action.TButton",
        )
        rss_button.pack(side="left", padx=(8, 0))
        direct_button = ttk.Button(
            self.advanced_frame,
            text="Direkten Transkriptlink öffnen …",
            command=self.request_direct_import,
            style="Action.TButton",
        )
        direct_button.pack(side="left", padx=(8, 0))
        self.online_buttons.extend((rss_button, direct_button))
        self.advanced_frame.grid_remove()

        self.preview_card = tk.Frame(
            self,
            background="#FFFFFF",
            highlightbackground="#DCE2E8",
            highlightthickness=1,
        )
        self.preview_card.grid(row=2, column=0, sticky="nsew")
        self.preview_card.grid_columnconfigure(0, weight=1)
        self.preview_card.grid_rowconfigure(0, weight=1)
        text_frame = ttk.Frame(self.preview_card, padding=16, style="Card.TFrame")
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(2, weight=1)

        summary = ttk.Frame(text_frame, style="Card.TFrame")
        summary.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        summary.columnconfigure(0, weight=1)
        ttk.Label(
            summary,
            textvariable=self.transcript_title_var,
            style="TranscriptTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            summary,
            textvariable=self.transcript_meta_var,
            style="Muted.Card.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.copy_button = ttk.Button(
            summary,
            text="Text kopieren",
            command=self.copy_current_transcript,
            state="disabled",
            style="Action.TButton",
        )
        self.copy_button.grid(row=0, column=1, rowspan=2, padx=(12, 0))

        search_frame = ttk.Frame(text_frame, style="Card.TFrame")
        search_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        search_frame.columnconfigure(0, weight=1)
        self.search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var,
            state="disabled",
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", ipady=3)
        self.search_entry.bind("<Return>", lambda _event: self.find_next_match())
        ttk.Label(
            search_frame,
            textvariable=self.search_result_var,
            style="Muted.Card.TLabel",
            width=14,
            anchor="center",
        ).grid(row=0, column=1, padx=(8, 0))
        self.search_next_button = ttk.Button(
            search_frame,
            text="Nächster Treffer",
            command=self.find_next_match,
            state="disabled",
        )
        self.search_next_button.grid(row=0, column=2)
        ttk.Label(
            search_frame,
            text="Schrift:",
            style="Muted.Card.TLabel",
        ).grid(row=0, column=3, padx=(16, 5))
        ttk.Button(
            search_frame,
            text="A−",
            width=3,
            command=lambda: self.adjust_font_size(-1),
            style="Action.TButton",
        ).grid(row=0, column=4)
        ttk.Label(
            search_frame,
            textvariable=self.font_size_label_var,
            width=6,
            anchor="center",
            style="Muted.Card.TLabel",
        ).grid(row=0, column=5)
        ttk.Button(
            search_frame,
            text="A+",
            width=3,
            command=lambda: self.adjust_font_size(1),
            style="Action.TButton",
        ).grid(row=0, column=6)

        self.preview = tk.Text(
            text_frame,
            wrap="word",
            padx=16,
            pady=14,
            state="disabled",
            undo=False,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#E2E7EC",
            background="#FBFCFD",
            foreground="#202936",
            selectbackground="#B8D8FF",
            font=("Segoe UI", 10),
            spacing1=2,
            spacing3=5,
        )
        scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=scroll.set)
        self.preview.tag_configure("search_match", background="#FFF0A8")
        self.preview.tag_configure("search_active", background="#FFC857")
        self.preview.grid(row=2, column=0, sticky="nsew")
        scroll.grid(row=2, column=1, sticky="ns")

        controls = ttk.Frame(text_frame, style="Card.TFrame")
        controls.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(controls, text="Exportformat:", style="Card.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            controls,
            textvariable=self.format_var,
            values=("TXT", "Markdown", "SRT"),
            state="readonly",
            width=12,
        ).grid(row=0, column=1, padx=(6, 18))
        ttk.Checkbutton(
            controls,
            text="Zeitstempel in TXT/Markdown",
            variable=self.timestamps_var,
            command=self.refresh_preview,
        ).grid(row=0, column=2, sticky="w")
        ttk.Label(
            controls,
            text="SRT enthält immer Zeitcodes.",
            style="Muted.Card.TLabel",
        ).grid(
            row=0, column=3, padx=(8, 0), sticky="w"
        )
        controls.columnconfigure(3, weight=1)
        self.export_button = ttk.Button(
            controls,
            text="Exportieren …",
            command=self.export_current,
            state="disabled",
            style="Primary.TButton",
        )
        self.export_button.grid(row=0, column=4, padx=(12, 0))

        footer = ttk.Frame(self, style="App.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=120)
        self.progress.grid(row=0, column=0, padx=(0, 10))
        self.progress.grid_remove()
        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0, column=1, sticky="w"
        )

    def _on_url_changed(self, *_args: object) -> None:
        value = self.url_var.get().strip()
        if is_youtube_host(value):
            self.source_var.set("YouTube")
            self.source_badge.configure(style="Source.YouTube.TLabel")
            self.source_help_var.set(
                "Keine Anmeldung nötig · Die gewünschte Untertitelsprache kann ausgewählt werden."
            )
            self.spotify_login_frame.grid_remove()
            self.youtube_options_frame.grid()
            return
        try:
            parse_episode_url(value)
        except EpisodeUrlError:
            self.source_var.set("Link einfügen" if not value else "Nicht erkannt")
            self.source_badge.configure(style="Source.Unknown.TLabel")
            self.source_help_var.set(
                "Unterstützt werden Spotify-Episodenlinks sowie YouTube- und youtu.be-Links."
            )
            self.spotify_login_frame.grid_remove()
            self.youtube_options_frame.grid_remove()
            return
        self.source_var.set("Spotify")
        self.source_badge.configure(style="Source.Spotify.TLabel")
        self.source_help_var.set(
            "Spotify benötigt einmal pro App-Sitzung den manuell eingegebenen sp_dc-Wert."
        )
        self.youtube_options_frame.grid_remove()
        self.spotify_login_frame.grid()

    def toggle_advanced_imports(self) -> None:
        opened = not self.advanced_open_var.get()
        self.advanced_open_var.set(opened)
        if opened:
            self.advanced_frame.grid()
            self.advanced_button.configure(text="Weitere Importmöglichkeiten  ▾")
        else:
            self.advanced_frame.grid_remove()
            self.advanced_button.configure(text="Weitere Importmöglichkeiten  ▸")

    def fetch_transcript(self) -> None:
        entered_url = self.url_var.get().strip()
        if is_youtube_host(entered_url):
            try:
                parse_youtube_url(entered_url)
            except YouTubeTranscriptError as exc:
                messagebox.showerror("Link nicht verwendbar", str(exc), parent=self.master)
                return
            preferred_language = self._selected_youtube_language()
            self._run_online_task(
                lambda: self.youtube_client.fetch(
                    entered_url,
                    preferred_language=preferred_language,
                ),
                self._load_youtube_transcript,
                "YouTube-Transkript wird abgerufen …",
            )
            return

        try:
            # Zuerst rein lokal prüfen; damit wird kein Cookie an eine falsche URL gesendet.
            from .url_validation import parse_episode_url

            parse_episode_url(entered_url)
        except EpisodeUrlError as exc:
            messagebox.showerror(
                "Link nicht verwendbar",
                f"{exc}\n\nErlaubt sind Spotify-Episodenlinks sowie YouTube- und youtu.be-Links.",
                parent=self.master,
            )
            return

        if self.spotify_cookie is None and not self.request_spotify_login():
            self.status_var.set("Abruf abgebrochen – keine Spotify-Anmeldung eingegeben.")
            return
        cookie = self.spotify_cookie
        if cookie is None:
            return
        self._run_online_task(
            lambda: self.spotify_client.fetch(entered_url, cookie),
            self._load_spotify_transcript,
            "Spotify-Transkript wird abgerufen …",
        )

    def request_spotify_login(self) -> bool:
        messagebox.showinfo(
            "Spotify-Anmeldung vorbereiten",
            (
                "1. Öffnen Sie Spotify im Browser und melden Sie sich an.\n"
                "2. Drücken Sie F12.\n"
                "3. Chrome/Edge: Anwendung (Application) > Speicher > Cookies > "
                "https://open.spotify.com\n"
                "4. Suchen Sie sp_dc und kopieren Sie ausschließlich dessen Wert.\n\n"
                "Der Wert ist ein Zugangsschlüssel. Geben Sie ihn nur im nächsten "
                "Fenster dieser lokalen App ein – niemals in einen Chat."
            ),
            parent=self.master,
        )
        value = simpledialog.askstring(
            "Spotify-Cookie eingeben",
            "Wert des Cookies sp_dc:",
            show="●",
            parent=self.master,
        )
        if value is None:
            return False
        try:
            self.spotify_cookie = validate_sp_dc(value)
        except SpotifyTranscriptError as exc:
            messagebox.showerror("Cookie nicht verwendbar", str(exc), parent=self.master)
            return False
        self.spotify_client.clear_session()
        self.spotify_login_var.set(
            "Spotify: Cookie für diese App-Sitzung vorhanden; nicht auf Festplatte gespeichert."
        )
        self.status_var.set("Spotify-Anmeldung wurde lokal übernommen.")
        return True

    def forget_spotify_login(self) -> None:
        self.spotify_cookie = None
        self.spotify_client.clear_session()
        self.spotify_login_var.set(
            "Spotify: noch nicht angemeldet (Cookie wird nicht gespeichert)."
        )
        self.status_var.set("Spotify-Anmeldung aus dem Arbeitsspeicher entfernt.")

    def _load_spotify_transcript(self, transcript: Transcript) -> None:
        self._load_online_transcript(transcript)
        self.status_var.set(
            f"Spotify-Transkript geladen: {transcript.title} – "
            f"{len(transcript.segments)} Abschnitte."
        )

    def _load_youtube_transcript(self, transcript: Transcript) -> None:
        self._load_online_transcript(transcript)
        language = transcript.language or "unbekannte Sprache"
        self.status_var.set(
            f"YouTube-Transkript geladen: Sprache {language}, "
            f"{len(transcript.segments)} Abschnitte."
        )

    def import_local_file(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self.master,
            title="Lokale Transkriptdatei öffnen",
            filetypes=[
                ("Unterstützte Transkripte", "*.vtt *.srt *.txt"),
                ("WebVTT", "*.vtt"),
                ("SRT-Untertitel", "*.srt"),
                ("Textdatei", "*.txt"),
                ("Alle Dateien", "*.*"),
            ],
        )
        if not selected:
            return
        try:
            self.transcript = self.service.import_file(Path(selected))
        except (TranscriptImportError, OSError, ValueError) as exc:
            self.transcript = None
            self.export_button.configure(state="disabled")
            self._set_preview("")
            self.status_var.set("Die lokale Datei konnte nicht importiert werden.")
            messagebox.showerror("Import fehlgeschlagen", str(exc), parent=self.master)
            return

        self.export_button.configure(state="normal")
        self.refresh_preview()
        timing = (
            "Zeitcodes übernommen"
            if self.transcript.timing_origin == "provided"
            else "Zeitcodes geschätzt"
        )
        self.status_var.set(
            f"Lokal geladen: {Path(selected).name} – "
            f"{len(self.transcript.segments)} Abschnitte, {timing}."
        )

    def request_rss_import(self) -> None:
        value = simpledialog.askstring(
            "Öffentlichen RSS-Feed prüfen",
            (
                "Fügen Sie die HTTPS-Adresse des offiziellen Podcast-RSS-Feeds ein.\n\n"
                "Die Adresse wird zunächst nur lokal geprüft."
            ),
            parent=self.master,
        )
        if value is None:
            return
        remote = self._prepare_remote_url(value)
        if remote is None or not self._confirm_download(remote, "RSS-Feed", "höchstens 2 MB"):
            return

        self._run_online_task(
            lambda: self.online_service.discover_feed(remote.url),
            self._on_feed_discovered,
            "Der bestätigte RSS-Feed wird geprüft …",
        )

    def request_direct_import(self) -> None:
        value = simpledialog.askstring(
            "Direkten Transkriptlink öffnen",
            (
                "Fügen Sie einen vom Herausgeber veröffentlichten HTTPS-Link zu einer "
                "VTT-, SRT- oder TXT-Datei ein.\n\n"
                "Die Adresse wird zunächst nur lokal geprüft."
            ),
            parent=self.master,
        )
        if value is None:
            return
        remote = self._prepare_remote_url(value)
        if remote is None or not self._confirm_download(
            remote,
            "Transkriptdatei",
            "höchstens 10 MB",
        ):
            return

        self._run_online_task(
            lambda: self.online_service.download_direct(remote.url),
            self._load_online_transcript,
            "Die bestätigte Transkriptdatei wird geladen …",
        )

    def _prepare_remote_url(self, value: str) -> RemoteUrl | None:
        try:
            return self.online_service.prepare_url(value)
        except RemoteUrlError as exc:
            messagebox.showerror("Adresse nicht zugelassen", str(exc), parent=self.master)
            self.status_var.set("Die Online-Adresse wurde aus Sicherheitsgründen abgelehnt.")
            return None

    def _confirm_download(self, remote: RemoteUrl, purpose: str, limit: str) -> bool:
        approved = messagebox.askokcancel(
            "Netzwerkzugriff bestätigen",
            (
                f"Zweck: {purpose} laden\n"
                f"Ziel-Domain: {remote.host}\n"
                f"Adresse: {remote.url}\n"
                f"Datenlimit: {limit}\n\n"
                "Gesendet werden eine HTTPS-GET-Anfrage, Ihre IP-Adresse und minimale "
                "Standardheader mit dem App-Namen und den akzeptierten Dateitypen. "
                "Der Zielserver kann diese Anfrage protokollieren.\n\n"
                "Nicht gesendet werden Spotify-Link, lokale Dateien, Cookies, Passwörter "
                "oder andere Zugangsdaten. Weiterleitungen zu einer anderen Domain werden "
                "blockiert.\n\n"
                "Bitte nur fortfahren, wenn der Herausgeber diesen Link veröffentlicht hat "
                "und Sie das Transkript verwenden dürfen."
            ),
            parent=self.master,
        )
        if not approved:
            self.status_var.set("Online-Abruf abgebrochen – es wurden keine Daten gesendet.")
        return approved

    def _on_feed_discovered(self, discovery: FeedDiscovery) -> None:
        if not discovery.transcripts:
            messagebox.showinfo(
                "Kein unterstütztes Transkript",
                (
                    "Der Feed enthält keinen verwendbaren podcast:transcript-Verweis "
                    "auf VTT, SRT oder Klartext."
                ),
                parent=self.master,
            )
            self.status_var.set("Im bestätigten RSS-Feed wurde kein passendes Transkript gefunden.")
            return

        dialog = TranscriptChoiceDialog(self.master, discovery)
        option = dialog.result
        if option is None:
            self.status_var.set("Keine Episode ausgewählt – kein weiterer Netzwerkzugriff.")
            return
        remote = self._prepare_remote_url(option.url)
        if remote is None or not self._confirm_download(
            remote,
            f"Transkript „{option.episode_title}“",
            "höchstens 10 MB",
        ):
            return

        self._run_online_task(
            lambda: self.online_service.download_published(option),
            self._load_online_transcript,
            "Das ausgewählte Transkript wird geladen …",
        )

    def _load_online_transcript(self, transcript: Transcript) -> None:
        self.transcript = transcript
        self.export_button.configure(state="normal")
        self.refresh_preview()
        self.status_var.set(
            f"Online-Transkript geladen: {transcript.title} – "
            f"{len(transcript.segments)} Abschnitte."
        )

    def _set_online_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in self.online_buttons:
            button.configure(state=state)
        self.youtube_language_combo.configure(state="disabled" if busy else "readonly")
        if busy:
            self.progress.grid()
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _run_online_task(
        self,
        task: Callable[[], Any],
        on_success: Callable[[Any], None],
        status: str,
    ) -> None:
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)
        self._set_online_busy(True)
        self.status_var.set(status)

        def worker() -> None:
            try:
                result_queue.put(("ok", task()))
            except (NetworkFetchError, FeedParseError, TranscriptImportError, ValueError) as exc:
                result_queue.put(("error", str(exc)))
            except Exception as exc:  # Letzte Grenze fuer den GUI-Thread.
                result_queue.put(("error", f"Unerwarteter Fehler: {exc}"))

        def poll_result() -> None:
            try:
                outcome, value = result_queue.get_nowait()
            except queue.Empty:
                self.master.after(100, poll_result)
                return
            self._set_online_busy(False)
            if outcome == "ok":
                on_success(value)
                return
            self.status_var.set("Der bestätigte Online-Abruf ist fehlgeschlagen.")
            messagebox.showerror("Online-Import fehlgeschlagen", value, parent=self.master)

        threading.Thread(target=worker, daemon=True).start()
        self.master.after(100, poll_result)

    def refresh_preview(self) -> None:
        if self.transcript is None:
            return
        content = render_txt(self.transcript, self.timestamps_var.get())
        self._set_preview(content)
        self._update_transcript_summary()
        self.copy_button.configure(state="normal")
        self.search_entry.configure(state="normal")
        self._highlight_search_matches()

    def _set_preview(self, content: str) -> None:
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", content)
        self.preview.configure(state="disabled")

    def _update_transcript_summary(self) -> None:
        if self.transcript is None:
            return
        source = self.transcript.source_url.lower()
        if "open.spotify.com" in source:
            platform = "Spotify"
        elif "youtube.com" in source or "youtu.be" in source:
            platform = "YouTube"
        elif source.startswith("file:") or ":\\" in source:
            platform = "Lokale Datei"
        else:
            platform = "Online-Import"
        language = self.transcript.language or "Sprache unbekannt"
        duration = format_clock(max(segment.end_ms for segment in self.transcript.segments))
        timing = (
            "echte Zeitcodes"
            if self.transcript.timing_origin == "provided"
            else "geschätzte Zeitcodes"
        )
        self.transcript_title_var.set(self.transcript.title)
        self.transcript_meta_var.set(
            f"{platform}  ·  {language}  ·  {len(self.transcript.segments)} Abschnitte"
            f"  ·  {duration}  ·  {timing}"
        )

    def copy_current_transcript(self) -> None:
        if self.transcript is None:
            return
        content = render_txt(self.transcript, self.timestamps_var.get())
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(content)
        except tk.TclError as exc:
            messagebox.showerror(
                "Kopieren fehlgeschlagen",
                f"Das Transkript konnte nicht kopiert werden: {exc}",
                parent=self.master,
            )
            return
        self.status_var.set("Transkript wurde in die Zwischenablage kopiert.")

    def _on_search_changed(self, *_args: object) -> None:
        self.search_match_index = 0
        self._highlight_search_matches()

    def _highlight_search_matches(self) -> None:
        if not hasattr(self, "preview"):
            return
        query = self.search_var.get().strip()
        self.preview.configure(state="normal")
        self.preview.tag_remove("search_match", "1.0", "end")
        self.preview.tag_remove("search_active", "1.0", "end")
        if not query or self.transcript is None:
            self.preview.configure(state="disabled")
            self.search_result_var.set("")
            self.search_next_button.configure(state="disabled")
            return

        start = "1.0"
        count = tk.IntVar(master=self.master)
        matches = 0
        while True:
            index = self.preview.search(
                query,
                start,
                stopindex="end",
                nocase=True,
                count=count,
            )
            if not index:
                break
            length = max(1, count.get())
            end = f"{index}+{length}c"
            self.preview.tag_add("search_match", index, end)
            start = end
            matches += 1
        self.preview.configure(state="disabled")
        self.search_next_button.configure(state="normal" if matches else "disabled")
        if matches:
            self._activate_search_match(0)
        else:
            self.search_result_var.set("Kein Treffer")

    def _activate_search_match(self, requested_index: int) -> None:
        ranges = self.preview.tag_ranges("search_match")
        pairs = list(zip(ranges[0::2], ranges[1::2]))
        if not pairs:
            self.search_result_var.set("Kein Treffer")
            return
        self.search_match_index = requested_index % len(pairs)
        start, end = pairs[self.search_match_index]
        self.preview.configure(state="normal")
        self.preview.tag_remove("search_active", "1.0", "end")
        self.preview.tag_add("search_active", start, end)
        self.preview.configure(state="disabled")
        self.preview.see(start)
        self.search_result_var.set(f"{self.search_match_index + 1} von {len(pairs)}")

    def find_next_match(self) -> None:
        ranges = self.preview.tag_ranges("search_match")
        if not ranges:
            self._highlight_search_matches()
            return
        self._activate_search_match(self.search_match_index + 1)

    def export_current(self) -> None:
        if self.transcript is None:
            messagebox.showinfo(
                "Noch kein Transkript",
                "Bitte zuerst ein Transkript abrufen oder eine Datei öffnen.",
                parent=self.master,
            )
            return

        format_map = {"TXT": "txt", "Markdown": "md", "SRT": "srt"}
        file_format = format_map[self.format_var.get()]
        if file_format == "srt" and self.transcript.timing_origin == "estimated":
            proceed = messagebox.askokcancel(
                "Geschätzte SRT-Zeitcodes",
                (
                    "Die geladene TXT-Datei enthält keine echten Zeitcodes. "
                    "Die SRT-Zeiten sind deshalb nur Schätzwerte. Trotzdem exportieren?"
                ),
                parent=self.master,
            )
            if not proceed:
                return
        filetypes = {
            "txt": [("Textdatei", "*.txt")],
            "md": [("Markdown-Datei", "*.md")],
            "srt": [("SRT-Untertitel", "*.srt")],
        }
        dialog_options: dict[str, Any] = {
            "parent": self.master,
            "title": "Transkript exportieren",
            "defaultextension": f".{file_format}",
            "initialfile": safe_filename(self.transcript.title, file_format),
            "filetypes": filetypes[file_format] + [("Alle Dateien", "*.*")],
        }
        previous_directory = Path(self.last_export_directory)
        if self.last_export_directory and previous_directory.is_dir():
            dialog_options["initialdir"] = str(previous_directory)
        destination = filedialog.asksaveasfilename(
            **dialog_options,
        )
        if not destination:
            return

        try:
            saved = export_transcript(
                self.transcript,
                Path(destination),
                file_format,
                self.timestamps_var.get(),
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export fehlgeschlagen", str(exc), parent=self.master)
            return

        self.last_export_directory = str(saved.parent.resolve())
        preferences_saved = self._save_current_preferences()
        suffix = "" if preferences_saved else " (Exportordner nicht gespeichert)"
        self.status_var.set(f"Export gespeichert: {saved}{suffix}")

        action = ExportCompleteDialog(self.master, saved).result
        if action == "file":
            self._open_export_target(saved)
        elif action == "folder":
            self._open_export_target(saved.parent)

    def _open_export_target(self, target: Path) -> None:
        """Öffnet eine exportierte Datei oder ihren Ordner mit Windows."""

        try:
            if sys.platform == "win32":
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif not webbrowser.open(target.resolve().as_uri()):
                raise OSError("Es ist keine passende Standardanwendung verfügbar.")
        except (OSError, ValueError) as exc:
            messagebox.showerror(
                "Öffnen fehlgeschlagen",
                f"Windows konnte dieses Ziel nicht öffnen:\n{target}\n\n{exc}",
                parent=self.master,
            )


def main() -> None:
    root = tk.Tk()
    TranscriptApp(root)
    root.mainloop()


def self_test() -> None:
    """Initialisiert die gepackte GUI und ihre Ressourcen ohne sichtbares Fenster."""

    # Der Import bleibt ohne Netzwerkzugriff und bestaetigt, dass PyInstaller die
    # YouTube-Abhaengigkeit samt requests/defusedxml eingepackt hat.
    from youtube_transcript_api import YouTubeTranscriptApi

    YouTubeTranscriptApi()
    root = tk.Tk()
    root.withdraw()
    try:
        app = TranscriptApp(root)
        # Den Dienst direkt aufrufen: Ein Fehler soll im Build-Test sichtbar
        # werden und darf nicht in einem unsichtbaren Meldungsfenster warten.
        app.transcript = app.service.fetch_from_url(app.url_var.get())
        app.refresh_preview()
        if app.transcript is None:
            raise RuntimeError("Das Beispieltranskript wurde nicht geladen.")
        preview = app.preview.get("1.0", "end")
        if "Beispielfolge" not in preview:
            raise RuntimeError("Die GUI-Vorschau wurde nicht aufgebaut.")
        if app.transcript_title_var.get() != "Beispielfolge: Von der Idee zur sicheren App":
            raise RuntimeError("Die neue Transkript-Kopfzeile wurde nicht aktualisiert.")
        app.search_var.set("Tests")
        if not app.preview.tag_ranges("search_match"):
            raise RuntimeError("Die Transkriptsuche findet den Beispieltext nicht.")
        app.find_next_match()
        app._apply_theme("dark", persist=False)
        if app.theme_var.get() != "dark" or app.preview.cget("background") != THEMES["dark"]["preview"]:
            raise RuntimeError("Der Dunkelmodus wurde nicht vollständig angewendet.")
        app._apply_theme("light", persist=False)
        if app.theme_var.get() != "light" or app.preview.cget("background") != THEMES["light"]["preview"]:
            raise RuntimeError("Der Hellmodus wurde nicht wiederhergestellt.")
        app.font_size_var.set(10)
        app.adjust_font_size(2, persist=False)
        if app.font_size_var.get() != 12 or app.font_size_label_var.get() != "120 %":
            raise RuntimeError("Die Schriftgrößensteuerung wurde nicht angewendet.")
        app.url_var.set("https://youtu.be/dQw4w9WgXcQ")
        if (
            app.source_var.get() != "YouTube"
            or app.spotify_login_frame.grid_info()
            or not app.youtube_options_frame.grid_info()
        ):
            raise RuntimeError("Die dynamische YouTube-Ansicht wurde nicht aktiviert.")
        app.youtube_language_var.set("Französisch")
        if app._selected_youtube_language() != "fr":
            raise RuntimeError("Die YouTube-Sprachauswahl wurde nicht übernommen.")
        app.url_var.set(EXAMPLE_URL)
        if (
            app.source_var.get() != "Spotify"
            or not app.spotify_login_frame.grid_info()
            or app.youtube_options_frame.grid_info()
        ):
            raise RuntimeError("Die dynamische Spotify-Ansicht wurde nicht aktiviert.")
        app.toggle_advanced_imports()
        if not app.advanced_frame.grid_info():
            raise RuntimeError("Die erweiterten Importoptionen wurden nicht geoeffnet.")
        remote = app.online_service.prepare_url("https://example.com/feed.xml")
        discovery = parse_podcast_feed(
            b"""<rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
            <channel><title>Test</title><item><title>Folge</title>
            <podcast:transcript url="https://example.com/folge.vtt" type="text/vtt" />
            </item></channel></rss>""",
            remote.url,
        )
        if len(discovery.transcripts) != 1:
            raise RuntimeError("Die Offline-RSS-Pruefung wurde nicht ausgefuehrt.")
        root.update_idletasks()
    finally:
        root.destroy()
