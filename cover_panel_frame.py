from typing import Callable, Optional, Dict
import customtkinter as ctk
import config

class CoverSourcesDialog(ctk.CTkToplevel):
    """Modal dialog for selecting active online cover portals and their individual cover limits."""

    def __init__(self, parent, panel_frame):
        super().__init__(parent)
        self.panel_frame = panel_frame
        self.title("⚙️ Cover-Portale & Limits konfigurieren")
        self.geometry("480x360")
        self.resizable(False, False)

        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.grab_set()

        # Center relative to parent
        self.update_idletasks()
        if parent:
            try:
                parent_x = parent.winfo_rootx()
                parent_y = parent.winfo_rooty()
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                win_w, win_h = 480, 360
                x = max(0, parent_x + (parent_w - win_w) // 2)
                y = max(0, parent_y + (parent_h - win_h) // 2)
                self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

        self._build_ui()
        self.after(200, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        ctk.CTkLabel(
            self, 
            text="🌐 Online Cover-Portale & Einzel-Limits", 
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self, 
            text="Wähle aus, auf welchen Portalen nach Hörspiel-Covern gesucht werden soll und wie viele Cover-Varianten pro Portal geladen werden (0 = Aus):",
            wraplength=440,
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).pack(padx=20, pady=(0, 10))

        frame = ctk.CTkFrame(self)
        frame.pack(padx=20, pady=5, fill="x")

        portals = [
            ("📻 Discogs (Sehr gut für alte Hörspiele)", self.panel_frame.source_discogs_var, self.panel_frame.limit_discogs_var),
            ("🎵 iTunes / Apple Music (Hohe Auflösung)", self.panel_frame.source_itunes_var, self.panel_frame.limit_itunes_var),
            ("🎧 Deezer", self.panel_frame.source_deezer_var, self.panel_frame.limit_deezer_var),
            ("🎼 MusicBrainz", self.panel_frame.source_musicbrainz_var, self.panel_frame.limit_musicbrainz_var),
        ]

        option_values = ["0", "1", "2", "3", "5", "6", "10", "15", "20"]

        for idx, (label_text, cb_var, limit_var) in enumerate(portals):
            row_frame = ctk.CTkFrame(frame, fg_color="transparent")
            row_frame.pack(fill="x", padx=10, pady=6)
            row_frame.grid_columnconfigure(0, weight=1)

            cb = ctk.CTkCheckBox(
                row_frame, 
                text=label_text, 
                variable=cb_var,
                command=lambda v=cb_var, l=limit_var: self._on_cb_toggled(v, l)
            )
            cb.grid(row=0, column=0, sticky="w")

            lbl_max = ctk.CTkLabel(row_frame, text="Max:", text_color="gray")
            lbl_max.grid(row=0, column=1, padx=(10, 4), sticky="e")

            opt = ctk.CTkOptionMenu(
                row_frame,
                values=option_values,
                variable=limit_var,
                width=65,
                command=lambda val, v=cb_var: self._on_opt_changed(val, v)
            )
            opt.grid(row=0, column=2, sticky="e")

        ctk.CTkButton(
            self, text="Fertig", width=120, command=self.destroy, fg_color="#1f538d"
        ).pack(pady=12)

    def _on_cb_toggled(self, cb_var, limit_var):
        if not cb_var.get():
            limit_var.set("0")
        elif limit_var.get() == "0":
            limit_var.set("3")
        self.panel_frame.on_cover_source_changed()

    def _on_opt_changed(self, val, cb_var):
        if val == "0":
            cb_var.set(False)
        else:
            cb_var.set(True)
        self.panel_frame.on_cover_source_changed()


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
        on_apply_metadata: Callable[[], None],
        on_apply_all_metadata: Optional[Callable[[], None]] = None
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
        self.on_apply_all_metadata = on_apply_all_metadata

        # Source variables
        self.source_embedded_var = ctk.BooleanVar(value=True)
        self.source_discogs_var = ctk.BooleanVar(value=True)
        self.source_itunes_var = ctk.BooleanVar(value=True)
        self.source_deezer_var = ctk.BooleanVar(value=True)
        self.source_musicbrainz_var = ctk.BooleanVar(value=True)

        # Per-provider limits variables
        cover_limits = getattr(config, 'COVER_LIMITS', {"discogs": 3, "itunes": 3, "deezer": 3, "musicbrainz": 3})
        self.limit_discogs_var = ctk.StringVar(value=str(cover_limits.get("discogs", 3)))
        self.limit_itunes_var = ctk.StringVar(value=str(cover_limits.get("itunes", 3)))
        self.limit_deezer_var = ctk.StringVar(value=str(cover_limits.get("deezer", 3)))
        self.limit_musicbrainz_var = ctk.StringVar(value=str(cover_limits.get("musicbrainz", 3)))

        self._build_ui()

    def get_provider_limits(self) -> Dict[str, int]:
        """Returns active per-provider candidate cover limits."""
        return {
            "discogs": int(self.limit_discogs_var.get()) if self.source_discogs_var.get() and self.limit_discogs_var.get().isdigit() else 0,
            "itunes": int(self.limit_itunes_var.get()) if self.source_itunes_var.get() and self.limit_itunes_var.get().isdigit() else 0,
            "deezer": int(self.limit_deezer_var.get()) if self.source_deezer_var.get() and self.limit_deezer_var.get().isdigit() else 0,
            "musicbrainz": int(self.limit_musicbrainz_var.get()) if self.source_musicbrainz_var.get() and self.limit_musicbrainz_var.get().isdigit() else 0,
        }

    def _build_ui(self):
        self.cover_title = ctk.CTkLabel(self, text="Cover Art", font=ctk.CTkFont(size=14, weight="bold"))
        self.cover_title.grid(row=0, column=0, padx=10, pady=10)

        # Cover Image Canvas / Label
        self.cover_img_label = ctk.CTkLabel(
            self, 
            text="📥 Kein Cover geladen\n\n(Bild per Drag & Drop\nhierher ziehen oder klicken)", 
            fg_color="#2b2b2b", 
            width=300, 
            height=300,
            cursor="hand2"
        )
        self.cover_img_label.grid(row=1, column=0, padx=15, pady=10, sticky="n")
        self.cover_img_label.bind("<Button-1>", lambda e: self.on_load_manual_cover() if callable(self.on_load_manual_cover) else None)

        self.cover_status_lbl = ctk.CTkLabel(self, text="", text_color="gray", wraplength=320)
        self.cover_status_lbl.grid(row=2, column=0, padx=10, pady=5)

        # Cover sources clean frame
        self.sources_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.sources_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")
        self.sources_frame.grid_columnconfigure(0, weight=1)

        self.source_embedded_cb = ctk.CTkCheckBox(
            self.sources_frame, 
            text="Eingebettetes Cover bevorzugen", 
            variable=self.source_embedded_var, 
            command=self.on_cover_source_changed
        )
        self.source_embedded_cb.pack(anchor="w", pady=3)

        self.portals_btn = ctk.CTkButton(
            self.sources_frame,
            text="⚙️ Online-Portale konfigurieren...",
            height=26,
            fg_color="#333333",
            hover_color="#444444",
            command=self._open_portals_dialog
        )
        self.portals_btn.pack(anchor="w", pady=3, fill="x")

        self.crop_cover_btn = ctk.CTkButton(self, text="✂ Cover zuschneiden...", command=self.on_open_crop_dialog, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.crop_cover_btn.grid(row=4, column=0, padx=20, pady=4, sticky="ew")

        self.chooser_cover_btn = ctk.CTkButton(self, text="🎨 Cover wählen (Varianten)...", command=self.on_open_cover_chooser, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.chooser_cover_btn.grid(row=5, column=0, padx=20, pady=4, sticky="ew")

        self.manual_cover_btn = ctk.CTkButton(self, text="Cover aus Datei laden...", command=self.on_load_manual_cover, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.manual_cover_btn.grid(row=6, column=0, padx=20, pady=4, sticky="ew")

        self.google_search_btn = ctk.CTkButton(self, text="🌐 Google Bildersuche...", command=self.on_google_cover_search, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.google_search_btn.grid(row=7, column=0, padx=20, pady=4, sticky="ew")

        self.apply_btn = ctk.CTkButton(self, text="Einzelnes Album speichern", command=self.on_apply_metadata, state="disabled", fg_color="#1f538d", hover_color="#143960")
        self.apply_btn.grid(row=8, column=0, padx=20, pady=(15, 4), sticky="ew")

        self.apply_all_btn = ctk.CTkButton(self, text="💾 Alle Alben auf einmal speichern", command=self.on_apply_all_metadata, state="disabled", fg_color="#2b712b", hover_color="#1e4e1e", font=ctk.CTkFont(weight="bold"))
        self.apply_all_btn.grid(row=9, column=0, padx=20, pady=(4, 20), sticky="ew")

    def _open_portals_dialog(self):
        CoverSourcesDialog(self.parent, self)
