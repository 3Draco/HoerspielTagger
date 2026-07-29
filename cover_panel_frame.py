from typing import Callable
import customtkinter as ctk

class CoverSourcesDialog(ctk.CTkToplevel):
    """Modal dialog for selecting active online cover portals."""

    def __init__(self, parent, panel_frame):
        super().__init__(parent)
        self.panel_frame = panel_frame
        self.title("⚙️ Cover-Portale konfigurieren")
        self.geometry("380x300")
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
                win_w, win_h = 380, 300
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
            text="🌐 Online Cover-Portale", 
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(pady=(15, 5))

        ctk.CTkLabel(
            self, 
            text="Wähle aus, auf welchen Portalen nach Hörspiel-Covern und Veröffentlichungsjahren gesucht werden soll:",
            wraplength=340,
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).pack(padx=20, pady=(0, 10))

        frame = ctk.CTkFrame(self)
        frame.pack(padx=20, pady=5, fill="x")

        self.cb_discogs = ctk.CTkCheckBox(
            frame, text="📻 Discogs (Sehr gut für alte Hörspiele)", 
            variable=self.panel_frame.source_discogs_var,
            command=self.panel_frame.on_cover_source_changed
        )
        self.cb_discogs.pack(anchor="w", padx=15, pady=6)

        self.cb_itunes = ctk.CTkCheckBox(
            frame, text="🎵 iTunes / Apple Music (Hohe Auflösung)", 
            variable=self.panel_frame.source_itunes_var,
            command=self.panel_frame.on_cover_source_changed
        )
        self.cb_itunes.pack(anchor="w", padx=15, pady=6)

        self.cb_deezer = ctk.CTkCheckBox(
            frame, text="🎧 Deezer", 
            variable=self.panel_frame.source_deezer_var,
            command=self.panel_frame.on_cover_source_changed
        )
        self.cb_deezer.pack(anchor="w", padx=15, pady=6)

        self.cb_musicbrainz = ctk.CTkCheckBox(
            frame, text="🎼 MusicBrainz", 
            variable=self.panel_frame.source_musicbrainz_var,
            command=self.panel_frame.on_cover_source_changed
        )
        self.cb_musicbrainz.pack(anchor="w", padx=15, pady=6)

        ctk.CTkButton(
            self, text="Fertig", width=120, command=self.destroy, fg_color="#1f538d"
        ).pack(pady=12)


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

        # Source variables
        self.source_embedded_var = ctk.BooleanVar(value=True)
        self.source_discogs_var = ctk.BooleanVar(value=True)
        self.source_itunes_var = ctk.BooleanVar(value=True)
        self.source_deezer_var = ctk.BooleanVar(value=True)
        self.source_musicbrainz_var = ctk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self):
        self.cover_title = ctk.CTkLabel(self, text="Cover Art", font=ctk.CTkFont(size=14, weight="bold"))
        self.cover_title.grid(row=0, column=0, padx=10, pady=10)

        # Cover Image Canvas / Label
        self.cover_img_label = ctk.CTkLabel(self, text="Kein Cover geladen", fg_color="#2b2b2b", width=300, height=300)
        self.cover_img_label.grid(row=1, column=0, padx=15, pady=10, sticky="n")

        self.cover_status_lbl = ctk.CTkLabel(self, text="", text_color="gray")
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

        self.apply_btn = ctk.CTkButton(self, text="Speichern & Umbenennen", command=self.on_apply_metadata, state="disabled", fg_color="#1f538d", hover_color="#143960")
        self.apply_btn.grid(row=8, column=0, padx=20, pady=(15, 20), sticky="ew")

    def _open_portals_dialog(self):
        CoverSourcesDialog(self.parent, self)
