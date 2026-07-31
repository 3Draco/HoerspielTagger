from typing import Dict, Callable, List, Any
import customtkinter as ctk

class MetadataFormFrame(ctk.CTkScrollableFrame):
    """Main scrollable metadata form and track list editor."""

    def __init__(self, parent, on_update_live_preview: Callable[[], None]):
        super().__init__(parent)
        self.parent = parent
        self.on_update_live_preview = on_update_live_preview

        self.form_entries: Dict[str, ctk.CTkEntry] = {}
        self.current_tag_entries: Dict[str, ctk.CTkEntry] = {}

        self.grid_columnconfigure(1, weight=1) # Column 1: Current MP3 Tag (Vorher)
        self.grid_columnconfigure(2, weight=0) # Column 2: Copy Button
        self.grid_columnconfigure(3, weight=1) # Column 3: LLM Proposal (Nachher)

        self._build_ui()

    def _build_ui(self):
        # Form Table Column Headers
        ctk.CTkLabel(self, text="ID3 Feld", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=10, pady=(5, 8), sticky="w")
        ctk.CTkLabel(self, text="📄 Aktuell in MP3-Dateien (Vorher)", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").grid(row=0, column=1, padx=10, pady=(5, 8), sticky="w")
        ctk.CTkLabel(self, text="🤖 LLM-Vorschlag / Bearbeitbar (Nachher)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#1f538d").grid(row=0, column=3, padx=10, pady=(5, 8), sticky="w")

        # Editor Fields with explicit ID3 Frame tags, Current Values (Vorher), and Hints
        self._create_form_row(1, "Album-Interpret (Serie)", "TPE2 / albumartist", "Reiner Serienname (z. B. 'Fünf Freunde')", "album_artist")
        self._create_form_row(2, "Album (Folgentitel)", "TALB / album", "Format: '03 - Fünf Freunde und das Burgverlies'", "album")
        self._create_form_row(3, "Reiner Folgentitel", "TIT2 / title", "Folgentitel ohne Nummerierung für Plex", "episode_title")
        self._create_form_row(4, "Serie / Haupt-Interpret", "TPE1 / artist", "Reiner Serienname (z. B. 'Fünf Freunde')", "series")
        self._create_form_row(5, "Folgennummer / Track-Nr.", "TRCK / tracknumber", "Nummer der Folge (z. B. 3)", "series_part")
        self._create_form_row(6, "Erscheinungsjahr", "TDRC / year", "Veröffentlichungsjahr (z. B. 1978)", "year")
        self._create_form_row(7, "Genre", "TCON / genre", "Festes Genre für Hörspiele", "genre")

        # Separator for Tracks
        self.tracks_title = ctk.CTkLabel(self, text="Kapitel / Tracks", font=ctk.CTkFont(size=14, weight="bold"))
        self.tracks_title.grid(row=8, column=0, columnspan=4, padx=10, pady=(20, 10), sticky="w")

        # Frame to hold dynamic track rows
        self.tracks_container = ctk.CTkFrame(self, fg_color="transparent")
        self.tracks_container.grid(row=9, column=0, columnspan=4, sticky="nsew", padx=5, pady=5)
        self.tracks_container.grid_columnconfigure(1, weight=3) # clean title entry

        # Live Preview Card (Result after Rename/Merge)
        self.preview_card = ctk.CTkFrame(self, corner_radius=8)
        self.preview_card.grid(row=10, column=0, columnspan=4, sticky="nsew", padx=5, pady=(15, 10))

        preview_header = ctk.CTkLabel(self.preview_card, text="🔍 Live-Vorschau (Ziel-Ordner & MP3-Dateinamen nach Umbenennen):", font=ctk.CTkFont(size=13, weight="bold"))
        preview_header.pack(anchor="w", padx=12, pady=(10, 4))

        self.preview_textbox = ctk.CTkTextbox(self.preview_card, height=130, font=ctk.CTkFont(family="Consolas", size=11))
        self.preview_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    def _create_form_row(self, row_idx: int, label_text: str, id3_tag: str, hint_text: str, key: str):
        # Column 0: Label
        lbl = ctk.CTkLabel(self, text=label_text, font=ctk.CTkFont(weight="bold"))
        lbl.grid(row=row_idx, column=0, padx=10, pady=4, sticky="w")

        # Column 1: Current MP3 Tag value (Vorher - read only)
        curr_frame = ctk.CTkFrame(self, fg_color="transparent")
        curr_frame.grid(row=row_idx, column=1, padx=8, pady=4, sticky="ew")
        curr_frame.grid_columnconfigure(0, weight=1)

        curr_ent = ctk.CTkEntry(curr_frame, state="disabled", fg_color=("#e2e8f0", "#1e293b"), text_color="gray")
        curr_ent.pack(fill="x")
        self.current_tag_entries[key] = curr_ent

        # Blue ID3 label underneath the current value entry
        ctk.CTkLabel(curr_frame, text=f"ID3: {id3_tag}", font=ctk.CTkFont(size=10), text_color="#3b82f6").pack(anchor="w", pady=(1, 0))

        # Column 2: Copy Button
        def _copy_value(k=key):
            val = self.current_tag_entries[k].get()
            self.form_entries[k].delete(0, ctk.END)
            self.form_entries[k].insert(0, val)
            self.on_update_live_preview()

        copy_btn = ctk.CTkButton(
            self,
            text="➔",
            width=28,
            height=28,
            fg_color="#2b2b2b",
            hover_color="#404040",
            text_color="#a0aec0",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=_copy_value
        )
        copy_btn.grid(row=row_idx, column=2, padx=4, pady=4)

        # Column 3: LLM Proposal entry (Nachher - editable)
        entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        entry_frame.grid(row=row_idx, column=3, padx=8, pady=4, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        ent = ctk.CTkEntry(entry_frame)
        ent.pack(fill="x")
        ent.bind("<KeyRelease>", lambda e: self.on_update_live_preview())

        ctk.CTkLabel(entry_frame, text=hint_text, font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", pady=(1, 0))
        self.form_entries[key] = ent
