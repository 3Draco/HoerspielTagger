import sys
from pathlib import Path
from typing import Callable, Optional
import customtkinter as ctk
from PIL import Image

class SidebarFrame(ctk.CTkFrame):
    """Left sidebar panel containing navigation, folder selection, options, and actions."""

    def __init__(
        self,
        parent,
        on_browse_folder: Callable[[], None],
        on_open_api_settings: Callable[[], None],
        on_merge_toggle: Callable[[], None],
        on_delete_tracks_toggle: Callable[[], None],
        on_update_preview: Callable[[], None],
        on_flat_episodes_toggle: Callable[[], None],
        on_scan_folder: Callable[[], None],
        on_start_analysis: Callable[[], None],
        on_clear_cache: Callable[[], None],
        on_open_splitter: Callable[[], None],
        on_open_series_db: Optional[Callable[[], None]] = None
    ):
        super().__init__(parent, width=280, corner_radius=0)
        self.parent = parent
        self.grid_rowconfigure(20, weight=1)

        self.on_browse_folder = on_browse_folder
        self.on_open_api_settings = on_open_api_settings
        self.on_merge_toggle = on_merge_toggle
        self.on_delete_tracks_toggle = on_delete_tracks_toggle
        self.on_update_preview = on_update_preview
        self.on_flat_episodes_toggle = on_flat_episodes_toggle
        self.on_scan_folder = on_scan_folder
        self.on_start_analysis = on_start_analysis
        self.on_clear_cache = on_clear_cache
        self.on_open_splitter = on_open_splitter
        self.on_open_series_db = on_open_series_db

        self._build_ui()

    def _on_open_series_db(self):
        if self.on_open_series_db:
            self.on_open_series_db()

    def _build_ui(self):
        # Determine base directory (supporting PyInstaller bundles)
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
            resource_dir = Path(getattr(sys, '_MEIPASS', base_dir))
        else:
            base_dir = Path(__file__).parent
            resource_dir = base_dir

        logo_path = resource_dir / "img" / "logo.png"
        if not logo_path.exists():
            logo_path = base_dir / "img" / "logo.png"

        if logo_path.exists():
            try:
                logo_img = Image.open(logo_path)
                self.logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(240, 131))
                self.logo_lbl = ctk.CTkLabel(self, image=self.logo_ctk, text="")
                self.logo_lbl.grid(row=0, column=0, padx=20, pady=(15, 10))
            except Exception:
                pass

        # Folder Selection
        self.folder_btn = ctk.CTkButton(self, text="Ordner wählen...", command=self.on_browse_folder, fg_color="#1f538d")
        self.folder_btn.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.folder_lbl = ctk.CTkLabel(self, text="Kein Ordner ausgewählt", wraplength=240, text_color="gray")
        self.folder_lbl.grid(row=2, column=0, padx=20, pady=(0, 10))

        # API settings button
        self.api_settings_btn = ctk.CTkButton(self, text="⚙️ API & Prompt Einstellungen...", command=self.on_open_api_settings, fg_color="#333333", hover_color="#444444")
        self.api_settings_btn.grid(row=3, column=0, padx=20, pady=(5, 4), sticky="ew")

        # Series DB Manager button
        self.series_db_btn = ctk.CTkButton(self, text="📚 Serien-Datenbank...", command=self._on_open_series_db, fg_color="#333333", hover_color="#444444")
        self.series_db_btn.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Options
        self.opt_lbl = ctk.CTkLabel(self, text="Optionen", font=ctk.CTkFont(size=14, weight="bold"))
        self.opt_lbl.grid(row=11, column=0, padx=20, pady=(5, 2), sticky="w")

        self.dry_run_var = ctk.BooleanVar(value=True)
        self.dry_run_cb = ctk.CTkCheckBox(self, text="Dry-Run (Testlauf)", variable=self.dry_run_var)
        self.dry_run_cb.grid(row=12, column=0, padx=20, pady=2, sticky="w")

        self.merge_var = ctk.BooleanVar(value=False)
        self.merge_cb = ctk.CTkCheckBox(self, text="Verlustfrei zusammenfügen & ID3-Kapitel", variable=self.merge_var, command=self.on_merge_toggle)
        self.merge_cb.grid(row=13, column=0, padx=20, pady=2, sticky="w")

        # Cleanup option under merge
        self.delete_tracks_var = ctk.BooleanVar(value=False)
        self.delete_tracks_cb = ctk.CTkCheckBox(self, text="  ↳ Originale löschen (statt in 'Tracks')", variable=self.delete_tracks_var, command=self.on_delete_tracks_toggle, state="disabled")
        self.delete_tracks_cb.grid(row=14, column=0, padx=20, pady=2, sticky="w")

        self.rename_folder_var = ctk.BooleanVar(value=True)
        self.rename_folder_cb = ctk.CTkCheckBox(self, text="📁 Episoden-Ordner umbenennen", variable=self.rename_folder_var, command=self.on_update_preview)
        self.rename_folder_cb.grid(row=16, column=0, padx=20, pady=2, sticky="w")

        self.parent_series_var = ctk.BooleanVar(value=True)
        self.parent_series_cb = ctk.CTkCheckBox(self, text="🏛 Serien-Ordner darüber anlegen", variable=self.parent_series_var, command=self.on_update_preview)
        self.parent_series_cb.grid(row=17, column=0, padx=20, pady=2, sticky="w")

        self.cover_var = ctk.BooleanVar(value=True)
        self.cover_cb = ctk.CTkCheckBox(self, text="Cover laden (wenn fehlt)", variable=self.cover_var)
        self.cover_cb.grid(row=18, column=0, padx=20, pady=2, sticky="w")

        self.flat_episodes_var = ctk.BooleanVar(value=False)
        self.flat_episodes_cb = ctk.CTkCheckBox(self, text="💿 Jede MP3 als eigene Folge", variable=self.flat_episodes_var, command=self.on_flat_episodes_toggle)
        self.flat_episodes_cb.grid(row=19, column=0, padx=20, pady=2, sticky="w")

        # Actions
        self.scan_btn = ctk.CTkButton(self, text="Ordner neu scannen", command=self.on_scan_folder, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.scan_btn.grid(row=21, column=0, padx=20, pady=4, sticky="ew")

        self.analyze_btn = ctk.CTkButton(self, text="LLM-Analyse starten", command=self.on_start_analysis, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.analyze_btn.grid(row=22, column=0, padx=20, pady=4, sticky="ew")

        self.clear_cache_btn = ctk.CTkButton(self, text="🧹 Cache leeren", command=self.on_clear_cache, fg_color="#2d88ad", hover_color="#1e5e78")
        self.clear_cache_btn.grid(row=23, column=0, padx=20, pady=4, sticky="ew")

        self.splitter_btn = ctk.CTkButton(self, text="✂ MP3 nach Kapiteln trennen...", command=self.on_open_splitter, fg_color="#1f538d", hover_color="#143960")
        self.splitter_btn.grid(row=24, column=0, padx=20, pady=(4, 15), sticky="ew")
