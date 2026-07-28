from typing import Callable
import customtkinter as ctk

class CoverPanelFrame(ctk.CTkFrame):
    """Right-side cover preview & action panel."""

    def __init__(
        self,
        parent,
        on_cover_source_changed: Callable[[], None],
        on_open_crop_dialog: Callable[[], None],
        on_open_cover_chooser: Callable[[], None],
        on_load_manual_cover: Callable[[], None],
        on_google_cover_search: Callable[[], None],
        on_apply_metadata: Callable[[], None]
    ):
        super().__init__(parent, width=360)
        self.parent = parent
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.on_cover_source_changed = on_cover_source_changed
        self.on_open_crop_dialog = on_open_crop_dialog
        self.on_open_cover_chooser = on_open_cover_chooser
        self.on_load_manual_cover = on_load_manual_cover
        self.on_google_cover_search = on_google_cover_search
        self.on_apply_metadata = on_apply_metadata

        self._build_ui()

    def _build_ui(self):
        self.cover_title = ctk.CTkLabel(self, text="Cover Art", font=ctk.CTkFont(size=14, weight="bold"))
        self.cover_title.grid(row=0, column=0, padx=10, pady=10)

        # Cover Image Canvas / Label
        self.cover_img_label = ctk.CTkLabel(self, text="Kein Cover geladen", fg_color="#2b2b2b", width=300, height=300)
        self.cover_img_label.grid(row=1, column=0, padx=15, pady=10, sticky="n")

        self.cover_status_lbl = ctk.CTkLabel(self, text="", text_color="gray")
        self.cover_status_lbl.grid(row=2, column=0, padx=10, pady=5)

        # Cover sources checkboxes frame
        self.sources_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sources_frame.grid(row=3, column=0, padx=50, pady=5, sticky="w")
        
        self.source_embedded_var = ctk.BooleanVar(value=True)
        self.source_itunes_var = ctk.BooleanVar(value=True)
        self.source_deezer_var = ctk.BooleanVar(value=True)
        self.source_musicbrainz_var = ctk.BooleanVar(value=True)
        
        self.source_embedded_cb = ctk.CTkCheckBox(self.sources_frame, text="Eingebettetes Cover", variable=self.source_embedded_var, command=self.on_cover_source_changed)
        self.source_embedded_cb.pack(anchor="w", pady=2)
        
        self.source_itunes_cb = ctk.CTkCheckBox(self.sources_frame, text="iTunes", variable=self.source_itunes_var, command=self.on_cover_source_changed)
        self.source_itunes_cb.pack(anchor="w", pady=2)
        
        self.source_deezer_cb = ctk.CTkCheckBox(self.sources_frame, text="Deezer", variable=self.source_deezer_var, command=self.on_cover_source_changed)
        self.source_deezer_cb.pack(anchor="w", pady=2)
        
        self.source_musicbrainz_cb = ctk.CTkCheckBox(self.sources_frame, text="MusicBrainz", variable=self.source_musicbrainz_var, command=self.on_cover_source_changed)
        self.source_musicbrainz_cb.pack(anchor="w", pady=2)

        self.crop_cover_btn = ctk.CTkButton(self, text="✂ Cover zuschneiden...", command=self.on_open_crop_dialog, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.crop_cover_btn.grid(row=4, column=0, padx=20, pady=4, sticky="ew")

        self.chooser_cover_btn = ctk.CTkButton(self, text="🎨 Cover wählen (Varianten)...", command=self.on_open_cover_chooser, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.chooser_cover_btn.grid(row=5, column=0, padx=20, pady=4, sticky="ew")

        self.manual_cover_btn = ctk.CTkButton(self, text="Cover aus Datei laden...", command=self.on_load_manual_cover, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.manual_cover_btn.grid(row=6, column=0, padx=20, pady=4, sticky="ew")

        self.google_search_btn = ctk.CTkButton(self, text="🌐 Google Bildersuche...", command=self.on_google_cover_search, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.google_search_btn.grid(row=7, column=0, padx=20, pady=4, sticky="ew")

        self.apply_btn = ctk.CTkButton(self, text="Speichern & Umbenennen", command=self.on_apply_metadata, state="disabled", fg_color="#1f538d", hover_color="#143960")
        self.apply_btn.grid(row=8, column=0, padx=20, pady=(15, 20), sticky="ew")
