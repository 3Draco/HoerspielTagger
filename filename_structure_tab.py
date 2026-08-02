import customtkinter as ctk
from typing import Callable, List, Dict, Any

class FilenameStructureTab(ctk.CTkScrollableFrame):
    """
    Dedicated UI Tab component for configuring custom folder & track file naming schemes,
    tag insertion buttons, track reordering list, and real-time live preview.
    """

    DEFAULT_FOLDER_PATTERN = "%Serie% %Folgennummer:02d% - %Folgentitel%"
    DEFAULT_FILE_PATTERN = "%Track:02d% - %Folgentitel%.mp3"

    def __init__(self, parent, on_update_live_preview: Callable[[], None]):
        super().__init__(parent)
        self.parent = parent
        self.on_update_live_preview = on_update_live_preview

        self.grid_columnconfigure(0, weight=1)

        self._build_ui()

    def _build_ui(self):
        # ---------------- 1. NAMING SCHEMES SECTION ----------------
        self.schema_card = ctk.CTkFrame(self, corner_radius=8)
        self.schema_card.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 15))
        self.schema_card.grid_columnconfigure(1, weight=1)

        schema_title = ctk.CTkLabel(
            self.schema_card,
            text="⚙️ Ordner- & Dateinamen-Muster (Custom Naming Schemes)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#3b82f6"
        )
        schema_title.grid(row=0, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="w")

        schema_desc = ctk.CTkLabel(
            self.schema_card,
            text="Passe an, wie Ordner und MP3-Dateinamen aufgebaut werden sollen. Klicke auf die Tags, um Platzhalter an der Cursor-Position einzufügen.",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=700,
            justify="left"
        )
        schema_desc.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="w")

        # --- A. Ordnernamens-Schema ---
        folder_lbl = ctk.CTkLabel(self.schema_card, text="📁 Ordnernamens-Muster:", font=ctk.CTkFont(weight="bold"))
        folder_lbl.grid(row=2, column=0, padx=12, pady=(5, 2), sticky="w")

        self.folder_pattern_ent = ctk.CTkEntry(self.schema_card, placeholder_text=self.DEFAULT_FOLDER_PATTERN)
        self.folder_pattern_ent.grid(row=2, column=1, padx=12, pady=(5, 2), sticky="ew")
        self.folder_pattern_ent.insert(0, self.DEFAULT_FOLDER_PATTERN)
        self.folder_pattern_ent.bind("<KeyRelease>", lambda e: self.on_update_live_preview())

        # Folder Tags Buttons Frame
        folder_btn_frame = ctk.CTkFrame(self.schema_card, fg_color="transparent")
        folder_btn_frame.grid(row=3, column=1, padx=12, pady=(2, 10), sticky="w")

        folder_tags = [
            ("%Serie%", "%Serie%"),
            ("%Folgennummer%", "%Folgennummer% (1)"),
            ("%Folgennummer:02d%", "%Folgennummer:02d% (01)"),
            ("%Folgennummer:03d%", "%Folgennummer:03d% (001)"),
            ("%Folgentitel%", "%Folgentitel%"),
            ("%Album%", "%Album%"),
            ("%Jahr%", "%Jahr%"),
            ("%Interpret%", "%Interpret%")
        ]

        for tag_val, btn_txt in folder_tags:
            btn = ctk.CTkButton(
                folder_btn_frame,
                text=btn_txt,
                height=24,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#2d3748",
                hover_color="#4a5568",
                command=lambda t=tag_val: self._insert_token(self.folder_pattern_ent, t)
            )
            btn.pack(side="left", padx=2, pady=2)

        # --- B. Dateinamens-Schema (Tracks) ---
        file_lbl = ctk.CTkLabel(self.schema_card, text="🎵 Dateinamens-Muster (Tracks):", font=ctk.CTkFont(weight="bold"))
        file_lbl.grid(row=4, column=0, padx=12, pady=(5, 2), sticky="w")

        self.file_pattern_ent = ctk.CTkEntry(self.schema_card, placeholder_text=self.DEFAULT_FILE_PATTERN)
        self.file_pattern_ent.grid(row=4, column=1, padx=12, pady=(5, 2), sticky="ew")
        self.file_pattern_ent.insert(0, self.DEFAULT_FILE_PATTERN)
        self.file_pattern_ent.bind("<KeyRelease>", lambda e: self.on_update_live_preview())

        # File Tags Buttons Frame
        file_btn_frame = ctk.CTkFrame(self.schema_card, fg_color="transparent")
        file_btn_frame.grid(row=5, column=1, padx=12, pady=(2, 10), sticky="w")

        file_tags = [
            ("%Track%", "%Track% (1)"),
            ("%Track:02d%", "%Track:02d% (01)"),
            ("%Track:03d%", "%Track:03d% (001)"),
            ("%Folgentitel%", "%Folgentitel%"),
            ("%Serie%", "%Serie%"),
            ("%Folgennummer%", "%Folgennummer%"),
            ("%Folgennummer:02d%", "%Folgennummer:02d%"),
            ("%Folgennummer:03d%", "%Folgennummer:03d%"),
            ("%Album%", "%Album%"),
            ("%Jahr%", "%Jahr%")
        ]

        for tag_val, btn_txt in file_tags:
            btn = ctk.CTkButton(
                file_btn_frame,
                text=btn_txt,
                height=24,
                font=ctk.CTkFont(size=10, weight="bold"),
                fg_color="#1f538d",
                hover_color="#14375e",
                command=lambda t=tag_val: self._insert_token(self.file_pattern_ent, t)
            )
            btn.pack(side="left", padx=2, pady=2)

        # ---------------- 2. TRACKS / KAPITEL LIST SECTION ----------------
        self.tracks_title = ctk.CTkLabel(self, text="Kapitel / Tracks", font=ctk.CTkFont(size=14, weight="bold"))
        self.tracks_title.grid(row=1, column=0, padx=10, pady=(10, 5), sticky="w")

        self.tracks_container = ctk.CTkFrame(self, fg_color="transparent")
        self.tracks_container.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.tracks_container.grid_columnconfigure(1, weight=3)

        # ---------------- 3. LIVE PREVIEW CARD SECTION ----------------
        self.preview_card = ctk.CTkFrame(self, corner_radius=8)
        self.preview_card.grid(row=3, column=0, sticky="nsew", padx=10, pady=(15, 10))

        preview_header = ctk.CTkLabel(
            self.preview_card,
            text="🔍 Live-Vorschau (Ziel-Ordner & MP3-Dateinamen nach Umbenennen):",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        preview_header.pack(anchor="w", padx=12, pady=(10, 4))

        self.preview_textbox = ctk.CTkTextbox(self.preview_card, height=140, font=ctk.CTkFont(family="Consolas", size=11))
        self.preview_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 10))

    def _insert_token(self, entry: ctk.CTkEntry, token: str):
        """Inserts a token at the current cursor position in entry."""
        try:
            insert_pos = entry.index(ctk.INSERT)
        except Exception:
            insert_pos = len(entry.get())
        entry.insert(insert_pos, token)
        entry.focus_set()
        self.on_update_live_preview()

    def get_folder_pattern(self) -> str:
        val = self.folder_pattern_ent.get().strip()
        return val if val else self.DEFAULT_FOLDER_PATTERN

    def get_file_pattern(self) -> str:
        val = self.file_pattern_ent.get().strip()
        return val if val else self.DEFAULT_FILE_PATTERN

    def set_folder_pattern(self, pattern: str):
        self.folder_pattern_ent.delete(0, ctk.END)
        self.folder_pattern_ent.insert(0, pattern if pattern else self.DEFAULT_FOLDER_PATTERN)

    def set_file_pattern(self, pattern: str):
        self.file_pattern_ent.delete(0, ctk.END)
        self.file_pattern_ent.insert(0, pattern if pattern else self.DEFAULT_FILE_PATTERN)
