import os
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import io

from tkinterdnd2 import DND_FILES, TkinterDnD

from audio_scanner import AudioScanner
from llm_client import LLMClient, AlbumMetadata, TrackMetadata
from cover_downloader import CoverDownloader
from tag_writer import TagWriter
from file_merger import FileMerger
from chapter_manager import ChapterManager
from cover_chooser_dialog import CoverChooserDialog
from cover_crop_dialog import CoverCropDialog
import config

class HoerspielTaggerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()

        # Initialize TkDND extension
        try:
            self.TkdndVersion = TkinterDnD._require(self)
        except Exception as e:
            self.TkdndVersion = None

        self.title("📻 HoerspielTag - AI-Powered Audio Drama Tagger")
        
        # Load last settings and window geometry if exists
        try:
            import json
            state_file = Path(__file__).parent / "window_state.json"
            self.loaded_settings = {}
            if state_file.exists():
                with open(state_file, "r") as f:
                    self.loaded_settings = json.load(f)
                    geom = self.loaded_settings.get("geometry")
                    if geom:
                        parts = geom.split("+")
                        if len(parts) == 3:
                            x = int(parts[1])
                            y = int(parts[2])
                            screen_w = self.winfo_screenwidth()
                            screen_h = self.winfo_screenheight()
                            # Ensure it's not fully offscreen
                            if -100 < x < screen_w - 100 and -100 < y < screen_h - 100:
                                self.geometry(geom)
                            else:
                                self.geometry("1200x800")
                        else:
                            self.geometry("1200x800")
            else:
                self.geometry("1200x800")
        except Exception:
            self.loaded_settings = {}
            self.geometry("1200x800")

        self.minsize(1000, 700)

        # Application state
        self.target_dir: Optional[str] = None
        self.scan_results: List[Dict[str, Any]] = []
        self.current_album_idx: int = 0
        self.current_metadata: Optional[AlbumMetadata] = None
        self.cover_bytes: Optional[bytes] = None
        self.llm_client: Optional[LLMClient] = None

        # Threading lock/status
        self.is_processing = False

        # Dynamic storage for form inputs
        self.form_entries: Dict[str, ctk.CTkEntry] = {}
        self.current_tag_entries: Dict[str, ctk.CTkEntry] = {}
        self.track_rows: List[Dict[str, Any]] = []
        self.album_states: Dict[str, Dict[str, Any]] = {}
        self.current_ctk_image: Optional[ctk.CTkImage] = None

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self._build_ui()
        self._setup_drag_and_drop()
        self._load_config_defaults()

    def _on_app_close(self):
        """Ensures immediate and clean application termination on single click."""
        self.is_processing = False
        
        # Save settings and window geometry
        try:
            geom = self.geometry()
            settings = {
                "geometry": geom,
                "api_url": self.api_url_ent.get(),
                "api_key": self.api_key_ent.get(),
                "model_id": self.model_ent.get(),
                "dry_run": self.dry_run_var.get(),
                "merge": self.merge_var.get(),
                "move_tracks": self.move_tracks_var.get(),
                "delete_tracks": self.delete_tracks_var.get(),
                "rename_folder": self.rename_folder_var.get(),
                "parent_series": self.parent_series_var.get(),
                "cover": self.cover_var.get(),
                "target_dir": self.target_dir
            }
            import json
            state_file = Path(__file__).parent / "window_state.json"
            with open(state_file, "w") as f:
                json.dump(settings, f)
        except Exception:
            pass

        try:
            self.quit()
            self.destroy()
        except Exception:
            pass
        import os
        os._exit(0)

    def _build_ui(self):
        # Configure grid layout (2 rows, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Bottom status bar row
        self.grid_columnconfigure(0, weight=0)  # Left settings panel
        self.grid_columnconfigure(1, weight=1)  # Right work panel

        # ================= LEFT SIDEBAR =================
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.sidebar.grid_rowconfigure(19, weight=1)

        # Title / Logo
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            try:
                logo_img = Image.open(logo_path)
                self.logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(38, 38))
                self.title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
                self.title_frame.grid(row=0, column=0, padx=20, pady=(15, 10), sticky="ew")
                self.title_frame.grid_columnconfigure(1, weight=1)
                
                self.logo_lbl = ctk.CTkLabel(self.title_frame, image=self.logo_ctk, text="")
                self.logo_lbl.grid(row=0, column=0, padx=(0, 10))
                
                self.title_lbl = ctk.CTkLabel(self.title_frame, text="HoerspielTag", font=ctk.CTkFont(size=20, weight="bold"))
                self.title_lbl.grid(row=0, column=1, sticky="w")
            except Exception:
                self.title_lbl = ctk.CTkLabel(self.sidebar, text="HoerspielTag", font=ctk.CTkFont(size=20, weight="bold"))
                self.title_lbl.grid(row=0, column=0, padx=20, pady=(15, 10))
        else:
            self.title_lbl = ctk.CTkLabel(self.sidebar, text="HoerspielTag", font=ctk.CTkFont(size=20, weight="bold"))
            self.title_lbl.grid(row=0, column=0, padx=20, pady=(15, 10))

        # Folder Selection
        self.folder_btn = ctk.CTkButton(self.sidebar, text="Ordner wählen...", command=self._browse_folder, fg_color="#1f538d")
        self.folder_btn.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        
        self.folder_lbl = ctk.CTkLabel(self.sidebar, text="Kein Ordner ausgewählt", wraplength=240, text_color="gray")
        self.folder_lbl.grid(row=2, column=0, padx=20, pady=(0, 10))

        # API settings separator
        self.api_lbl = ctk.CTkLabel(self.sidebar, text="API Einstellungen", font=ctk.CTkFont(size=14, weight="bold"))
        self.api_lbl.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")

        # API Base URL
        self.api_url_lbl = ctk.CTkLabel(self.sidebar, text="Base URL:")
        self.api_url_lbl.grid(row=4, column=0, padx=20, pady=0, sticky="w")
        self.api_url_ent = ctk.CTkEntry(self.sidebar)
        self.api_url_ent.grid(row=5, column=0, padx=20, pady=(0, 5), sticky="ew")

        # API Key
        self.api_key_lbl = ctk.CTkLabel(self.sidebar, text="API Key:")
        self.api_key_lbl.grid(row=6, column=0, padx=20, pady=0, sticky="w")
        self.api_key_ent = ctk.CTkEntry(self.sidebar, show="*")
        self.api_key_ent.grid(row=7, column=0, padx=20, pady=(0, 5), sticky="ew")

        # Model ID
        self.model_lbl = ctk.CTkLabel(self.sidebar, text="Modell / Agent ID:")
        self.model_lbl.grid(row=8, column=0, padx=20, pady=0, sticky="w")
        self.model_ent = ctk.CTkEntry(self.sidebar)
        self.model_ent.grid(row=9, column=0, padx=20, pady=(0, 5), sticky="ew")

        # Connection status test button (Moved llm_status_lbl out of here)
        self.test_conn_btn = ctk.CTkButton(self.sidebar, text="🔍 Verbindung testen", height=22, command=self._test_llm_connection, fg_color="#333333", hover_color="#444444")
        self.test_conn_btn.grid(row=10, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Options
        self.opt_lbl = ctk.CTkLabel(self.sidebar, text="Optionen", font=ctk.CTkFont(size=14, weight="bold"))
        self.opt_lbl.grid(row=11, column=0, padx=20, pady=(5, 2), sticky="w")

        self.dry_run_var = ctk.BooleanVar(value=True)
        self.dry_run_cb = ctk.CTkCheckBox(self.sidebar, text="Dry-Run (Testlauf)", variable=self.dry_run_var)
        self.dry_run_cb.grid(row=12, column=0, padx=20, pady=2, sticky="w")

        self.merge_var = ctk.BooleanVar(value=False)
        self.merge_cb = ctk.CTkCheckBox(self.sidebar, text="Verlustfrei zusammenfügen & ID3-Kapitel", variable=self.merge_var, command=self._on_merge_toggle)
        self.merge_cb.grid(row=13, column=0, padx=20, pady=2, sticky="w")

        # Cleanup options (indented, disabled by default)
        self.move_tracks_var = ctk.BooleanVar(value=False)
        self.move_tracks_cb = ctk.CTkCheckBox(self.sidebar, text="  ↳ Originale in 'Tracks' verschieben", variable=self.move_tracks_var, command=self._on_move_tracks_toggle, state="disabled")
        self.move_tracks_cb.grid(row=14, column=0, padx=20, pady=2, sticky="w")

        self.delete_tracks_var = ctk.BooleanVar(value=False)
        self.delete_tracks_cb = ctk.CTkCheckBox(self.sidebar, text="  ↳ Originale löschen", variable=self.delete_tracks_var, command=self._on_delete_tracks_toggle, state="disabled")
        self.delete_tracks_cb.grid(row=15, column=0, padx=20, pady=2, sticky="w")

        self.rename_folder_var = ctk.BooleanVar(value=True)
        self.rename_folder_cb = ctk.CTkCheckBox(self.sidebar, text="📁 Episoden-Ordner umbenennen", variable=self.rename_folder_var, command=self._update_live_preview)
        self.rename_folder_cb.grid(row=16, column=0, padx=20, pady=2, sticky="w")

        self.parent_series_var = ctk.BooleanVar(value=True)
        self.parent_series_cb = ctk.CTkCheckBox(self.sidebar, text="🏛 Serien-Ordner darüber anlegen", variable=self.parent_series_var, command=self._update_live_preview)
        self.parent_series_cb.grid(row=17, column=0, padx=20, pady=2, sticky="w")

        self.cover_var = ctk.BooleanVar(value=True)
        self.cover_cb = ctk.CTkCheckBox(self.sidebar, text="Cover laden (wenn fehlt)", variable=self.cover_var)
        self.cover_cb.grid(row=18, column=0, padx=20, pady=2, sticky="w")

        # Actions
        self.scan_btn = ctk.CTkButton(self.sidebar, text="Ordner neu scannen", command=self._scan_folder, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.scan_btn.grid(row=20, column=0, padx=20, pady=4, sticky="ew")

        self.analyze_btn = ctk.CTkButton(self.sidebar, text="LLM-Analyse starten", command=self._start_analysis, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.analyze_btn.grid(row=21, column=0, padx=20, pady=4, sticky="ew")

        self.clear_cache_btn = ctk.CTkButton(self.sidebar, text="🧹 Cache leeren", command=self._clear_cache, fg_color="#2d88ad", hover_color="#1e5e78")
        self.clear_cache_btn.grid(row=22, column=0, padx=20, pady=4, sticky="ew")

        self.splitter_btn = ctk.CTkButton(self.sidebar, text="✂ MP3 nach Kapiteln trennen...", command=self._open_splitter_dialog, fg_color="#1f538d", hover_color="#143960")
        self.splitter_btn.grid(row=23, column=0, padx=20, pady=(4, 15), sticky="ew")


        # ================= MAIN AREA =================
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Header status / Navigation
        self.header_frame = ctk.CTkFrame(self.main_frame, height=50)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.header_frame.grid_columnconfigure(1, weight=1)

        self.nav_prev_btn = ctk.CTkButton(self.header_frame, text="◀ Zurück", width=80, command=self._prev_album, state="disabled")
        self.nav_prev_btn.grid(row=0, column=0, padx=10, pady=10)

        self.album_status_lbl = ctk.CTkLabel(self.header_frame, text="Keine Daten geladen", font=ctk.CTkFont(size=14, weight="bold"))
        self.album_status_lbl.grid(row=0, column=1, padx=10, pady=10)

        self.nav_next_btn = ctk.CTkButton(self.header_frame, text="Weiter ▶", width=80, command=self._next_album, state="disabled")
        self.nav_next_btn.grid(row=0, column=2, padx=10, pady=10)

        # ================= BOTTOM STATUS BAR =================
        self.status_bar = ctk.CTkFrame(self, height=28, corner_radius=0)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        self.status_bar.grid_columnconfigure(1, weight=1) # Spacer column

        # LLM Status Label in bottom status bar (left side)
        self.llm_status_lbl = ctk.CTkLabel(self.status_bar, text="🟡 Verbindung wird geprüft...", font=ctk.CTkFont(size=11), text_color="orange")
        self.llm_status_lbl.grid(row=0, column=0, padx=10, pady=2, sticky="w")

        # Spacer
        spacer = ctk.CTkLabel(self.status_bar, text="")
        spacer.grid(row=0, column=1, sticky="ew")

        # Progress bar & Loading status in status bar (right side)
        self.progress_bar = ctk.CTkProgressBar(self.status_bar, mode="indeterminate", width=150)
        self.loading_lbl = ctk.CTkLabel(self.status_bar, text="", font=ctk.CTkFont(size=11, weight="bold"))

        # Content area tab structure
        self.content_tabview = ctk.CTkTabview(self.main_frame)
        self.content_tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.tab_scan = self.content_tabview.add("Scannen und Ordnerstruktur")
        self.tab_edit = self.content_tabview.add("Metadaten bearbeiten und taggen")

        # ---------------- TAB 1: Scan Log & Drop Zone ----------------
        self.tab_scan.grid_rowconfigure(0, weight=0) # Drop Zone fixed height
        self.tab_scan.grid_rowconfigure(1, weight=1) # Log textbox fills remaining area
        self.tab_scan.grid_columnconfigure(0, weight=1)

        # Drop Zone Frame
        self.drop_frame = ctk.CTkFrame(self.tab_scan, fg_color=("#d9e8f5", "#1e293b"), border_width=2, border_color="#1f538d", corner_radius=10)
        self.drop_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.drop_label = ctk.CTkLabel(
            self.drop_frame,
            text="📥 Ordner per Drag & Drop hierher ziehen\n(oder hier klicken, um Ordner auszuwählen)",
            font=ctk.CTkFont(size=14, weight="bold"),
            pady=15,
            cursor="hand2"
        )
        self.drop_label.pack(expand=True, fill="both")

        # Click event on drop zone to trigger browse folder
        self.drop_frame.bind("<Button-1>", lambda e: self._browse_folder())
        self.drop_label.bind("<Button-1>", lambda e: self._browse_folder())

        # Scan Log Textbox
        self.scan_textbox = ctk.CTkTextbox(self.tab_scan, font=ctk.CTkFont(family="Consolas", size=12))
        self.scan_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.scan_textbox.insert("0.0", "Wähle einen Ordner aus oder ziehe einen Ordner in das Drop-Feld oben, um zu beginnen...")

        # ---------------- TAB 2: Metadata Edit ----------------
        self.tab_edit.grid_rowconfigure(0, weight=1)
        self.tab_edit.grid_columnconfigure(0, weight=1) # Editor Form
        self.tab_edit.grid_columnconfigure(1, weight=0) # Cover Preview

        # Metadata Form Panel (Left of Tab 2)
        self.form_scroll = ctk.CTkScrollableFrame(self.tab_edit)
        self.form_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.form_scroll.grid_columnconfigure(1, weight=1) # Column 1: Current MP3 Tag (Vorher)
        self.form_scroll.grid_columnconfigure(2, weight=1) # Column 2: LLM Proposal (Nachher)

        # Form Table Column Headers
        ctk.CTkLabel(self.form_scroll, text="ID3 Feld", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=10, pady=(5, 8), sticky="w")
        ctk.CTkLabel(self.form_scroll, text="📄 Aktuell in MP3-Dateien (Vorher)", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray").grid(row=0, column=1, padx=10, pady=(5, 8), sticky="w")
        ctk.CTkLabel(self.form_scroll, text="🤖 LLM-Vorschlag / Bearbeitbar (Nachher)", font=ctk.CTkFont(size=12, weight="bold"), text_color="#1f538d").grid(row=0, column=2, padx=10, pady=(5, 8), sticky="w")

        # Editor Fields with explicit ID3 Frame tags, Current Values (Vorher), and Hints
        self._create_form_row(1, "Album-Interpret (Serie)", "TPE2 / albumartist", "Reiner Serienname (z. B. 'Fünf Freunde')", "album_artist")
        self._create_form_row(2, "Album (Folgentitel)", "TALB / album", "Format: '03 - Fünf Freunde und das Burgverlies'", "album")
        self._create_form_row(3, "Reiner Folgentitel", "TIT2 / title", "Folgentitel ohne Nummerierung für Plex", "episode_title")
        self._create_form_row(4, "Serie / Haupt-Interpret", "TPE1 / artist", "Reiner Serienname (z. B. 'Fünf Freunde')", "series")
        self._create_form_row(5, "Folgennummer / Track-Nr.", "TRCK / tracknumber", "Nummer der Folge (z. B. 3)", "series_part")
        self._create_form_row(6, "Erscheinungsjahr", "TDRC / year", "Veröffentlichungsjahr (z. B. 1978)", "year")
        self._create_form_row(7, "Genre", "TCON / genre", "Festes Genre für Hörspiele", "genre")

        # Separator for Tracks
        self.tracks_title = ctk.CTkLabel(self.form_scroll, text="Kapitel / Tracks", font=ctk.CTkFont(size=14, weight="bold"))
        self.tracks_title.grid(row=8, column=0, columnspan=3, padx=10, pady=(20, 10), sticky="w")

        # Frame to hold dynamic track rows
        self.tracks_container = ctk.CTkFrame(self.form_scroll, fg_color="transparent")
        self.tracks_container.grid(row=9, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
        self.tracks_container.grid_columnconfigure(1, weight=3) # clean title entry

        # Live Preview Card (Result after Rename/Merge)
        self.preview_card = ctk.CTkFrame(self.form_scroll, corner_radius=8)
        self.preview_card.grid(row=10, column=0, columnspan=3, sticky="nsew", padx=5, pady=(15, 10))

        preview_header = ctk.CTkLabel(self.preview_card, text="🔍 Live-Vorschau (Ziel-Ordner & MP3-Dateinamen nach Umbenennen):", font=ctk.CTkFont(size=13, weight="bold"))
        preview_header.pack(anchor="w", padx=12, pady=(10, 4))



        self.preview_textbox = ctk.CTkTextbox(self.preview_card, height=130, font=ctk.CTkFont(family="Consolas", size=11))
        self.preview_textbox.pack(fill="both", expand=True, padx=12, pady=(4, 10))

        # Cover & Action Panel (Right of Tab 2)
        self.cover_panel = ctk.CTkFrame(self.tab_edit, width=360)
        self.cover_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.cover_panel.grid_rowconfigure(1, weight=1)
        self.cover_panel.grid_columnconfigure(0, weight=1)

        self.cover_title = ctk.CTkLabel(self.cover_panel, text="Cover Art", font=ctk.CTkFont(size=14, weight="bold"))
        self.cover_title.grid(row=0, column=0, padx=10, pady=10)

        # Cover Image Canvas / Label
        self.cover_img_label = ctk.CTkLabel(self.cover_panel, text="Kein Cover geladen", fg_color="#2b2b2b", width=300, height=300)
        self.cover_img_label.grid(row=1, column=0, padx=15, pady=10, sticky="n")

        self.cover_status_lbl = ctk.CTkLabel(self.cover_panel, text="", text_color="gray")
        self.cover_status_lbl.grid(row=2, column=0, padx=10, pady=5)

        self.crop_cover_btn = ctk.CTkButton(self.cover_panel, text="✂ Cover zuschneiden...", command=self._open_crop_dialog, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.crop_cover_btn.grid(row=3, column=0, padx=20, pady=4, sticky="ew")

        self.chooser_cover_btn = ctk.CTkButton(self.cover_panel, text="🎨 Cover wählen (Varianten)...", command=self._open_cover_chooser, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.chooser_cover_btn.grid(row=4, column=0, padx=20, pady=4, sticky="ew")

        self.manual_cover_btn = ctk.CTkButton(self.cover_panel, text="Cover aus Datei laden...", command=self._load_manual_cover, state="disabled", fg_color="#2d88ad", hover_color="#1e5e78")
        self.manual_cover_btn.grid(row=5, column=0, padx=20, pady=4, sticky="ew")

        self.apply_btn = ctk.CTkButton(self.cover_panel, text="Speichern & Umbenennen", command=self._apply_metadata, state="disabled", fg_color="#1f538d", hover_color="#143960")
        self.apply_btn.grid(row=6, column=0, padx=20, pady=(15, 20), sticky="ew")


    def _create_form_row(self, row_idx: int, label_text: str, id3_tag: str, hint_text: str, key: str):
        # Column 0: Tag Label (align to top-right of entries)
        label_lbl = ctk.CTkLabel(self.form_scroll, text=label_text, font=ctk.CTkFont(weight="bold"))
        label_lbl.grid(row=row_idx, column=0, padx=10, pady=(8, 0), sticky="ne")

        # Column 1: Read-only current MP3 tag (Vorher)
        curr_frame = ctk.CTkFrame(self.form_scroll, fg_color="transparent")
        curr_frame.grid(row=row_idx, column=1, padx=8, pady=4, sticky="ew")
        curr_frame.grid_columnconfigure(0, weight=1)

        curr_ent = ctk.CTkEntry(curr_frame, state="disabled", fg_color=("#e2e8f0", "#1e293b"), text_color="gray")
        curr_ent.pack(fill="x")
        self.current_tag_entries[key] = curr_ent

        # Blue ID3 label underneath the current value entry
        ctk.CTkLabel(curr_frame, text=f"ID3: {id3_tag}", font=ctk.CTkFont(size=10), text_color="#3b82f6").pack(anchor="w", pady=(1, 0))

        # Column 2: LLM Proposal entry (Nachher - editable)
        entry_frame = ctk.CTkFrame(self.form_scroll, fg_color="transparent")
        entry_frame.grid(row=row_idx, column=2, padx=8, pady=4, sticky="ew")
        entry_frame.grid_columnconfigure(0, weight=1)

        ent = ctk.CTkEntry(entry_frame)
        ent.pack(fill="x")
        ent.bind("<KeyRelease>", lambda e: self._update_live_preview())

        ctk.CTkLabel(entry_frame, text=hint_text, font=ctk.CTkFont(size=10), text_color="gray").pack(anchor="w", pady=(1, 0))
        self.form_entries[key] = ent

    def _load_config_defaults(self):
        # Load API settings
        self.api_url_ent.insert(0, self.loaded_settings.get("api_url", config.LLM_API_BASE_URL))
        self.api_key_ent.insert(0, self.loaded_settings.get("api_key", config.LLM_API_KEY))
        self.model_ent.insert(0, self.loaded_settings.get("model_id", config.LLM_MODEL_ID))

        # Load options checkboxes
        self.dry_run_var.set(self.loaded_settings.get("dry_run", True))
        self.merge_var.set(self.loaded_settings.get("merge", False))
        self.move_tracks_var.set(self.loaded_settings.get("move_tracks", False))
        self.delete_tracks_var.set(self.loaded_settings.get("delete_tracks", False))
        self.rename_folder_var.set(self.loaded_settings.get("rename_folder", True))
        self.parent_series_var.set(self.loaded_settings.get("parent_series", True))
        self.cover_var.set(self.loaded_settings.get("cover", True))

        # Handle enabling/disabling checkbox states dynamically based on the loaded merge option
        self._on_merge_toggle()

        # Load last target directory if exists and still valid
        last_dir = self.loaded_settings.get("target_dir")
        if last_dir and Path(last_dir).exists():
            self.target_dir = last_dir
            self.folder_lbl.configure(text=last_dir)
            self._scan_folder(reset_states=True)

        self._test_llm_connection()

    def _test_llm_connection(self):
        """Triggers asynchronous LLM connection test."""
        self.llm_status_lbl.configure(text="🟡 Verbindung wird geprüft...", text_color="orange")
        threading.Thread(target=self._run_test_connection_thread, daemon=True).start()

    def _run_test_connection_thread(self):
        """Tests HTTP connection to LLM API endpoint."""
        url = self.api_url_ent.get().strip()
        try:
            import urllib.request
            # Parse host/url for ping
            req = urllib.request.Request(url, headers={"User-Agent": "HoerspielTag"})
            try:
                with urllib.request.urlopen(req, timeout=4) as resp:
                    code = resp.getcode()
            except urllib.error.HTTPError as he:
                # 401/404/405 still means the server is reachable and listening!
                code = he.code

            self.after(0, lambda: self.llm_status_lbl.configure(text=f"🟢 LLM erreichbar (HTTP {code})", text_color="#2b712b"))
        except Exception as err:
            err_str = str(err)
            short_err = err_str[:28] + "..." if len(err_str) > 28 else err_str
            self.after(0, lambda: self.llm_status_lbl.configure(text=f"🔴 Nicht erreichbar: {short_err}", text_color="#d9534f"))

    def _setup_drag_and_drop(self):
        """Registers Drag & Drop targets for windows and frames."""
        try:
            for widget in [self, self.drop_frame, self.drop_label, self.scan_textbox, self.sidebar]:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind('<<Drop>>', self._on_drop_folder)
        except Exception as e:
            print(f"Drag & Drop Setup Info: {e}")

    def _on_drop_folder(self, event):
        """Handles folder/file drag and drop events."""
        raw_data = event.data
        if not raw_data:
            return

        try:
            paths = self.tk.splitlist(raw_data)
        except Exception:
            paths = [raw_data.strip("{}")]

        if not paths:
            return

        resolved_paths = []
        for p in paths:
            path_obj = Path(p).resolve()
            if path_obj.exists():
                if path_obj.is_file():
                    resolved_paths.append(path_obj.parent)
                else:
                    resolved_paths.append(path_obj)

        if not resolved_paths:
            return

        first_path = resolved_paths[0]
        if len(paths) > 1:
            target = first_path.parent
            self.dragged_paths = {str(rp) for rp in resolved_paths}
        else:
            target = first_path
            self.dragged_paths = {str(first_path)}

        self.target_dir = str(target)
        self.folder_lbl.configure(text=str(target))
        self.scan_btn.configure(state="normal")
        self._scan_folder()

    # ================= EVENT HANDLERS & LOGIC =================

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dragged_paths = None
            self.target_dir = folder
            self.folder_lbl.configure(text=folder)
            self.scan_btn.configure(state="normal")
            self._scan_folder()

    def _initialize_album_states(self, reset: bool = False):
        """Initializes default scanned state for all folders in self.scan_results so navigation never wipes data."""
        if reset or not hasattr(self, "album_states") or self.album_states is None:
            self.album_states = {}
        for album in self.scan_results:
            folder_path = album["folder_path"]
            if folder_path in self.album_states:
                continue
            orig_tracks = album["tracks"]

            album_artist = ""
            album_name = album["folder_name"]
            series_part = ""

            # Pad prefix number to 2 digits if matches (e.g. "4 - Title" -> "04 - Title")
            import re
            match = re.match(r"^(\d+)\s*-\s*(.*)$", album_name)
            if match:
                num_str, title_str = match.groups()
                album_name = f"{int(num_str):02d} - {title_str}"
                series_part = num_str.zfill(2)

            year_str = ""
            genre_str = "Hörspiel"

            if orig_tracks:
                t0 = orig_tracks[0]
                album_artist = t0.get("album_artist") or t0.get("artist") or ""
                raw_album = t0.get("album") or album["folder_name"]
                match_raw = re.match(r"^(\d+)\s*-\s*(.*)$", raw_album)
                if match_raw:
                    num_str, title_str = match_raw.groups()
                    album_name = f"{int(num_str):02d} - {title_str}"
                    series_part = num_str.zfill(2)
                else:
                    album_name = raw_album

                if t0.get("year"):
                    year_str = str(t0["year"])
                if t0.get("genre"):
                    genre_str = t0["genre"]

            form_data = {
                "album_artist": album_artist,
                "album": album_name,
                "episode_title": album_name.split(" - ", 1)[-1] if " - " in album_name else album_name,
                "series": album_artist,
                "series_part": series_part,
                "year": year_str,
                "genre": genre_str
            }

            track_rows = []
            for i, track in enumerate(orig_tracks):
                row_num = i + 1
                clean_title_val = track["title"] or Path(track["filename"]).stem
                track_num_val = track["track_number"] or row_num

                track_rows.append({
                    "original_filename": track["filename"],
                    "filepath": track["filepath"],
                    "clean_title": clean_title_val,
                    "track_number": track_num_val
                })

            self.album_states[folder_path] = {
                "metadata": None,
                "form_data": form_data,
                "track_rows": track_rows,
                "cover_bytes": None,
                "cover_status": "Eingebettetes Cover vorhanden" if album["has_embedded_cover"] else "Kein Cover geladen",
                "cover_status_color": "#2b712b" if album["has_embedded_cover"] else "gray"
            }

    def _clear_cache(self):
        """Clears all cached album states and resets the editor."""
        self.album_states = {}
        self.cover_bytes = None
        self._clear_editor()
        self._scan_folder(reset_states=True)
        
        # Show temporary success message
        self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
        self.loading_lbl.configure(text="🧹 Cache erfolgreich geleert!", text_color="#2b712b")
        self.after(3000, self._clear_status)

    def _scan_folder(self, reset_states=True, keep_index=False):
        if not self.target_dir:
            return

        if not Path(self.target_dir).exists():
            self.scan_textbox.delete("0.0", tk.END)
            self.scan_textbox.insert("0.0", f"Fehler: Der ausgewählte Ordner existiert nicht mehr:\n{self.target_dir}\n\nBitte wähle den Ordner erneut aus.")
            self.folder_lbl.configure(text="Ordner existiert nicht mehr", text_color="red")
            self.scan_results = []
            self._update_album_nav()
            self._clear_editor()
            return

        # Store the currently selected album's folder path
        old_folder_path = None
        if keep_index and self.scan_results and self.current_album_idx in range(len(self.scan_results)):
            old_folder_path = self.scan_results[self.current_album_idx]["folder_path"]

        self.scan_textbox.delete("0.0", tk.END)
        self.scan_textbox.insert("0.0", "Scanne Ordner Struktur...\n")

        try:
            results = AudioScanner.scan_directory(self.target_dir)
            if hasattr(self, "dragged_paths") and self.dragged_paths:
                results = [r for r in results if str(Path(r["folder_path"]).resolve()) in self.dragged_paths]
            self.scan_results = results

            if not self.scan_results:
                self.scan_textbox.insert(tk.END, "Keine MP3-Dateien gefunden.")
                self.analyze_btn.configure(state="disabled")
                return

            self.analyze_btn.configure(state="normal")
            
            for idx, album in enumerate(self.scan_results):
                self.scan_textbox.insert(tk.END, f"\n📁 Ordner: {album['folder_name']}\n")
                self.scan_textbox.insert(tk.END, f"   Relativer Pfad: {album['relative_folder_path']}\n")
                self.scan_textbox.insert(tk.END, f"   Tracks: {len(album['tracks'])} MP3s\n")
                self.scan_textbox.insert(tk.END, f"   Eingebettetes Cover vorhanden: {'Ja' if album['has_embedded_cover'] else 'Nein'}\n")
                self.scan_textbox.insert(tk.END, f"   Eingebettete Kapitel vorhanden: {'Ja (kann getrennt werden)' if album.get('has_chapters') else 'Nein'}\n")
            
            self.scan_textbox.insert(tk.END, f"\nInsgesamt {len(self.scan_results)} Ordner mit Hörspielen gefunden.")
            
            # Find the new index of the previously selected album path to keep it selected
            target_idx = 0
            if keep_index and old_folder_path:
                for idx, album in enumerate(self.scan_results):
                    if album["folder_path"] == old_folder_path:
                        target_idx = idx
                        break
            
            self.current_album_idx = target_idx

            # Initialize states for all folders immediately upon scanning
            self._initialize_album_states(reset=reset_states)
            self._update_album_nav()
            self._restore_album_state(self.current_album_idx)

        except Exception as e:
            messagebox.showerror("Fehler beim Scannen", str(e))

    def _update_album_nav(self):
        if not self.scan_results:
            self.album_status_lbl.configure(text="Keine Alben geladen")
            self.nav_prev_btn.configure(state="disabled")
            self.nav_next_btn.configure(state="disabled")
            return

        total = len(self.scan_results)
        curr = self.current_album_idx + 1
        album_name = self.scan_results[self.current_album_idx]["folder_name"]
        self.album_status_lbl.configure(text=f"Ordner {curr}/{total}: {album_name}")

        self.nav_prev_btn.configure(state="normal" if self.current_album_idx > 0 else "disabled")
        self.nav_next_btn.configure(state="normal" if self.current_album_idx < total - 1 else "disabled")

    def _save_current_album_state(self):
        """Saves current editor form fields, track titles, track order, and cover data for current_album_idx."""
        if not self.scan_results or self.current_album_idx not in range(len(self.scan_results)):
            return

        folder_path = self.scan_results[self.current_album_idx]["folder_path"]
        form_data = {k: ent.get() for k, ent in self.form_entries.items()}

        track_data = []
        for row in self.track_rows:
            num = row.get("track_number", 1)
            if "number_entry" in row and hasattr(row["number_entry"], "get"):
                try:
                    num = int(row["number_entry"].get())
                except Exception:
                    pass

            title = row.get("clean_title", "")
            if "title_entry" in row and hasattr(row["title_entry"], "get"):
                title = row["title_entry"].get()

            track_data.append({
                "original_filename": row["original_filename"],
                "filepath": row["filepath"],
                "clean_title": title,
                "track_number": num
            })

        self.album_states[folder_path] = {
            "metadata": self.current_metadata,
            "form_data": form_data,
            "track_rows": track_data,
            "cover_bytes": self.cover_bytes,
            "cover_status": self.cover_status_lbl.cget("text"),
            "cover_status_color": self.cover_status_lbl.cget("text_color")
        }

    def _restore_album_state(self, idx: int) -> bool:
        """Restores saved form fields, track rows, and cover image for album index idx."""
        if not self.scan_results or idx not in range(len(self.scan_results)):
            return False

        folder_path = self.scan_results[idx]["folder_path"]
        if folder_path not in self.album_states:
            return False

        state = self.album_states[folder_path]
        self._clear_editor()

        self.current_metadata = state.get("metadata")
        self.cover_bytes = state.get("cover_bytes")

        # Restore form inputs (Nachher - LLM Proposal)
        form_data = state.get("form_data", {})
        for k, val in form_data.items():
            if k in self.form_entries:
                self.form_entries[k].delete(0, tk.END)
                self.form_entries[k].insert(0, val)

        # Populate current MP3 tags (Vorher) from scanned files
        album_data = self.scan_results[idx]
        orig_tracks = album_data.get("tracks", [])
        t0 = orig_tracks[0] if orig_tracks else {}

        orig_tags = {
            "album_artist": t0.get("album_artist") or "",
            "album": t0.get("album") or "",
            "episode_title": t0.get("title") or "",
            "series": t0.get("artist") or "",
            "series_part": str(t0.get("track_number")) if t0.get("track_number") is not None else "",
            "year": str(t0.get("year")) if t0.get("year") is not None else "",
            "genre": t0.get("genre") or ""
        }

        for k, curr_val in orig_tags.items():
            if k in self.current_tag_entries:
                self.current_tag_entries[k].configure(state="normal")
                self.current_tag_entries[k].delete(0, tk.END)
                display_val = curr_val if curr_val else "(Kein Tag)"
                self.current_tag_entries[k].insert(0, display_val)
                self.current_tag_entries[k].configure(state="disabled")

        # Restore cover image & status
        if self.cover_bytes:
            self._display_cover_image(self.cover_bytes)
            self.cover_status_lbl.configure(
                text=state.get("cover_status", "Cover geladen"),
                text_color=state.get("cover_status_color", "#2b712b")
            )
        else:
            self.current_ctk_image = None
            try:
                self.cover_img_label.configure(text="Kein Cover geladen", image="")
            except Exception:
                pass
            self.cover_status_lbl.configure(
                text=state.get("cover_status", ""),
                text_color=state.get("cover_status_color", "gray")
            )

        # Restore track rows
        self.track_rows = state.get("track_rows", [])
        if self.track_rows:
            self._render_track_rows()
            self.apply_btn.configure(state="normal")
            self.manual_cover_btn.configure(state="normal")
            self.chooser_cover_btn.configure(state="normal")

        self._update_live_preview()
        return True

    def _prev_album(self):
        if self.current_album_idx > 0:
            self._save_current_album_state()
            self.current_album_idx -= 1
            self._update_album_nav()
            if not self._restore_album_state(self.current_album_idx):
                self._clear_editor()

    def _next_album(self):
        if self.current_album_idx < len(self.scan_results) - 1:
            self._save_current_album_state()
            self.current_album_idx += 1
            self._update_album_nav()
            if not self._restore_album_state(self.current_album_idx):
                self._clear_editor()

    def _clear_editor(self):
        # Clear fields
        for ent in self.form_entries.values():
            ent.delete(0, tk.END)
        for ent in self.current_tag_entries.values():
            ent.configure(state="normal")
            ent.delete(0, tk.END)
            ent.configure(state="disabled")
        
        # Clear cover safely without pyimage TclError
        self.current_ctk_image = None
        try:
            self.cover_img_label.configure(text="Kein Cover geladen", image="")
        except Exception:
            pass
        self.cover_status_lbl.configure(text="")
        self.cover_bytes = None
        self.current_metadata = None
        
        # Clear dynamic track rows
        for widget in self.tracks_container.winfo_children():
            widget.destroy()
        
        self.track_rows = []
        self.apply_btn.configure(state="disabled")
        self.manual_cover_btn.configure(state="disabled")
        self.chooser_cover_btn.configure(state="disabled")
        self.crop_cover_btn.configure(state="disabled")

    def _open_cover_chooser(self):
        """Opens modal dialog for choosing between multiple candidate album covers from iTunes."""
        artist = self.form_entries["album_artist"].get()
        album = self.form_entries["album"].get()
        title = self.form_entries["series"].get() or album

        def fetch_and_open():
            candidates = CoverDownloader.search_cover_candidates(artist, album, title)
            def open_dialog():
                def on_selected(new_bytes):
                    self.cover_bytes = new_bytes
                    self._display_cover_image(new_bytes)
                    self.cover_status_lbl.configure(text="Cover aus iTunes-Varianten gewählt", text_color="#2b712b")
                    self._save_current_album_state()

                CoverChooserDialog(self, candidates, on_selected)
            self.after(0, open_dialog)

        threading.Thread(target=fetch_and_open, daemon=True).start()

    def _start_analysis(self):
        if not self.scan_results or self.is_processing:
            return

        self._save_current_album_state()
        self.is_processing = True
        self.analyze_btn.configure(state="disabled", text="Analysiere...")
        
        # Start loading progress bar in bottom status bar
        self.progress_bar.grid(row=0, column=2, padx=10, pady=2, sticky="e")
        self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
        self.loading_lbl.configure(text="⏳ Starte Batch-Analyse...")
        self.progress_bar.start()

        self.content_tabview.set("Metadaten bearbeiten und taggen")

        # Run in thread so GUI doesn't freeze
        threading.Thread(target=self._run_analysis_thread, daemon=True).start()

    def _stop_loading_indicator(self):
        """Stops and hides the header loading progress bar."""
        self.progress_bar.stop()
        self.progress_bar.grid_remove()
        self.loading_lbl.grid_remove()
        self.loading_lbl.configure(text="")

    def _clear_status(self):
        """Hides the status label and resets color."""
        self.loading_lbl.grid_remove()
        self.loading_lbl.configure(text_color="#1f538d")

    @staticmethod
    def _clean_track_title(raw_title: str, series_name: Optional[str] = None) -> str:
        if not raw_title:
            return ""
        import re
        from encoding_utils import fix_encoding_corruptions
        raw_title = fix_encoding_corruptions(raw_title)
        # Strip track number prefixes like '01 - ', '01. ', 'Folge 01 - ', 'Track 01 - '
        cleaned = re.sub(r'^(?:folge|track|cd|disk)?\s*\d+[\s\-_:]*', '', raw_title, flags=re.IGNORECASE).strip()
        if series_name and series_name.strip():
            s_name = series_name.strip()
            if cleaned.lower().startswith(s_name.lower()):
                cleaned = cleaned[len(s_name):].lstrip(" -:_")
        return fix_encoding_corruptions(cleaned or raw_title)

    def _run_analysis_thread(self):
        try:
            # Re-read/override API config from inputs
            config.LLM_API_BASE_URL = self.api_url_ent.get()
            config.LLM_API_KEY = self.api_key_ent.get()
            config.LLM_MODEL_ID = self.model_ent.get()

            self.llm_client = LLMClient()
            total = len(self.scan_results)

            for idx in range(total):
                album = self.scan_results[idx]
                folder_path = album["folder_path"]
                folder_name = album["folder_name"]

                self.after(0, lambda i=idx+1, t=total, fn=folder_name: self.loading_lbl.configure(
                    text=f"⏳ Analysiere Ordner {i}/{t}: {fn}..."
                ))

                # 1. Query LLM for this folder
                metadata = self.llm_client.analyze_album(folder_name, album["tracks"])

                # 2. Cover Art search for this folder
                cover_bytes = None
                cover_status = "iTunes-Suche erfolglos"
                cover_color = "#7a2b2b"

                if self.cover_var.get() and not album["has_embedded_cover"]:
                    cover_url = CoverDownloader.search_cover_url(metadata.album_artist, metadata.album, getattr(metadata, 'episode_title', None))
                    if cover_url:
                        cover_bytes = CoverDownloader.download_image(cover_url)
                        cover_status = "Cover von iTunes geladen"
                        cover_color = "#2b712b"

                if not cover_bytes:
                    local_cover = self._find_local_cover(folder_path)
                    if local_cover:
                        try:
                            with open(local_cover, "rb") as f:
                                cover_bytes = f.read()
                            cover_status = f"Lokales Cover: {Path(local_cover).name}"
                            cover_color = "gray"
                        except Exception:
                            pass

                # Build track rows data for this folder
                orig_tracks = album["tracks"]
                episode_num = metadata.series_part or metadata.episode_number
                episode_title = metadata.episode_title or (metadata.album.split(" - ", 1)[-1] if " - " in metadata.album else metadata.album)
                series_name = metadata.series_name or metadata.album_artist or metadata.series

                track_rows = []
                for i_t, track in enumerate(orig_tracks):
                    row_num = i_t + 1
                    prop = next((t for t in metadata.tracks if t.original_filename == track["filename"]), None)
                    raw_clean = prop.clean_title if prop else track["title"] or Path(track["filename"]).stem
                    clean_title_val = self._clean_track_title(raw_clean, series_name)
                    track_num_val = prop.track_number if prop else (track["track_number"] or row_num)

                    # If folder has only 1 file (single episode MP3), use episode_title directly!
                    if len(orig_tracks) == 1:
                        clean_title_val = episode_title
                        if episode_num:
                            track_num_val = episode_num

                    track_rows.append({
                        "original_filename": track["filename"],
                        "filepath": track["filepath"],
                        "clean_title": clean_title_val,
                        "track_number": track_num_val
                    })

                form_data = {
                    "album_artist": metadata.album_artist,
                    "album": metadata.album,
                    "episode_title": episode_title,
                    "series": metadata.series,
                    "series_part": str(episode_num) if episode_num is not None else "",
                    "year": str(metadata.year) if metadata.year is not None else "",
                    "genre": metadata.genre
                }

                # Save state per folder_path
                self.album_states[folder_path] = {
                    "metadata": metadata,
                    "form_data": form_data,
                    "track_rows": track_rows,
                    "cover_bytes": cover_bytes,
                    "cover_status": cover_status,
                    "cover_status_color": cover_color
                }

                # If this is the active album in UI, render it immediately
                if idx == self.current_album_idx:
                    self.after(0, lambda target_idx=idx: self._restore_album_state(target_idx))

            def on_batch_done():
                self.content_tabview.set("Metadaten bearbeiten und taggen")
                self._restore_album_state(self.current_album_idx)
                
                # Show status message
                self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
                self.loading_lbl.configure(
                    text=f"✓ {total} Ordner erfolgreich analysiert!",
                    text_color="#2b712b"
                )
                self.after(6000, self._clear_status)

            self.after(0, on_batch_done)

        except Exception as e:
            self.after(0, self._handle_analysis_error, str(e))
        finally:
            self.is_processing = False
            self.after(0, lambda: self.progress_bar.stop())
            self.after(0, lambda: self.progress_bar.grid_remove())
            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="LLM-Analyse starten"))

    def _display_metadata_proposal(self, metadata: AlbumMetadata, cover_url: Optional[str]):
        # Populate Form fields
        episode_num = metadata.series_part or metadata.episode_number
        episode_title = metadata.episode_title or (metadata.album.split(" - ", 1)[-1] if " - " in metadata.album else metadata.album)

        self.form_entries["album_artist"].insert(0, metadata.album_artist)
        self.form_entries["album"].insert(0, metadata.album)
        if "episode_title" in self.form_entries:
            self.form_entries["episode_title"].insert(0, episode_title)
        self.form_entries["series"].insert(0, metadata.series)
        self.form_entries["series_part"].insert(0, str(episode_num) if episode_num is not None else "")
        self.form_entries["year"].insert(0, str(metadata.year) if metadata.year is not None else "")
        self.form_entries["genre"].insert(0, metadata.genre)

        # Populate Cover art preview
        if self.cover_bytes:
            self._display_cover_image(self.cover_bytes)
            self.cover_status_lbl.configure(text="Cover von iTunes geladen", text_color="#2b712b")
        else:
            album_folder = self.scan_results[self.current_album_idx]["folder_path"]
            local_cover = self._find_local_cover(album_folder)
            if local_cover:
                try:
                    with open(local_cover, "rb") as f:
                        self.cover_bytes = f.read()
                    self._display_cover_image(self.cover_bytes)
                    self.cover_status_lbl.configure(text=f"Lokales Cover gefunden: {Path(local_cover).name}", text_color="gray")
                except Exception:
                    pass
            
            if not self.cover_bytes:
                self.cover_img_label.configure(text="Kein Cover gefunden", image=None)
                self.cover_status_lbl.configure(text="iTunes-Suche erfolglos", text_color="#7a2b2b")
                self.crop_cover_btn.configure(state="disabled")

        # Enable manual cover & chooser buttons
        self.manual_cover_btn.configure(state="normal")
        self.chooser_cover_btn.configure(state="normal")

        # Build track rows data
        orig_tracks = self.scan_results[self.current_album_idx]["tracks"]
        series_name = metadata.series_name or metadata.album_artist or metadata.series
        self.track_rows = []
        for i, track in enumerate(orig_tracks):
            row_num = i + 1
            prop = next((t for t in metadata.tracks if t.original_filename == track["filename"]), None)
            raw_clean = prop.clean_title if prop else track["title"] or Path(track["filename"]).stem
            clean_title_val = self._clean_track_title(raw_clean, series_name)
            track_num_val = prop.track_number if prop else (track["track_number"] or row_num)

            # If folder has only 1 file (single episode MP3), use episode_title directly!
            if len(orig_tracks) == 1:
                clean_title_val = episode_title
                if episode_num:
                    track_num_val = episode_num

            self.track_rows.append({
                "original_filename": track["filename"],
                "filepath": track["filepath"],
                "clean_title": clean_title_val,
                "track_number": track_num_val
            })

        self._render_track_rows()
        self.apply_btn.configure(state="normal")

        # Save analyzed state for current album so switching navigation keeps it
        self._save_current_album_state()

    def _render_track_rows(self):
        """Renders track rows with reorder buttons and left-aligned filename labels."""
        for widget in self.tracks_container.winfo_children():
            widget.destroy()

        # Grid headers
        ctk.CTkLabel(self.tracks_container, text="Reihenfolge", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=2, pady=2)
        ctk.CTkLabel(self.tracks_container, text="Originale Datei", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ctk.CTkLabel(self.tracks_container, text="Nr.", font=ctk.CTkFont(weight="bold"), width=35).grid(row=0, column=2, padx=5, pady=2)
        ctk.CTkLabel(self.tracks_container, text="Bereinigter Titel", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5, pady=2, sticky="ew")

        self.tracks_container.grid_columnconfigure(3, weight=3)

        for i, row in enumerate(self.track_rows):
            row_num = i + 1

            # Move Up / Down frame
            move_frame = ctk.CTkFrame(self.tracks_container, fg_color="transparent")
            move_frame.grid(row=row_num, column=0, padx=2, pady=2)

            btn_up = ctk.CTkButton(
                move_frame, text="▲", width=22, height=22,
                state="normal" if i > 0 else "disabled",
                command=lambda idx=i: self._move_track(idx, -1)
            )
            btn_up.pack(side="left", padx=1)

            btn_dn = ctk.CTkButton(
                move_frame, text="▼", width=22, height=22,
                state="normal" if i < len(self.track_rows) - 1 else "disabled",
                command=lambda idx=i: self._move_track(idx, 1)
            )
            btn_dn.pack(side="left", padx=1)

            # Original filename label (fixed left alignment & wrapping)
            orig_lbl = ctk.CTkLabel(
                self.tracks_container,
                text=row["original_filename"],
                anchor="w",
                justify="left",
                wraplength=220
            )
            orig_lbl.grid(row=row_num, column=1, padx=5, pady=2, sticky="w")

            # Track number entry
            num_ent = ctk.CTkEntry(self.tracks_container, width=40)
            num_ent.insert(0, str(row.get("track_number", row_num)))
            num_ent.grid(row=row_num, column=2, padx=5, pady=2)
            num_ent.bind("<KeyRelease>", lambda e: self._update_live_preview())

            # Clean title entry
            title_ent = ctk.CTkEntry(self.tracks_container)
            title_ent.insert(0, row.get("clean_title", ""))
            title_ent.grid(row=row_num, column=3, padx=5, pady=2, sticky="ew")
            title_ent.bind("<KeyRelease>", lambda e: self._update_live_preview())

            # Link widgets in row dictionary
            row["number_entry"] = num_ent
            row["title_entry"] = title_ent

        self._update_live_preview()

    def _on_merge_toggle(self):
        self._update_live_preview()
        if self.merge_var.get():
            self.move_tracks_cb.configure(state="normal")
            self.delete_tracks_cb.configure(state="normal")
        else:
            self.move_tracks_var.set(False)
            self.delete_tracks_var.set(False)
            self.move_tracks_cb.configure(state="disabled")
            self.delete_tracks_cb.configure(state="disabled")

    def _on_move_tracks_toggle(self):
        if self.move_tracks_var.get():
            self.delete_tracks_var.set(False)

    def _on_delete_tracks_toggle(self):
        if self.delete_tracks_var.get():
            self.move_tracks_var.set(False)

    def _update_live_preview(self):
        """Updates live preview of target folder name and target MP3 file names as a directory tree."""
        if not hasattr(self, "preview_textbox"):
            return

        album_artist = self.form_entries["album_artist"].get().strip() if "album_artist" in self.form_entries else ""
        album = self.form_entries["album"].get().strip() if "album" in self.form_entries else ""
        
        # Ensure single digit prefix in album name is padded to 2 digits for preview (e.g. "4 - " -> "04 - ")
        import re
        match = re.match(r"^(\d+)\s*-\s*(.*)$", album)
        if match:
            num_str, title_str = match.groups()
            album = f"{int(num_str):02d} - {title_str}"
        folder_path_name = self.scan_results[self.current_album_idx]["folder_name"] if (self.scan_results and self.current_album_idx in range(len(self.scan_results))) else "Unbenannter Ordner"

        # Determine target folder name
        ep_folder_name = album if (self.rename_folder_var.get() and album) else folder_path_name
        if not ep_folder_name:
            ep_folder_name = f"{album_artist} {album}" if (album_artist and album) else (album or "Unbenannter Ordner")

        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            ep_folder_name = ep_folder_name.replace(char, "_")

        self.preview_textbox.delete("0.0", tk.END)

        tree_lines = []
        indent = ""

        # Build tree structure
        if self.parent_series_var.get() and album_artist:
            clean_series = album_artist
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                clean_series = clean_series.replace(char, "_")
            tree_lines.append(f"📁 {clean_series}")
            tree_lines.append(f"└── 📁 {ep_folder_name}")
            indent = "     "
        else:
            tree_lines.append(f"📁 {ep_folder_name}")
            indent = "└── "

        if self.merge_var.get():
            merged_filename = f"{album}.mp3" if album else "Hörspiel_Gesamt.mp3"
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                merged_filename = merged_filename.replace(char, "_")
            
            tree_lines.append(f"{indent}└── 📄 {merged_filename} (Zusammengefügt)")
            
            # Show embedded chapters
            child_indent = indent + "     "
            chapter_count = len(self.track_rows)
            for idx, row in enumerate(self.track_rows, 1):
                clean_t = row["title_entry"].get() if ("title_entry" in row and hasattr(row["title_entry"], "get")) else row.get("clean_title", "")
                is_last_chapter = (idx == chapter_count)
                bullet = "└── " if is_last_chapter else "├── "
                tree_lines.append(f"{child_indent}{bullet}📌 Kapitel {idx:02d}: {clean_t}")
        else:
            file_count = len(self.track_rows)
            for idx, row in enumerate(self.track_rows, 1):
                clean_t = row["title_entry"].get() if ("title_entry" in row and hasattr(row["title_entry"], "get")) else row.get("clean_title", "")
                try:
                    num_val = int(row["number_entry"].get()) if ("number_entry" in row and hasattr(row["number_entry"], "get")) else row.get("track_number", idx)
                except Exception:
                    num_val = idx

                filename = f"{num_val:02d} - {clean_t}.mp3"
                is_last_file = (idx == file_count)
                bullet = "└── " if is_last_file else "├── "
                tree_lines.append(f"{indent}{bullet}📄 {filename}")

        self.preview_textbox.insert("0.0", "\n".join(tree_lines))

    def _move_track(self, index: int, direction: int):
        """Swaps track order up or down."""
        # Preserve user entries before swapping
        for row in self.track_rows:
            try:
                row["track_number"] = int(row["number_entry"].get())
            except (ValueError, AttributeError):
                pass
            if "title_entry" in row and hasattr(row["title_entry"], "get"):
                row["clean_title"] = row["title_entry"].get()

        target_idx = index + direction
        if 0 <= target_idx < len(self.track_rows):
            self.track_rows[index], self.track_rows[target_idx] = self.track_rows[target_idx], self.track_rows[index]
            for i, r in enumerate(self.track_rows):
                r["track_number"] = i + 1
            self._render_track_rows()
            self._update_live_preview()

    def _find_local_cover(self, folder: str) -> Optional[str]:
        for name in ["cover.jpg", "cover.png", "folder.jpg", "folder.png", "front.jpg", "front.png"]:
            p = Path(folder) / name
            if p.exists() and p.is_file():
                return str(p)
        return None

    def _display_cover_image(self, img_bytes: bytes):
        try:
            image = Image.open(io.BytesIO(img_bytes))
            # Resize image keeping aspect ratio
            image.thumbnail((300, 300))
            self.current_ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(image.width, image.height))
            self.cover_img_label.configure(image=self.current_ctk_image, text="")
            self.crop_cover_btn.configure(state="normal")
        except Exception as e:
            self.current_ctk_image = None
            try:
                self.cover_img_label.configure(image="", text="Fehler beim Rendern")
            except Exception:
                pass
            self.crop_cover_btn.configure(state="disabled")

    def _open_crop_dialog(self):
        """Opens interactive cover crop modal."""
        if not self.cover_bytes:
            return

        def on_cropped(new_bytes):
            self.cover_bytes = new_bytes
            self._display_cover_image(self.cover_bytes)
            self.cover_status_lbl.configure(text="Cover zugeschnitten", text_color="#2b712b")

        CoverCropDialog(self, self.cover_bytes, on_cropped)

    def _load_manual_cover(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png")])
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    self.cover_bytes = f.read()
                self._display_cover_image(self.cover_bytes)
                self.cover_status_lbl.configure(text=f"Manuelles Cover: {Path(file_path).name}", text_color="#1f538d")
            except Exception as e:
                messagebox.showerror("Fehler beim Laden", str(e))

    def _handle_analysis_error(self, err_msg: str):
        self.loading_lbl.grid_remove()
        messagebox.showerror("LLM-Analyse Fehler", f"Die LLM-Analyse schlug fehl:\n{err_msg}")
        self.scan_textbox.insert(tk.END, f"\n❌ LLM-Analyse fehlgeschlagen: {err_msg}")
        self.content_tabview.set("Scannen und Ordnerstruktur")

    def _apply_metadata(self):
        if not self.scan_results or not self.current_metadata:
            return

        album = self.scan_results[self.current_album_idx]
        is_dry_run = self.dry_run_var.get()

        # Build output log message
        log_msgs = []
        log_msgs.append(f"=== {'TESTLAUF (Dry-Run)' if is_dry_run else 'SCHREIBOPERATION'} ===")
        
        album_artist = self.form_entries["album_artist"].get()
        album_name = self.form_entries["album"].get()
        
        # Ensure single digit prefix in album name is padded to 2 digits (e.g. "4 - " -> "04 - ")
        import re
        match = re.match(r"^(\d+)\s*-\s*(.*)$", album_name)
        if match:
            num_str, title_str = match.groups()
            album_name = f"{int(num_str):02d} - {title_str}"

        genre = self.form_entries["genre"].get()
        
        year_str = self.form_entries["year"].get()
        year = int(year_str) if year_str.isdigit() else None

        log_msgs.append(f"Album-Interpret: {album_artist}")
        log_msgs.append(f"Album (Folge):  {album_name}")
        log_msgs.append(f"Genre:          {genre}")
        log_msgs.append(f"Jahr:           {year}")

        # Target changes structure
        changes = []
        for row in self.track_rows:
            orig_filename = row["original_filename"]
            filepath = row["filepath"]
            
            try:
                track_num = int(row["number_entry"].get())
            except ValueError:
                messagebox.showerror("Ungültige Eingabe", "Track-Nummern müssen Zahlen sein!")
                return
                
            clean_title = row["title_entry"].get()
            new_filename = f"{track_num:02d} - {clean_title}.mp3"

            changes.append({
                "orig_filename": orig_filename,
                "filepath": filepath,
                "track_number": track_num,
                "clean_title": clean_title,
                "new_filename": new_filename
            })

        # Sort changes strictly by assigned track_number
        changes.sort(key=lambda x: x["track_number"])

        for change in changes:
            log_msgs.append(f"\n* Track {change['track_number']:02d}: {change['orig_filename']}")
            log_msgs.append(f"  -> Neuer Name:  {change['new_filename']}")
            log_msgs.append(f"  -> Bereinigt:   {change['clean_title']}")

        if self.merge_var.get():
            log_msgs.append("\n" + "=" * 55)
            log_msgs.append("🔗 VERLUSTFREI ZUSAMMENFÜGEN (Zusammenfügungs-Reihenfolge):")
            log_msgs.append("=" * 55)
            for idx, c in enumerate(changes, 1):
                log_msgs.append(f"  {idx:02d}. [Track {c['track_number']:02d}] {c['orig_filename']}  -->  {c['new_filename']}")

        # Display summary for user confirmation
        summary_win = ctk.CTkToplevel(self)
        summary_win.title("Bestätigung der Änderungen")
        summary_win.geometry("720x540")
        summary_win.grab_set()

        # Center relative to parent
        summary_win.update_idletasks()
        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_w = self.winfo_width()
        parent_h = self.winfo_height()
        win_w = 720
        win_h = 540
        x = parent_x + (parent_w - win_w) // 2
        y = parent_y + (parent_h - win_h) // 2
        summary_win.geometry(f"{win_w}x{win_h}+{x}+{y}")

        tb = ctk.CTkTextbox(summary_win, font=ctk.CTkFont(family="Consolas", size=11))
        tb.pack(expand=True, fill="both", padx=15, pady=15)
        tb.insert("0.0", "\n".join(log_msgs))

        if is_dry_run:
            hint_lbl = ctk.CTkLabel(
                summary_win,
                text="💡 TESTLAUF-MODUS AKTIV: Es werden keine Dateien verändert.\nEntferne das Häkchen bei 'Dry-Run (Testlauf)' in der linken Seitenleiste, um echte Änderungen zu speichern.",
                text_color="#e2b93b",
                font=ctk.CTkFont(weight="bold")
            )
            hint_lbl.pack(padx=15, pady=(0, 10))

        btn_frame = ctk.CTkFrame(summary_win)
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        def on_confirm():
            summary_win.destroy()
            if not is_dry_run:
                self.apply_btn.configure(state="disabled", text="Speichere...")
                self.progress_bar.grid(row=0, column=2, padx=10, pady=2, sticky="e")
                self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
                self.loading_lbl.configure(text=f"💾 Speichere: {album_name}...", text_color="#1f538d")
                self.progress_bar.start()
                threading.Thread(
                    target=self._run_write_operation, 
                    args=(album, album_artist, album_name, genre, year, changes), 
                    daemon=True
                ).start()
            else:
                messagebox.showinfo("Dry-Run Beendet", "Der Dry-Run wurde erfolgreich simuliert. Es wurden keine Dateien verändert.\n\nUm echte Änderungen vorzunehmen, entferne das Häkchen bei 'Dry-Run (Testlauf)' in der linken Seitenleiste.")

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Echte Änderungen anwenden!" if not is_dry_run else "Dry-Run simulieren",
            command=on_confirm,
            fg_color="#1f538d" if not is_dry_run else "#2b712b"
        )
        confirm_btn.pack(side="right", padx=10)

        cancel_btn = ctk.CTkButton(btn_frame, text="Abbrechen", command=summary_win.destroy, fg_color="gray")
        cancel_btn.pack(side="left", padx=10)

    def _run_write_operation(self, album, album_artist, album_name, genre, year, changes):
        folder_path = Path(album["folder_path"])
        
        try:
            # 1. Save Cover to folder if downloaded/provided
            if self.cover_bytes:
                cover_file = folder_path / "cover.jpg"
                with open(cover_file, "wb") as f:
                    f.write(self.cover_bytes)

            # 2. Write Tags and Rename Files
            new_file_paths = []
            for change in changes:
                orig_path = Path(change["filepath"])
                
                # Write tags using mutagen
                TagWriter.write_tags(
                    filepath=str(orig_path),
                    title=change["clean_title"],
                    album=album_name,
                    artist=album_artist,
                    album_artist=album_artist,
                    track_number=change["track_number"],
                    genre=genre,
                    year=year,
                    cover_bytes=self.cover_bytes
                )

                # Rename the file on disk
                target_path = orig_path.parent / change["new_filename"]
                if orig_path != target_path:
                    # Prevent overwriting
                    counter = 1
                    test_path = target_path
                    while test_path.exists() and test_path != orig_path:
                        test_path = orig_path.parent / f"{target_path.stem} ({counter}){target_path.suffix}"
                        counter += 1
                    target_path = test_path
                    
                    os.rename(orig_path, target_path)

                new_file_paths.append(str(target_path))

            # 3. Optional Lossless ffmpeg merge with ID3v2 CHAP/CTOC Chapters
            merged_file_path = None
            if self.merge_var.get():
                # Merge if 2 or more files exist
                if len(new_file_paths) >= 2:
                    merged_filename = f"{album_name}.mp3"
                    # Clean filename characters
                    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                        merged_filename = merged_filename.replace(char, "_")
                        
                    merged_out = folder_path / merged_filename
                    
                    # Sort file paths strictly by assigned track_number order
                    sorted_changes = sorted(changes, key=lambda x: x["track_number"])
                    sorted_paths = [str(folder_path / c["new_filename"]) for c in sorted_changes]

                    try:
                        # Build chapter timing data from assigned tracks
                        chapter_data = ChapterManager.build_chapter_data(sorted_changes)

                        # Lossless FFmpeg merge
                        FileMerger.merge_files(sorted_paths, str(merged_out))
                        
                        # Verify integrity
                        FileMerger.verify_merged_file(sorted_paths, str(merged_out))
                        
                        merged_file_path = str(merged_out)
                        
                        # Determine pure episode title (without '04 - ' prefix) for Plex
                        episode_title = self.current_metadata.episode_title if (self.current_metadata and self.current_metadata.episode_title) else (album_name.split(" - ", 1)[-1] if " - " in album_name else album_name)
                        episode_num = self.current_metadata.series_part if (self.current_metadata and self.current_metadata.series_part) else 1

                        # Apply tags & embed ID3v2 CHAP/CTOC frames
                        TagWriter.write_tags(
                            filepath=merged_file_path,
                            title=episode_title,
                            album=album_name,
                            artist=album_artist,
                            album_artist=album_artist,
                            track_number=episode_num,
                            genre=genre,
                            year=year,
                            cover_bytes=self.cover_bytes,
                            chapters=chapter_data
                        )
                        # Clean up original tracks based on selected option
                        if self.delete_tracks_var.get():
                            for path_str in new_file_paths:
                                p = Path(path_str)
                                if p.exists() and p.is_file() and p.resolve() != Path(merged_file_path).resolve():
                                    try:
                                        p.unlink()
                                    except Exception as e:
                                        print(f"Error deleting original track {p.name}: {e}")
                        elif self.move_tracks_var.get():
                            tracks_dir = folder_path / "Tracks"
                            try:
                                tracks_dir.mkdir(parents=True, exist_ok=True)
                                for path_str in new_file_paths:
                                    p = Path(path_str)
                                    if p.exists() and p.is_file() and p.resolve() != Path(merged_file_path).resolve():
                                        target_p = tracks_dir / p.name
                                        os.rename(p, target_p)
                            except Exception as e:
                                print(f"Error moving original tracks: {e}")
                    except Exception as merge_err:
                        self.after(0, lambda err=merge_err: messagebox.showwarning("ffmpeg Merge Fehler", f"Zusammenführung der MP3s schlug fehl: {err}"))

            # 4. Folder Renaming and Parent Series Folder Organization
            target_ep_folder_name = album_name if self.rename_folder_var.get() and album_name else folder_path.name
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                target_ep_folder_name = target_ep_folder_name.replace(char, "_")

            if self.parent_series_var.get() and album_artist:
                clean_series_name = album_artist
                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    clean_series_name = clean_series_name.replace(char, "_")

                # If current parent folder is not already the series folder
                if folder_path.parent.name.lower() != clean_series_name.lower():
                    series_dir = folder_path.parent / clean_series_name
                    series_dir.mkdir(parents=True, exist_ok=True)
                    final_folder_path = series_dir / target_ep_folder_name
                else:
                    final_folder_path = folder_path.parent / target_ep_folder_name
            elif self.rename_folder_var.get():
                final_folder_path = folder_path.parent / target_ep_folder_name
            else:
                final_folder_path = folder_path

            if folder_path != final_folder_path and not final_folder_path.exists():
                try:
                    os.rename(folder_path, final_folder_path)
                    album["folder_path"] = str(final_folder_path)
                    # Update key in album_states if folder renamed
                    old_key = str(folder_path)
                    new_key = str(final_folder_path)
                    if old_key in self.album_states:
                        self.album_states[new_key] = self.album_states.pop(old_key)
                    if self.target_dir and Path(self.target_dir).resolve() == Path(old_key).resolve():
                        self.target_dir = new_key
                        self.folder_lbl.configure(text=new_key)
                except Exception as folder_err:
                    print(f"Folder move warning: {folder_err}")

            # Operations completed
            def success_notify():
                self.progress_bar.stop()
                self.progress_bar.grid_remove()
                self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
                self.loading_lbl.configure(
                    text=f"✓ {album_name} erfolgreich gespeichert!",
                    text_color="#2b712b"
                )
                self.after(5000, self._clear_status)
                self._clear_editor()
                self._scan_folder(reset_states=False, keep_index=True)

            self.after(0, success_notify)

        except Exception as write_err:
            def error_notify(err=write_err):
                self.progress_bar.stop()
                self.progress_bar.grid_remove()
                self.loading_lbl.grid_remove()
                messagebox.showerror("Schreibfehler", f"Fehler beim Schreiben der Änderungen: {err}")
            self.after(0, error_notify)
        finally:
            self.after(0, lambda: self.apply_btn.configure(state="normal", text="Speichern & Umbenennen"))

    def _open_splitter_dialog(self):
        """Allows selecting a merged MP3 file and losslessly splitting it back into tracks via ID3 CHAP frames."""
        file_path = filedialog.askopenfilename(
            title="Zusammengefügte MP3 mit ID3-Kapiteln auswählen",
            filetypes=[("MP3 Audio", "*.mp3")]
        )
        if not file_path:
            return

        mp3_file = Path(file_path)
        out_dir = mp3_file.parent / f"{mp3_file.stem}_Kapitel"

        try:
            chapters = ChapterManager.extract_chapters(str(mp3_file))
            if not chapters:
                messagebox.showwarning(
                    "Keine Kapitel gefunden",
                    f"In der Datei '{mp3_file.name}' wurden keine ID3v2 CHAP Kapitelmarkierungen gefunden."
                )
                return

            confirm = messagebox.askyesno(
                "Kapitel-Splitter bestätigen",
                f"Datei: {mp3_file.name}\nAnzahl erkannter Kapitel: {len(chapters)}\n\nSollen die Einzeldateien im Ordner\n'{out_dir.name}' verlustfrei gespeichert werden?"
            )
            if not confirm:
                return

            def run_split_thread():
                try:
                    created_files = ChapterManager.split_by_chapters(str(mp3_file), str(out_dir))
                    self.after(0, lambda: messagebox.showinfo(
                        "Splitter Erfolgreich",
                        f"Es wurden {len(created_files)} Kapiteldateien verlustfrei im Ordner:\n{out_dir}\nerstellt!"
                    ))
                except Exception as err:
                    self.after(0, lambda e=err: messagebox.showerror("Splitter Fehler", f"Fehler beim Teilen der MP3: {e}"))

            threading.Thread(target=run_split_thread, daemon=True).start()

        except Exception as err:
            messagebox.showerror("Fehler", f"Konnte Kapitel nicht lesen: {err}")

            self.after(0, success_notify)

        except Exception as write_err:
            self.after(0, lambda: messagebox.showerror("Schreibfehler", f"Fehler beim Schreiben der Änderungen: {write_err}"))
        finally:
            self.after(0, lambda: self.apply_btn.configure(state="normal", text="Speichern & Umbenennen"))

if __name__ == "__main__":
    app = HoerspielTaggerGUI()
    app.mainloop()
