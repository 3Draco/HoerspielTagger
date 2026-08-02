import os
import sys
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
from api_settings_dialog import ApiSettingsDialog
from sidebar_frame import SidebarFrame
from metadata_form_frame import MetadataFormFrame
from cover_panel_frame import CoverPanelFrame
from summary_dialog import SummaryDialog
from batch_edit_tab import BatchEditTab
from filename_structure_tab import FilenameStructureTab
import config

class HoerspielTaggerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()

        # Initialize TkDND extension
        try:
            self.TkdndVersion = TkinterDnD._require(self)
        except Exception as e:
            self.TkdndVersion = None

        # Determine base directory (supporting PyInstaller bundles)
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
            resource_dir = Path(getattr(sys, '_MEIPASS', base_dir))
        else:
            base_dir = Path(__file__).parent
            resource_dir = base_dir

        self.title(f"Hörspiel Tagger {config.APP_VERSION} - AI-Powered Audio Drama Tagger")
        
        # Set window icon if available
        icon_path = resource_dir / "img" / "icon.ico"
        if not icon_path.exists():
            icon_path = base_dir / "img" / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass
        
        # Load last settings and window geometry if exists (Encrypted per machine)
        try:
            import json, hashlib, uuid, platform, base64
            from cryptography.fernet import Fernet

            def _get_fernet_key():
                # Hardware-bound encryption key unique to this machine
                node = uuid.getnode()
                system = platform.node()
                raw_id = f"HoerspielTagger:{node}:{system}".encode('utf-8')
                key_32 = hashlib.sha256(raw_id).digest()
                return base64.urlsafe_b64encode(key_32)

            state_file = base_dir / "app_config.dat"
            old_file = base_dir / "window_state.json"
            self.loaded_settings = {}

            if state_file.exists():
                with open(state_file, "rb") as f:
                    encrypted_data = f.read()
                fernet = Fernet(_get_fernet_key())
                decrypted_bytes = fernet.decrypt(encrypted_data)
                self.loaded_settings = json.loads(decrypted_bytes.decode('utf-8'))
            elif old_file.exists():
                with open(old_file, "r", encoding="utf-8") as f:
                    self.loaded_settings = json.load(f)

            geom = self.loaded_settings.get("geometry")
            if geom:
                parts = geom.split("+")
                if len(parts) == 3:
                    try:
                        x = int(parts[1])
                        y = int(parts[2])
                        import ctypes
                        try:
                            # Use Windows system metrics for virtual desktop (multi-monitor/surround bounds)
                            vx = ctypes.windll.user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
                            vy = ctypes.windll.user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
                            vw = ctypes.windll.user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
                            vh = ctypes.windll.user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
                        except Exception:
                            vx, vy, vw, vh = -10000, -10000, 40000, 40000

                        # Check if window top-left is within any active monitor area
                        if (vx - 100 <= x <= vx + vw - 100) and (vy - 100 <= y <= vy + vh - 100):
                            self.geometry(geom)
                        else:
                            self.geometry("1200x800")
                    except Exception:
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
        self.track_rows: List[Dict[str, Any]] = []
        self.album_states: Dict[str, Dict[str, Any]] = {}
        self.current_ctk_image: Optional[ctk.CTkImage] = None
        self.keep_ctk_images: List[ctk.CTkImage] = []
        self._cover_fetch_token: int = 0

        self.protocol("WM_DELETE_WINDOW", self._on_app_close)
        self._build_ui()
        self._setup_drag_and_drop()
        self._load_config_defaults()

    def _on_app_close(self):
        """Ensures immediate and clean application termination on single click."""
        self.is_processing = False
        
        # Save settings and window geometry (Encrypted per machine)
        try:
            geom = self.geometry()
            settings = {
                "geometry": geom,
                "api_url": config.LLM_API_BASE_URL,
                "api_key": config.LLM_API_KEY,
                "model_id": config.LLM_MODEL_ID,
                "system_prompt": config.LLM_SYSTEM_PROMPT,
                "discogs_token": getattr(config, "DISCOGS_API_TOKEN", ""),
                "dry_run": self.dry_run_var.get(),
                "merge": self.merge_var.get(),
                "delete_tracks": self.delete_tracks_var.get(),
                "rename_folder": self.rename_folder_var.get(),
                "parent_series": self.parent_series_var.get(),
                "cover": self.cover_var.get(),
                "target_dir": self.target_dir,
                "source_embedded": self.source_embedded_var.get(),
                "source_discogs": self.source_discogs_var.get(),
                "source_itunes": self.source_itunes_var.get(),
                "source_deezer": self.source_deezer_var.get(),
                "source_musicbrainz": self.source_musicbrainz_var.get(),
                "flat_episodes": self.flat_episodes_var.get(),
                "max_cover_count": getattr(config, "MAX_COVER_COUNT", 6),
                "folder_pattern": self.structure_tab.get_folder_pattern() if hasattr(self, "structure_tab") else "",
                "file_pattern": self.structure_tab.get_file_pattern() if hasattr(self, "structure_tab") else ""
            }
            import json, hashlib, uuid, platform, base64
            from cryptography.fernet import Fernet

            def _get_fernet_key():
                node = uuid.getnode()
                system = platform.node()
                raw_id = f"HoerspielTagger:{node}:{system}".encode('utf-8')
                key_32 = hashlib.sha256(raw_id).digest()
                return base64.urlsafe_b64encode(key_32)

            if getattr(sys, 'frozen', False):
                base_dir = Path(sys.executable).parent
            else:
                base_dir = Path(__file__).parent

            state_file = base_dir / "app_config.dat"
            data_bytes = json.dumps(settings).encode('utf-8')
            fernet = Fernet(_get_fernet_key())
            encrypted_data = fernet.encrypt(data_bytes)

            with open(state_file, "wb") as f:
                f.write(encrypted_data)
        except Exception as e:
            print(f"Error saving settings on exit: {e}")

        try:
            self.quit()
            self.destroy()
        except Exception:
            pass
        import os
        os._exit(0)

    # Backward compatible properties mapping to component sub-frames
    @property
    def dry_run_var(self): return self.sidebar.dry_run_var
    @property
    def merge_var(self): return self.sidebar.merge_var
    @property
    def delete_tracks_var(self): return self.sidebar.delete_tracks_var
    @property
    def rename_folder_var(self): return self.sidebar.rename_folder_var
    @property
    def parent_series_var(self): return self.sidebar.parent_series_var
    @property
    def cover_var(self): return self.sidebar.cover_var
    @property
    def flat_episodes_var(self): return self.sidebar.flat_episodes_var

    @property
    def folder_lbl(self): return self.sidebar.folder_lbl
    @property
    def delete_tracks_cb(self): return self.sidebar.delete_tracks_cb
    @property
    def rename_folder_cb(self): return self.sidebar.rename_folder_cb
    @property
    def scan_btn(self): return self.sidebar.scan_btn
    @property
    def analyze_btn(self): return self.sidebar.analyze_btn

    @property
    def form_entries(self): return self.form_scroll.form_entries
    @property
    def current_tag_entries(self): return self.form_scroll.current_tag_entries
    @property
    def tracks_container(self): return self.form_scroll.tracks_container
    @property
    def preview_textbox(self): return self.form_scroll.preview_textbox

    @property
    def cover_img_label(self): return self.cover_panel.cover_img_label
    @property
    def cover_status_lbl(self): return self.cover_panel.cover_status_lbl
    @property
    def source_embedded_var(self): return self.cover_panel.source_embedded_var
    @property
    def source_discogs_var(self): return self.cover_panel.source_discogs_var
    @property
    def source_itunes_var(self): return self.cover_panel.source_itunes_var
    @property
    def source_deezer_var(self): return self.cover_panel.source_deezer_var
    @property
    def source_musicbrainz_var(self): return self.cover_panel.source_musicbrainz_var
    @property
    def crop_cover_btn(self): return self.cover_panel.crop_cover_btn
    @property
    def chooser_cover_btn(self): return self.cover_panel.chooser_cover_btn
    @property
    def manual_cover_btn(self): return self.cover_panel.manual_cover_btn
    @property
    def google_search_btn(self): return self.cover_panel.google_search_btn
    @property
    def apply_btn(self): return self.cover_panel.apply_btn
    @property
    def apply_all_btn(self): return self.cover_panel.apply_all_btn
    @property
    def tracks_container(self): return self.structure_tab.tracks_container
    @property
    def preview_textbox(self): return self.structure_tab.preview_textbox

    def _build_ui(self):
        # Configure grid layout (2 rows, 2 columns)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # Bottom status bar row
        self.grid_columnconfigure(0, weight=0)  # Left settings panel
        self.grid_columnconfigure(1, weight=1)  # Right work panel

        # ================= LEFT SIDEBAR =================
        self.sidebar = SidebarFrame(
            self,
            on_browse_folder=self._browse_folder,
            on_open_api_settings=self._open_api_settings_dialog,
            on_merge_toggle=self._on_merge_toggle,
            on_delete_tracks_toggle=self._on_delete_tracks_toggle,
            on_update_preview=self._update_live_preview,
            on_flat_episodes_toggle=self._on_flat_episodes_toggle,
            on_scan_folder=self._scan_folder,
            on_start_analysis=self._start_analysis,
            on_clear_cache=self._clear_cache,
            on_open_splitter=self._open_splitter_dialog,
            on_open_series_db=self._open_series_db_dialog
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

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
        self.tab_edit = self.content_tabview.add("🏷️ Metadaten-Tags")
        self.tab_structure = self.content_tabview.add("📁 Dateinamen & Ordnerstruktur")
        self.tab_batch = self.content_tabview.add("⚡ Massenbearbeitung")

        # Tab 3: Filename & Folder Structure UI Component
        self.structure_tab = FilenameStructureTab(
            self.tab_structure,
            on_update_live_preview=self._update_live_preview
        )
        self.structure_tab.pack(expand=True, fill="both")

        # Massenbearbeitung UI Component
        self.batch_tab_ui = BatchEditTab(
            self.tab_batch,
            get_scan_results_cb=lambda: self.scan_results,
            on_status_update_cb=lambda msg, color: self.cover_status_lbl.configure(text=msg, text_color=color) if hasattr(self, 'cover_status_lbl') else None
        )
        self.batch_tab_ui.pack(expand=True, fill="both")

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
        self.form_scroll = MetadataFormFrame(self.tab_edit, on_update_live_preview=self._update_live_preview)
        self.form_scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Cover & Action Panel (Right of Tab 2)
        self.cover_panel = CoverPanelFrame(
            self.tab_edit,
            on_cover_source_changed=self._on_cover_source_changed,
            on_open_crop_dialog=self._open_crop_dialog,
            on_open_cover_chooser=self._open_cover_chooser,
            on_load_manual_cover=self._load_manual_cover,
            on_google_cover_search=self._open_google_cover_search,
            on_apply_metadata=self._apply_metadata,
            on_apply_all_metadata=self._apply_all_metadata
        )
        self.cover_panel.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)


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
        # Load API settings into config module
        config.LLM_API_BASE_URL = self.loaded_settings.get("api_url", config.LLM_API_BASE_URL)
        config.LLM_API_KEY = self.loaded_settings.get("api_key", config.LLM_API_KEY)
        config.LLM_MODEL_ID = self.loaded_settings.get("model_id", config.LLM_MODEL_ID)
        config.LLM_SYSTEM_PROMPT = self.loaded_settings.get("system_prompt", config.LLM_SYSTEM_PROMPT)
        config.DISCOGS_API_TOKEN = self.loaded_settings.get("discogs_token", getattr(config, "DISCOGS_API_TOKEN", ""))
        config.MAX_COVER_COUNT = self.loaded_settings.get("max_cover_count", getattr(config, "MAX_COVER_COUNT", 6))

        if "folder_pattern" in self.loaded_settings and self.loaded_settings["folder_pattern"]:
            self.structure_tab.set_folder_pattern(self.loaded_settings["folder_pattern"])
        if "file_pattern" in self.loaded_settings and self.loaded_settings["file_pattern"]:
            self.structure_tab.set_file_pattern(self.loaded_settings["file_pattern"])

        # Load options checkboxes
        self.dry_run_var.set(self.loaded_settings.get("dry_run", True))
        self.merge_var.set(self.loaded_settings.get("merge", False))
        self.delete_tracks_var.set(self.loaded_settings.get("delete_tracks", False))
        self.rename_folder_var.set(self.loaded_settings.get("rename_folder", True))
        self.parent_series_var.set(self.loaded_settings.get("parent_series", True))
        self.cover_var.set(self.loaded_settings.get("cover", True))

        # Load cover sources settings
        self.source_embedded_var.set(self.loaded_settings.get("source_embedded", True))
        self.source_discogs_var.set(self.loaded_settings.get("source_discogs", True))
        self.source_itunes_var.set(self.loaded_settings.get("source_itunes", True))
        self.source_deezer_var.set(self.loaded_settings.get("source_deezer", True))
        self.source_musicbrainz_var.set(self.loaded_settings.get("source_musicbrainz", True))

        # Load flat mode setting
        self.flat_episodes_var.set(self.loaded_settings.get("flat_episodes", False))
        if self.flat_episodes_var.get():
            self.rename_folder_cb.configure(text="📁 Episoden-Ordner anlegen")
        else:
            self.rename_folder_cb.configure(text="📁 Episoden-Ordner umbenennen")

        # Handle enabling/disabling checkbox states dynamically based on the loaded merge option
        self._on_merge_toggle()

        # Load last target directory if exists and still valid
        last_dir = self.loaded_settings.get("target_dir")
        if last_dir and Path(last_dir).exists():
            self.target_dir = last_dir
            self.folder_lbl.configure(text=last_dir)
            self._scan_folder(reset_states=True)

        self._test_llm_connection()

    def _open_api_settings_dialog(self):
        """Opens modal for API & Prompt settings."""
        def on_save(url, key, model, prompt):
            self._test_llm_connection()
        ApiSettingsDialog(self, on_save_callback=on_save)

    def _test_llm_connection(self):
        """Triggers asynchronous LLM connection test."""
        self.llm_status_lbl.configure(text="🟡 Verbindung wird geprüft...", text_color="orange")
        threading.Thread(target=self._run_test_connection_thread, daemon=True).start()

    def _run_test_connection_thread(self):
        """Tests HTTP connection to LLM API endpoint."""
        url = config.LLM_API_BASE_URL
        try:
            import urllib.request
            # Parse host/url for ping
            req = urllib.request.Request(url, headers={"User-Agent": "HoerspielTagger"})
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
            print(f"Folder Drag & Drop Setup Info: {e}")
            
        try:
            # Gather cover widgets, including underlying Tkinter components for safety in CTk
            cover_widgets = [self.cover_panel, self.cover_img_label]
            if hasattr(self.cover_panel, "_canvas"):
                cover_widgets.append(self.cover_panel._canvas)
            if hasattr(self.cover_img_label, "_label"):
                cover_widgets.append(self.cover_img_label._label)

            for widget in cover_widgets:
                # Register for files (local image files dropped)
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind('<<Drop>>', self._on_drop_cover)
                except Exception:
                    pass
                # Register for text/URLs (web images dragged directly from browser)
                try:
                    widget.drop_target_register("DND_Text")
                    widget.dnd_bind('<<Drop>>', self._on_drop_cover)
                except Exception:
                    pass
        except Exception as e:
            print(f"Cover Drag & Drop Setup Info: {e}")

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

    def _on_drop_cover(self, event):
        """Handles cover Drag & Drop events (e.g. from local images or web browser URLs)."""
        raw_data = event.data
        if not raw_data:
            return

        import re
        import base64
        import urllib.parse
        from PIL import Image
        import io

        # 1. Check if it is a base64 data URL
        if "data:image/" in raw_data and ";base64," in raw_data:
            try:
                header, base64_data = raw_data.split(";base64,", 1)
                base64_data = base64_data.strip("{} \n\r")
                img_data = base64.b64decode(base64_data)
                # Verify image
                Image.open(io.BytesIO(img_data))
                self.cover_bytes = img_data
                self._display_cover_image(self.cover_bytes)
                self.cover_status_lbl.configure(text="Cover per Drag & Drop geladen (Base64)", text_color="#2b712b")
                self._save_current_album_state()
                return
            except Exception as e:
                messagebox.showerror("Fehler beim Dekodieren", f"Konnte Base64-Bild nicht lesen: {e}")
                return

        # 2. Extract URL using regex
        url_match = re.search(r'(https?://[^\s{}"]+)', raw_data)
        if url_match:
            url = url_match.group(1)
            
            # Check if it is a Google Image Search redirect URL and extract the actual image URL
            if "google." in url and "imgurl=" in url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    queries = urllib.parse.parse_qs(parsed.query)
                    if "imgurl" in queries:
                        url = queries["imgurl"][0]
                except Exception as e:
                    print(f"Error parsing Google redirect URL: {e}")

            self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
            self.loading_lbl.configure(text="⏳ Lade Cover aus Web...", text_color="#1f538d")
            self.update()
            
            def download_web_cover():
                import requests
                try:
                    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        # Verify that the downloaded bytes actually form a valid image
                        try:
                            Image.open(io.BytesIO(resp.content))
                            def success():
                                self.cover_bytes = resp.content
                                self._display_cover_image(self.cover_bytes)
                                self.cover_status_lbl.configure(text="Cover von URL geladen", text_color="#2b712b")
                                self._save_current_album_state()
                            self.after(0, success)
                        except Exception as img_err:
                            self.after(0, lambda: messagebox.showerror(
                                "Ungültiges Bild", 
                                f"Die heruntergeladene Datei ist kein gültiges Bild.\nURL: {url[:60]}...\n\nFehler: {img_err}"
                            ))
                    else:
                        self.after(0, lambda: messagebox.showerror("Download Fehler", f"Server lieferte Statuscode {resp.status_code}"))
                except Exception as err:
                    self.after(0, lambda e=err: messagebox.showerror("Download Fehler", f"Konnte Bild nicht herunterladen: {e}"))
                finally:
                    self.after(0, self._clear_status)
                    
            threading.Thread(target=download_web_cover, daemon=True).start()
        else:
            # 3. Handle local file drops
            try:
                paths = self.tk.splitlist(raw_data)
                if paths:
                    p = Path(paths[0])
                    if p.exists() and p.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                        with open(p, "rb") as f:
                            img_data = f.read()
                        # Verify image
                        Image.open(io.BytesIO(img_data))
                        self.cover_bytes = img_data
                        self._display_cover_image(self.cover_bytes)
                        self.cover_status_lbl.configure(text="Cover per Drag & Drop geladen", text_color="#2b712b")
                        self._save_current_album_state()
            except Exception as e:
                messagebox.showerror("Fehler beim Laden", f"Konnte lokale Bilddatei nicht lesen: {e}")

    def _get_active_cover_sources(self) -> List[str]:
        sources = []
        if self.source_discogs_var.get():
            sources.append("discogs")
        if self.source_itunes_var.get():
            sources.append("itunes")
        if self.source_deezer_var.get():
            sources.append("deezer")
        if self.source_musicbrainz_var.get():
            sources.append("musicbrainz")
        return sources

    def _auto_fill_year_if_missing(self, year_val: Optional[int]):
        if year_val and "year" in self.form_entries:
            current_year = self.form_entries["year"].get().strip()
            if not current_year:
                self.form_entries["year"].delete(0, tk.END)
                self.form_entries["year"].insert(0, str(year_val))

    @staticmethod
    def _extract_episode_num_from_text(text: str) -> Optional[int]:
        if not text:
            return None
        import re
        m1 = re.search(r'(?:folge|nr\.?|vol\.?)\s*(\d{1,3})\b', text, re.IGNORECASE)
        if m1:
            try:
                val = int(m1.group(1))
                if 0 < val < 999:
                    return val
            except ValueError:
                pass
        m2 = re.search(r'\(\s*0*(\d{1,3})\s*\)', text)
        if m2:
            try:
                val = int(m2.group(1))
                if 0 < val < 999:
                    return val
            except ValueError:
                pass
        m3 = re.search(r'(?:^|[\-\s])0*(\d{1,3})\s*\-\s*', text)
        if m3:
            try:
                val = int(m3.group(1))
                if 0 < val < 999:
                    return val
            except ValueError:
                pass
        return None

    def _auto_correct_episode_num_if_matched(self, ep_num: Optional[int]):
        if not ep_num or ep_num <= 0:
            return
        num_str = f"{ep_num:02d}"
        if "series_part" in self.form_entries:
            curr_val = self.form_entries["series_part"].get().strip()
            if curr_val != num_str and curr_val != str(ep_num):
                self.form_entries["series_part"].delete(0, tk.END)
                self.form_entries["series_part"].insert(0, num_str)
                if "album" in self.form_entries:
                    ep_title = self.form_entries["episode_title"].get().strip() if "episode_title" in self.form_entries else ""
                    if ep_title:
                        self.form_entries["album"].delete(0, tk.END)
                        self.form_entries["album"].insert(0, f"{num_str} - {ep_title}")
                self._update_live_preview()
                self._save_current_album_state()

    def _on_cover_source_changed(self):
        """Triggered when cover sources checkboxes are toggled by the user."""
        if not self.scan_results or self.current_album_idx not in range(len(self.scan_results)):
            return

        album = self.scan_results[self.current_album_idx]
        state_key = album["tracks"][0]["filepath"] if album.get("flat_mode") else album["folder_path"]
        state = self.album_states.get(state_key, {})
        orig_tracks = album.get("tracks", [])
        t0 = orig_tracks[0] if orig_tracks else {}

        # If "Eingebettetes Cover" is checked and the folder had an embedded cover originally
        if self.source_embedded_var.get() and album.get("has_embedded_cover"):
            # Load the original embedded cover
            try:
                from mutagen.mp3 import MP3
                audio = MP3(t0["filepath"])
                if audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith("APIC"):
                            self.cover_bytes = audio.tags[key].data
                            self._display_cover_image(self.cover_bytes)
                            self.cover_status_lbl.configure(text="Originales eingebettetes Cover", text_color="#2b712b")
                            self._save_current_album_state()
                            return
            except Exception as e:
                print(f"Error restoring embedded cover: {e}")

        # Otherwise, if we have active online sources, fetch the best online match
        sources = self._get_active_cover_sources()

        if sources:
            artist = self.form_entries["album_artist"].get().strip()
            album_title = self.form_entries["album"].get().strip()
            title = self.form_entries["series"].get().strip() or album_title
            ep_num = self.form_entries["series_part"].get().strip() if "series_part" in self.form_entries else ""

            self.cover_status_lbl.configure(text="🔍 Suche Cover online...", text_color="orange")
            self.update()

            def fetch():
                candidates = CoverDownloader.search_cover_candidates(artist, album_title, title, sources=sources, episode_num=ep_num)
                if candidates and candidates[0].get("score", 0) >= 10:
                    best = candidates[0]
                    cover_url = best.get("url")
                    found_year = best.get("year")
                    found_ep = self._extract_episode_num_from_text(best.get("title", ""))
                    if cover_url:
                        img_bytes = CoverDownloader.download_image(cover_url)
                        if img_bytes:
                            def apply():
                                self.cover_bytes = img_bytes
                                self._display_cover_image(img_bytes)
                                self._auto_fill_year_if_missing(found_year)
                                if found_ep:
                                    self._auto_correct_episode_num_if_matched(found_ep)
                                self.cover_status_lbl.configure(text="Cover online geladen", text_color="#2b712b")
                                self._save_current_album_state()
                            self.after(0, apply)
                            return
                def fail():
                    self.cover_bytes = None
                    self.current_ctk_image = None
                    self.cover_img_label.configure(text="Kein Cover geladen", image=None)
                    self.cover_status_lbl.configure(text="Cover-Suche erfolglos", text_color="#7a2b2b")
                    self._save_current_album_state()
                self.after(0, fail)

            threading.Thread(target=fetch, daemon=True).start()
        else:
            # Clear cover if no sources checked
            self.cover_bytes = None
            self.current_ctk_image = None
            self.cover_img_label.configure(text="Kein Cover geladen", image=None)
            self.cover_status_lbl.configure(text="Keine Quelle ausgewählt", text_color="#7a2b2b")
            self._save_current_album_state()

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
            state_key = album["tracks"][0]["filepath"] if album.get("flat_mode") else album["folder_path"]
            if state_key in self.album_states:
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

                composer_str = t0.get("composer") or t0.get("author") or ""
                publisher_str = t0.get("publisher") or ""
                comment_str = t0.get("comment") or ""
                disc_str = str(t0.get("disc_number")) if t0.get("disc_number") else ""

            form_data = {
                "album_artist": "",
                "album": "",
                "episode_title": "",
                "series": "",
                "series_part": "",
                "year": "",
                "genre": "",
                "composer": "",
                "publisher": "",
                "disc_number": "",
                "comment": ""
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

            self.album_states[state_key] = {
                "metadata": None,
                "form_data": form_data,
                "track_rows": track_rows,
                "cover_bytes": None,
                "cover_status": "Eingebettetes Cover vorhanden" if album["has_embedded_cover"] else "Kein Cover geladen",
                "cover_status_color": "#2b712b" if album["has_embedded_cover"] else "gray"
            }

    def _clear_cache(self):
        """Clears all cached album states, removes loaded folders/files, and resets the application to fresh initial state."""
        self.album_states = {}
        self.scan_results = []
        self.current_album_idx = 0
        self.target_dir = None
        self.dragged_paths = None
        self.cover_bytes = None
        self.current_ctk_image = None
        self.is_processing = False

        # Reset Sidebar UI
        self.folder_lbl.configure(text="Kein Ordner ausgewählt", text_color="gray")
        self.scan_btn.configure(state="disabled")
        self.analyze_btn.configure(state="disabled")

        # Reset Main Panel UI
        self.scan_textbox.delete("0.0", tk.END)
        self.scan_textbox.insert("0.0", "Wähle einen Ordner aus oder ziehe einen Ordner in das Drop-Feld oben, um zu beginnen...")

        self.album_status_lbl.configure(text="Keine Daten geladen")
        self.nav_prev_btn.configure(state="disabled")
        self.nav_next_btn.configure(state="disabled")

        self._clear_editor()
        self._update_live_preview()

        # Reset Tab view to first tab
        self.content_tabview.set("Scannen und Ordnerstruktur")

        # Show temporary success message
        self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
        self.loading_lbl.configure(text="🧹 Cache & Ordner erfolgreich geleert!", text_color="#2b712b")
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
                def _is_in_dragged(folder_p_str: str) -> bool:
                    f_path = Path(folder_p_str).resolve()
                    for dp in self.dragged_paths:
                        dp_path = Path(dp).resolve()
                        if f_path == dp_path or dp_path in f_path.parents:
                            return True
                    return False

                results = [r for r in results if _is_in_dragged(r["folder_path"])]

            # If flat mode is active, treat each MP3 as a separate episode
            if self.flat_episodes_var.get():
                flat_results = []
                for album in results:
                    for track in album["tracks"]:
                        track_name_no_ext = Path(track["filename"]).stem
                        flat_results.append({
                            "folder_path": album["folder_path"],
                            "folder_name": track_name_no_ext,
                            "relative_folder_path": album["relative_folder_path"],
                            "tracks": [track],
                            "has_embedded_cover": track["has_cover"],
                            "has_chapters": track.get("has_chapters", False),
                            "flat_mode": True,
                            "original_flat_filename": track["filename"]
                        })
                results = flat_results

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
            if hasattr(self, 'batch_tab_ui'):
                self.batch_tab_ui.refresh_file_list()

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

        album = self.scan_results[self.current_album_idx]
        state_key = album["tracks"][0]["filepath"] if album.get("flat_mode") else album["folder_path"]
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

        self.album_states[state_key] = {
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

        album_data = self.scan_results[idx]
        state_key = album_data["tracks"][0]["filepath"] if album_data.get("flat_mode") else album_data["folder_path"]
        if state_key not in self.album_states:
            return False

        state = self.album_states[state_key]
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

        # If cover_bytes is not set in state, but file has cover and embedded source is active, load it
        if not self.cover_bytes and album_data.get("has_embedded_cover") and self.source_embedded_var.get():
            try:
                from mutagen.mp3 import MP3
                audio = MP3(t0["filepath"])
                if audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith("APIC"):
                            self.cover_bytes = audio.tags[key].data
                            state["cover_bytes"] = self.cover_bytes
                            state["cover_status"] = "Originales eingebettetes Cover"
                            state["cover_status_color"] = "#2b712b"
                            break
            except Exception as e:
                print(f"Error loading embedded cover: {e}")

        orig_tags = {
            "album_artist": t0.get("album_artist") or "",
            "album": t0.get("album") or "",
            "episode_title": t0.get("title") or "",
            "series": t0.get("artist") or "",
            "series_part": str(t0.get("track_number")) if t0.get("track_number") is not None else "",
            "year": str(t0.get("year")) if t0.get("year") is not None else "",
            "genre": t0.get("genre") or "",
            "composer": t0.get("composer") or t0.get("author") or "",
            "publisher": t0.get("publisher") or "",
            "disc_number": str(t0.get("disc_number")) if t0.get("disc_number") is not None else "",
            "comment": t0.get("comment") or ""
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
                self.cover_img_label.configure(text="Kein Cover geladen", image=None)
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
            self.apply_all_btn.configure(state="normal")
            self.manual_cover_btn.configure(state="normal")
            self.chooser_cover_btn.configure(state="normal")
            self.google_search_btn.configure(state="normal")

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
            self.cover_img_label.configure(text="Kein Cover geladen", image=None)
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
        self.apply_all_btn.configure(state="disabled")
        self.manual_cover_btn.configure(state="disabled")
        self.chooser_cover_btn.configure(state="disabled")
        self.crop_cover_btn.configure(state="disabled")
        self.google_search_btn.configure(state="disabled")

    def _open_cover_chooser(self):
        """Opens modal dialog immediately for choosing between multiple candidate album covers from active sources."""
        artist = self.form_entries["album_artist"].get()
        album = self.form_entries["album"].get()
        title = self.form_entries["series"].get() or album
        sources = self._get_active_cover_sources()

        def on_selected(new_bytes, year=None, cand_title=None):
            self._cover_fetch_token += 1
            self.cover_bytes = new_bytes
            self._display_cover_image(new_bytes)
            if year:
                self._auto_fill_year_if_missing(year)
            if cand_title:
                found_ep = self._extract_episode_num_from_text(cand_title)
                if found_ep:
                    self._auto_correct_episode_num_if_matched(found_ep)
            self.cover_status_lbl.configure(text="Cover aus Varianten gewählt", text_color="#2b712b")
            self._save_current_album_state()

        CoverChooserDialog(
            parent=self,
            artist=artist,
            album=album,
            title=title,
            sources=sources,
            on_select_cover=on_selected
        )

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

        # Update bottom-left status bar
        self.llm_status_lbl.configure(text="⏳ LLM Analyse gestartet...", text_color="orange")

        self.content_tabview.set("🏷️ Metadaten-Tags")

        # Open blocking progress dialog
        from analysis_progress_dialog import AnalysisProgressDialog
        self.progress_dialog = AnalysisProgressDialog(self)

        # Run in thread so GUI doesn't freeze
        threading.Thread(target=self._run_analysis_thread, daemon=True).start()

    def _update_analysis_status(self, i, t, fn):
        self.loading_lbl.configure(text=f"⏳ Analysiere Ordner {i + 1}/{t}: {fn}...")
        self.llm_status_lbl.configure(text=f"⏳ Analysiere {i + 1}/{t}: {fn}...", text_color="orange")
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            self.progress_dialog.update_progress(i, t, fn)

    def _close_progress_dialog(self):
        if hasattr(self, "progress_dialog") and self.progress_dialog:
            try:
                self.progress_dialog.close()
            except Exception:
                pass
            self.progress_dialog = None

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
            self.llm_client = LLMClient()
            total = len(self.scan_results)

            # Enrich system prompt with known acronyms/aliases
            active_prompt = config.LLM_SYSTEM_PROMPT
            try:
                from series_db import SeriesDatabase
                alias_summary = SeriesDatabase.get_prompt_aliases_summary()
                if alias_summary:
                    active_prompt += "\n\nBEKANNTE SERIEN-KÜRZEL & ALIASE (VERWENDE DIESE NORM-NAMEN):\n" + alias_summary
            except Exception as e:
                print(f"[SeriesDB Prompt Info] {e}")

            for idx in range(total):
                album = self.scan_results[idx]
                folder_path = album["folder_path"]
                folder_name = album["folder_name"]

                self.after(0, lambda i=idx, t=total, fn=folder_name: self._update_analysis_status(i, t, fn))

                # Check if folder starts with a registered prefix code (e.g. LB08, JS120)
                pre_matched = None
                try:
                    from series_db import SeriesDatabase
                    pre_matched = SeriesDatabase.resolve_folder_prefix(folder_name)
                except Exception:
                    pass

                # 1. Query LLM for this folder with enriched prompt
                metadata = self.llm_client.analyze_album(folder_name, album["tracks"], custom_prompt=active_prompt)

                # Apply pre-matched series info if found
                if pre_matched:
                    metadata.series = pre_matched["series_name"]
                    metadata.series_name = pre_matched["series_name"]
                    metadata.album_artist = pre_matched["series_name"]
                    metadata.genre = pre_matched["genre"]
                    metadata.formatted_genre = pre_matched["genre"]
                    if pre_matched.get("episode_num") is not None:
                        metadata.series_part = pre_matched["episode_num"]

                # Check SeriesDatabase for genre consistency / instant registration
                try:
                    from series_db import SeriesDatabase
                    series_name = metadata.series_name or metadata.album_artist or metadata.series
                    if series_name:
                        known_genre = SeriesDatabase.get_genre(series_name)
                        if known_genre:
                            metadata.genre = known_genre
                            metadata.formatted_genre = known_genre
                        elif metadata.genre:
                            # INSTANT REGISTRATION: First episode registers series genre immediately!
                            SeriesDatabase.set_series_genre(series_name, metadata.genre)
                except Exception as db_err:
                    print(f"[SeriesDB Info] {db_err}")

                # 2. Cover Art search for this folder
                cover_bytes = None
                cover_status = "Cover-Suche erfolglos"
                cover_color = "#7a2b2b"

                use_embedded = self.source_embedded_var.get() and album["has_embedded_cover"]

                if use_embedded:
                    try:
                        from mutagen.mp3 import MP3
                        t0 = album["tracks"][0]
                        audio = MP3(t0["filepath"])
                        if audio.tags:
                            for key in audio.tags.keys():
                                if key.startswith("APIC"):
                                    cover_bytes = audio.tags[key].data
                                    cover_status = "Originales eingebettetes Cover"
                                    cover_color = "#2b712b"
                                    break
                    except Exception as e:
                        print(f"Error loading embedded cover in analysis: {e}")

                if self.cover_var.get() or not metadata.year:
                    sources = self._get_active_cover_sources()
                    if sources:
                        ep_num = getattr(metadata, 'series_part', None) or getattr(metadata, 'episode_number', None)
                        candidates = CoverDownloader.search_cover_candidates(metadata.album_artist, metadata.album, getattr(metadata, 'episode_title', None), sources=sources, episode_num=ep_num)
                        if candidates and candidates[0].get("score", 0) >= 10:
                            best = candidates[0]
                            found_ep = self._extract_episode_num_from_text(best.get("title", ""))
                            if found_ep and not metadata.series_part:
                                metadata.series_part = found_ep
                            if not cover_bytes and self.cover_var.get():
                                cover_url = best.get("url")
                                if cover_url:
                                    cover_bytes = CoverDownloader.download_image(cover_url)
                                    cover_status = "Cover online geladen"
                                    cover_color = "#2b712b"
                            if not metadata.year and best.get("year"):
                                metadata.year = best["year"]

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
                    "genre": metadata.genre,
                    "composer": getattr(metadata, 'composer', '') or getattr(metadata, 'author', '') or '',
                    "publisher": getattr(metadata, 'publisher', '') or '',
                    "disc_number": str(getattr(metadata, 'disc_number', 1) or '1'),
                    "comment": getattr(metadata, 'comment', '') or ''
                }

                # Save state per state_key
                state_key = album["tracks"][0]["filepath"] if album.get("flat_mode") else album["folder_path"]
                self.album_states[state_key] = {
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
                self.content_tabview.set("🏷️ Metadaten-Tags")
                self._restore_album_state(self.current_album_idx)
                self.apply_all_btn.configure(state="normal")
                
                # Update bottom-left status bar
                self.llm_status_lbl.configure(text="🟢 LLM Analyse abgeschlossen", text_color="#2b712b")

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
            self.after(0, lambda: self.scan_btn.configure(state="normal" if self.target_dir else "disabled"))
            self.after(0, self._close_progress_dialog)

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

        # Build track rows data for this folder
        orig_tracks = self.scan_results[self.current_album_idx]["tracks"]
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

        self.track_rows = track_rows
        self._render_track_rows()
        self.apply_btn.configure(state="normal")
        self.apply_all_btn.configure(state="normal")

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
            self.delete_tracks_cb.configure(state="normal")
        else:
            self.delete_tracks_var.set(False)
            self.delete_tracks_cb.configure(state="disabled")

    def _on_flat_episodes_toggle(self):
        """Updates the rename folder checkbox text dynamically depending on flat mode."""
        if self.flat_episodes_var.get():
            self.rename_folder_cb.configure(text="📁 Episoden-Ordner anlegen")
        else:
            self.rename_folder_cb.configure(text="📁 Episoden-Ordner umbenennen")
        self._scan_folder(reset_states=True)

    def _on_delete_tracks_toggle(self):
        pass

    def _on_cover_source_changed(self):
        """Immediately re-evaluates and loads cover art when any cover source checkbox is toggled in a background thread."""
        if not self.scan_results or self.current_album_idx not in range(len(self.scan_results)):
            return

        self._cover_fetch_token += 1
        current_token = self._cover_fetch_token

        album = self.scan_results[self.current_album_idx]
        folder_path = album["folder_path"]
        metadata = self.current_metadata

        use_embedded = self.source_embedded_var.get() and album["has_embedded_cover"]

        if use_embedded:
            cover_bytes = None
            try:
                from mutagen.mp3 import MP3
                t0 = album["tracks"][0]
                audio = MP3(t0["filepath"])
                if audio.tags:
                    for key in audio.tags.keys():
                        if key.startswith("APIC"):
                            cover_bytes = audio.tags[key].data
                            break
            except Exception as e:
                print(f"Error loading embedded cover: {e}")

            if cover_bytes:
                self.cover_bytes = cover_bytes
                self._display_cover_image(cover_bytes)
                self.cover_status_lbl.configure(text="Originales eingebettetes Cover", text_color="#2b712b")
                self._save_current_album_state()
                return

        # Show searching status label while thread fetches online/local cover
        self.cover_status_lbl.configure(text="⏳ Suche Cover...", text_color="orange")

        def fetch_cover_thread(token):
            cover_bytes = None
            cover_status = "Kein Cover geladen"
            cover_color = "gray"

            found_year = None
            if self.cover_var.get() or ("year" in self.form_entries and not self.form_entries["year"].get().strip()):
                sources = self._get_active_cover_sources()
                if sources:
                    artist = self.form_entries["album_artist"].get() if "album_artist" in self.form_entries else (metadata.album_artist if metadata else "")
                    album_title = self.form_entries["album"].get() if "album" in self.form_entries else (metadata.album if metadata else "")
                    episode_title = self.form_entries["episode_title"].get() if "episode_title" in self.form_entries else getattr(metadata, 'episode_title', None)

                    if artist or album_title:
                        ep_num = self.form_entries["series_part"].get() if "series_part" in self.form_entries else (getattr(metadata, 'series_part', None) if metadata else "")
                        candidates = CoverDownloader.search_cover_candidates(artist, album_title, episode_title, sources=sources, episode_num=ep_num)
                        if candidates and candidates[0].get("score", 0) >= 10:
                            best = candidates[0]
                            found_year = best.get("year")
                            if self.cover_var.get() and best.get("url"):
                                cover_bytes = CoverDownloader.download_image(best["url"])
                                if cover_bytes:
                                    cover_status = "Cover online geladen"
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

            def apply_ui():
                # Ignore stale thread results if user took another action in the meantime
                if token != self._cover_fetch_token:
                    return

                self.cover_bytes = cover_bytes
                if cover_bytes:
                    self._display_cover_image(cover_bytes)
                    self.cover_status_lbl.configure(text=cover_status, text_color=cover_color)
                else:
                    self.current_ctk_image = None
                    try:
                        self.cover_img_label.configure(text="Kein Cover geladen", image=None)
                        if hasattr(self.cover_img_label, "_draw"):
                            self.cover_img_label._draw()
                    except Exception:
                        pass
                    self.cover_status_lbl.configure(text=cover_status, text_color=cover_color)
                    self.crop_cover_btn.configure(state="disabled")

                if found_year:
                    self._auto_fill_year_if_missing(found_year)

                self._save_current_album_state()

            self.after(0, apply_ui)

        threading.Thread(target=fetch_cover_thread, args=(current_token,), daemon=True).start()

    def _format_pattern(self, pattern: str, ctx: Dict[str, Any]) -> str:
        """Evaluates custom pattern tokens using metadata context dictionary."""
        if not pattern:
            return ""

        series = ctx.get("series") or ctx.get("album_artist") or ""
        ep_num = ctx.get("series_part")
        ep_title = ctx.get("episode_title") or ""
        album = ctx.get("album") or ""
        year = str(ctx.get("year") or "")
        artist = ctx.get("artist") or series
        track_num = ctx.get("track_number")
        clean_title = ctx.get("clean_title") or ep_title

        # Episode number variants
        ep_str = str(ep_num) if ep_num is not None else ""
        try:
            ep_int = int(ep_num) if ep_num is not None else None
            ep_02 = f"{ep_int:02d}" if ep_int is not None else ep_str
            ep_03 = f"{ep_int:03d}" if ep_int is not None else ep_str
        except (ValueError, TypeError):
            ep_02 = ep_str
            ep_03 = ep_str

        # Track number variants
        tr_str = str(track_num) if track_num is not None else ""
        try:
            tr_int = int(track_num) if track_num is not None else None
            tr_02 = f"{tr_int:02d}" if tr_int is not None else tr_str
            tr_03 = f"{tr_int:03d}" if tr_int is not None else tr_str
        except (ValueError, TypeError):
            tr_02 = tr_str
            tr_03 = tr_str

        res = pattern
        res = res.replace("%Folgennummer:03d%", ep_03)
        res = res.replace("%Folgennummer:02d%", ep_02)
        res = res.replace("%Folgennummer%", ep_str)

        res = res.replace("%Track:03d%", tr_03)
        res = res.replace("%Track:02d%", tr_02)
        res = res.replace("%Track%", tr_str)

        res = res.replace("%Serie%", series)
        res = res.replace("%Folgentitel%", clean_title)
        res = res.replace("%Album%", album)
        res = res.replace("%Jahr%", year)
        res = res.replace("%Interpret%", artist)

        return res

    def _update_live_preview(self):
        """Updates live preview of target folder name and target MP3 file names as a directory tree."""
        if not hasattr(self, "structure_tab") or not hasattr(self.structure_tab, "preview_textbox"):
            return

        album_artist = self.form_entries["album_artist"].get().strip() if "album_artist" in self.form_entries else ""
        album = self.form_entries["album"].get().strip() if "album" in self.form_entries else ""
        ep_title = self.form_entries["episode_title"].get().strip() if "episode_title" in self.form_entries else ""
        series = self.form_entries["series"].get().strip() if "series" in self.form_entries else album_artist
        
        ep_part_str = self.form_entries["series_part"].get().strip() if "series_part" in self.form_entries else ""
        try:
            ep_part = int(ep_part_str) if ep_part_str.isdigit() else None
        except Exception:
            ep_part = None

        year_str = self.form_entries["year"].get().strip() if "year" in self.form_entries else ""
        try:
            year_val = int(year_str) if year_str.isdigit() else None
        except Exception:
            year_val = None

        folder_path_name = self.scan_results[self.current_album_idx]["folder_name"] if (self.scan_results and self.current_album_idx in range(len(self.scan_results))) else "Unbenannter Ordner"

        folder_pattern = self.structure_tab.get_folder_pattern()
        file_pattern = self.structure_tab.get_file_pattern()

        ctx = {
            "series": series or album_artist,
            "album_artist": album_artist,
            "series_part": ep_part,
            "episode_title": ep_title,
            "album": album,
            "year": year_val,
            "artist": album_artist
        }

        if self.rename_folder_var.get() and folder_pattern:
            ep_folder_raw = self._format_pattern(folder_pattern, ctx)
        else:
            ep_folder_raw = folder_path_name

        if not ep_folder_raw.strip():
            ep_folder_raw = album or "Unbenannter Ordner"

        import re
        folder_segments = [seg.strip(" -_\t\r\n") for seg in re.split(r'[/\\]', ep_folder_raw) if seg.strip()]
        clean_segments = []
        for seg in folder_segments:
            for char in [':', '*', '?', '"', '<', '>', '|']:
                seg = seg.replace(char, "_")
            seg = seg.strip(" -_\t\r\n")
            if seg:
                clean_segments.append(seg)

        if not clean_segments:
            clean_segments = ["Unbenannter Ordner"]

        # Insert parent series folder if requested and not already top segment
        if self.parent_series_var.get() and album_artist:
            clean_series = album_artist.strip(" -_\t\r\n")
            for char in [':', '*', '?', '"', '<', '>', '|', '/', '\\']:
                clean_series = clean_series.replace(char, "_")
            if clean_segments[0].lower() != clean_series.lower():
                clean_segments.insert(0, clean_series)

        self.structure_tab.preview_textbox.delete("0.0", tk.END)

        tree_lines = []
        current_indent = ""

        for idx, seg in enumerate(clean_segments):
            if idx == 0:
                tree_lines.append(f"📁 {seg}")
                current_indent = "     "
            else:
                tree_lines.append(f"{current_indent[:-5]}└── 📁 {seg}")
                current_indent += "     "

        indent = current_indent[:-5]

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

                t_ctx = dict(ctx)
                t_ctx["track_number"] = num_val
                t_ctx["clean_title"] = clean_t

                filename = self._format_pattern(file_pattern, t_ctx)
                if not filename.lower().endswith(".mp3"):
                    filename += ".mp3"

                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    filename = filename.replace(char, "_")

                is_last_file = (idx == file_count)
                bullet = "└── " if is_last_file else "├── "
                tree_lines.append(f"{indent}{bullet}📄 {filename}")

        self.structure_tab.preview_textbox.insert("0.0", "\n".join(tree_lines))

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
        if not img_bytes:
            self.current_ctk_image = None
            try:
                self.cover_img_label.configure(image=None, text="Kein Cover geladen")
                if hasattr(self.cover_img_label, "_draw"):
                    self.cover_img_label._draw()
            except Exception:
                pass
            self.crop_cover_btn.configure(state="disabled")
            return

        try:
            pil_img = Image.open(io.BytesIO(img_bytes))
            # Convert CMYK, P, L or other modes to RGB/RGBA for CustomTkinter compatibility
            if pil_img.mode not in ("RGB", "RGBA"):
                pil_img = pil_img.convert("RGB")

            pil_img = pil_img.copy()
            pil_img.thumbnail((300, 300))

            w, h = max(1, pil_img.width), max(1, pil_img.height)
            self.current_ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))
            self.keep_ctk_images.append(self.current_ctk_image)
            self.cover_img_label.configure(image=self.current_ctk_image, text="")
            if hasattr(self.cover_img_label, "_draw"):
                self.cover_img_label._draw()
            self.crop_cover_btn.configure(state="normal")
        except Exception as e:
            print(f"Error rendering cover image: {e}")
            self.current_ctk_image = None
            try:
                self.cover_img_label.configure(image=None, text="Fehler beim Rendern")
                if hasattr(self.cover_img_label, "_draw"):
                    self.cover_img_label._draw()
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
        self.llm_status_lbl.configure(text="🔴 LLM Analyse fehlgeschlagen", text_color="#d9534f")
        messagebox.showerror("LLM-Analyse Fehler", f"Die LLM-Analyse schlug fehl:\n{err_msg}")
        self.scan_textbox.insert(tk.END, f"\n❌ LLM-Analyse fehlgeschlagen: {err_msg}")
        self.content_tabview.set("Scannen und Ordnerstruktur")

    def _apply_metadata(self):
        if not self.scan_results:
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
            
            ep_title = self.form_entries["episode_title"].get().strip() if "episode_title" in self.form_entries else clean_title
            ep_part_str = self.form_entries["series_part"].get().strip() if "series_part" in self.form_entries else ""
            try:
                ep_part = int(ep_part_str) if ep_part_str.isdigit() else None
            except Exception:
                ep_part = None

            series_name = self.form_entries["series"].get().strip() if "series" in self.form_entries else album_artist

            t_ctx = {
                "series": series_name or album_artist,
                "album_artist": album_artist,
                "series_part": ep_part,
                "episode_title": ep_title,
                "album": album_name,
                "year": year,
                "artist": album_artist,
                "track_number": track_num,
                "clean_title": clean_title
            }

            file_pattern = self.structure_tab.get_file_pattern()
            new_filename = self._format_pattern(file_pattern, t_ctx)
            if not new_filename.lower().endswith(".mp3"):
                new_filename += ".mp3"

            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                new_filename = new_filename.replace(char, "_")

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

        def on_confirm():
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

        SummaryDialog(self, log_msgs=log_msgs, is_dry_run=is_dry_run, on_confirm_callback=on_confirm)

    def _apply_all_metadata(self):
        if not self.scan_results:
            messagebox.showinfo("Keine Alben", "Es wurden keine Alben gescannt oder geladen.")
            return

        try:
            self._save_current_album_state()
            is_dry_run = self.dry_run_var.get()
            total_albums = len(self.scan_results)

            log_msgs = []
            log_msgs.append(f"=== BATCH-{'TESTLAUF (Dry-Run)' if is_dry_run else 'SCHREIBOPERATION'} FÜR ALLE {total_albums} HÖRSPIELE ===")

            all_batch_items = []

            for idx, album in enumerate(self.scan_results):
                tracks = album.get("tracks", [])
                if album.get("flat_mode") and tracks:
                    state_key = tracks[0]["filepath"]
                else:
                    state_key = album.get("folder_path", "")

                state = self.album_states.get(state_key, {})
                form_data = state.get("form_data", {})
                track_rows = state.get("track_rows", [])

                # Fallback if track_rows was not populated in state
                if not track_rows and tracks:
                    track_rows = []
                    for i_t, t in enumerate(tracks, 1):
                        clean_t = t.get("title") or Path(t["filename"]).stem
                        track_rows.append({
                            "original_filename": t["filename"],
                            "filepath": t["filepath"],
                            "clean_title": clean_t,
                            "track_number": t.get("track_number") or i_t
                        })

                album_artist = form_data.get("album_artist") or album.get("album_artist") or album.get("folder_name", "")
                album_name = form_data.get("album") or album.get("album") or album.get("folder_name", "")

                import re
                match = re.match(r"^(\d+)\s*-\s*(.*)$", album_name)
                if match:
                    num_str, title_str = match.groups()
                    album_name = f"{int(num_str):02d} - {title_str}"

                ep_title = form_data.get("episode_title") or (album_name.split(" - ", 1)[-1] if " - " in album_name else album_name)
                series_part = form_data.get("series_part") or ""

                genre = form_data.get("genre", "Hörspiel")
                year_str = form_data.get("year", "")
                year = int(year_str) if year_str and year_str.isdigit() else None

                log_msgs.append(f"\n[{idx+1}/{total_albums}] Ordner: {album.get('folder_name', 'Unbekannt')}")
                log_msgs.append(f"  Album-Interpret: {album_artist}")
                log_msgs.append(f"  Album (Folge):  {album_name}")
                log_msgs.append(f"  Genre:          {genre}")
                log_msgs.append(f"  Jahr:           {year if year else 'Keines'}")

                changes = []
                for row in track_rows:
                    orig_filename = row.get("original_filename", "")
                    filepath = row.get("filepath", "")
                    track_num = row.get("track_number", 1)
                    clean_title = row.get("clean_title", "")
                    new_filename = f"{track_num:02d} - {clean_title}.mp3"
                    changes.append({
                        "orig_filename": orig_filename,
                        "filepath": filepath,
                        "track_number": track_num,
                        "clean_title": clean_title,
                        "new_filename": new_filename
                    })

                changes.sort(key=lambda x: x["track_number"])

                for change in changes:
                    log_msgs.append(f"  * Track {change['track_number']:02d}: {change['clean_title']}")

                c_bytes = state.get("cover_bytes")
                if not c_bytes and album.get("has_embedded_cover") and self.source_embedded_var.get():
                    try:
                        from mutagen.mp3 import MP3
                        if tracks:
                            t0 = tracks[0]
                            audio = MP3(t0["filepath"])
                            if audio.tags:
                                for key in audio.tags.keys():
                                    if key.startswith("APIC"):
                                        c_bytes = audio.tags[key].data
                                        break
                    except Exception:
                        pass

                if not c_bytes:
                    local_c = self._find_local_cover(album["folder_path"])
                    if local_c:
                        try:
                            with open(local_c, "rb") as f:
                                c_bytes = f.read()
                        except Exception:
                            pass

                composer = form_data.get("composer") or ""
                publisher = form_data.get("publisher") or ""
                comment = form_data.get("comment") or ""
                disc_number = form_data.get("disc_number") or ""

                all_batch_items.append({
                    "album": album,
                    "album_artist": album_artist,
                    "album_name": album_name,
                    "episode_title": ep_title,
                    "series_part": series_part,
                    "genre": genre,
                    "year": year,
                    "composer": composer,
                    "publisher": publisher,
                    "comment": comment,
                    "disc_number": disc_number,
                    "changes": changes,
                    "cover_bytes": c_bytes
                })

            def on_confirm():
                if not is_dry_run:
                    self.apply_btn.configure(state="disabled")
                    self.apply_all_btn.configure(state="disabled", text="Speichere alle...")
                    self.progress_bar.grid(row=0, column=2, padx=10, pady=2, sticky="e")
                    self.loading_lbl.grid(row=0, column=3, padx=10, pady=2, sticky="e")
                    self.loading_lbl.configure(text=f"💾 Speichere {total_albums} Alben...", text_color="#1f538d")
                    self.progress_bar.start()

                    threading.Thread(
                        target=self._run_batch_all_write_operation, 
                        args=(all_batch_items,), 
                        daemon=True
                    ).start()
                else:
                    messagebox.showinfo("Dry-Run Beendet", f"Der Dry-Run für alle {total_albums} Alben wurde erfolgreich simuliert. Es wurden keine Dateien verändert.")

            SummaryDialog(self, log_msgs=log_msgs, is_dry_run=is_dry_run, on_confirm_callback=on_confirm)

        except Exception as err:
            messagebox.showerror("Fehler beim Vorbereiten", f"Konnte Änderungen für alle Alben nicht vorbereiten: {err}")

    def _run_batch_all_write_operation(self, all_batch_items):
        total = len(all_batch_items)
        try:
            for idx, item in enumerate(all_batch_items, start=1):
                self.after(0, lambda i=idx, t=total, name=item["album_name"]: self.loading_lbl.configure(
                    text=f"💾 Speichere Album {i}/{t}: {name}..."
                ))
                saved_cover = self.cover_bytes
                self.cover_bytes = item["cover_bytes"]
                self._run_write_operation(
                    item["album"], 
                    item["album_artist"], 
                    item["album_name"], 
                    item["genre"], 
                    item["year"], 
                    item["changes"],
                    is_batch=True,
                    composer=item.get("composer"),
                    publisher=item.get("publisher"),
                    comment=item.get("comment"),
                    disc_number=item.get("disc_number")
                )
                self.cover_bytes = saved_cover

            def on_done():
                self._stop_loading_indicator()
                messagebox.showinfo("Erfolg", f"Alle {total} Alben wurden erfolgreich gespeichert und getaggt!")
                self.scan_textbox.insert(tk.END, f"\n✅ Alle {total} Alben erfolgreich gespeichert und getaggt.")
                self._scan_folder(reset_states=True)

            self.after(0, on_done)
        except Exception as e:
            self.after(0, lambda err=str(e): messagebox.showerror("Fehler beim Speichern", f"Fehler beim Speichern der Alben: {err}"))
        finally:
            self.is_processing = False
            self.after(0, lambda: self.progress_bar.stop())
            self.after(0, lambda: self.progress_bar.grid_remove())
            self.after(0, lambda: self.apply_btn.configure(state="normal"))
            self.after(0, lambda: self.apply_all_btn.configure(state="normal", text="💾 Alle Alben auf einmal speichern"))

    def _run_write_operation(
        self,
        album,
        album_artist,
        album_name,
        genre,
        year,
        changes,
        is_batch: bool = False,
        composer: Optional[str] = None,
        publisher: Optional[str] = None,
        comment: Optional[str] = None,
        disc_number: Optional[str] = None
    ):
        if composer is None:
            composer = self.form_entries["composer"].get().strip() if "composer" in self.form_entries else None
        if publisher is None:
            publisher = self.form_entries["publisher"].get().strip() if "publisher" in self.form_entries else None
        if comment is None:
            comment = self.form_entries["comment"].get().strip() if "comment" in self.form_entries else None
        if disc_number is None:
            disc_number = self.form_entries["disc_number"].get().strip() if "disc_number" in self.form_entries else None

        # Auto-learn / update SeriesDatabase with finalized series name & genre
        if album_artist and genre:
            try:
                from series_db import SeriesDatabase
                SeriesDatabase.set_series_genre(
                    series_name=album_artist,
                    genre=genre,
                    composer=composer,
                    publisher=publisher,
                    comment=comment
                )
            except Exception as db_err:
                print(f"[SeriesDB Info] {db_err}")

        folder_path = Path(album["folder_path"])
        is_flat = album.get("flat_mode", False)

        # 0. In flat mode, determine and create target folder immediately if option is active
        if is_flat and (self.rename_folder_var.get() or self.parent_series_var.get()):
            target_ep_folder_name = album_name if (self.rename_folder_var.get() and album_name) else album["folder_name"]
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                target_ep_folder_name = target_ep_folder_name.replace(char, "_")

            if self.parent_series_var.get() and album_artist:
                clean_series_name = album_artist
                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    clean_series_name = clean_series_name.replace(char, "_")
                final_folder_path = folder_path / clean_series_name / target_ep_folder_name
            else:
                final_folder_path = folder_path / target_ep_folder_name

            final_folder_path.mkdir(parents=True, exist_ok=True)
            write_dest_dir = final_folder_path
        else:
            write_dest_dir = folder_path
        
        try:
            # 1. Save Cover to folder if downloaded/provided
            if self.cover_bytes:
                cover_file = write_dest_dir / "cover.jpg"
                with open(cover_file, "wb") as f:
                    f.write(self.cover_bytes)

            # 2. Write Tags and Rename Files (If merging, isolate original tracks into 'Tracks' subfolder first)
            new_file_paths = []
            if self.merge_var.get():
                target_tracks_dir = write_dest_dir / "Tracks"
                target_tracks_dir.mkdir(parents=True, exist_ok=True)
            else:
                target_tracks_dir = write_dest_dir

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
                    composer=composer,
                    publisher=publisher,
                    comment=comment,
                    disc_number=disc_number,
                    cover_bytes=self.cover_bytes
                )

                # Rename/Move the file on disk into target_tracks_dir
                target_path = target_tracks_dir / change["new_filename"]
                if orig_path != target_path:
                    # Prevent overwriting
                    counter = 1
                    test_path = target_path
                    while test_path.exists() and test_path != orig_path:
                        test_path = target_tracks_dir / f"{target_path.stem} ({counter}){target_path.suffix}"
                        counter += 1
                    target_path = test_path
                    
                    os.rename(orig_path, target_path)

                change["actual_moved_path"] = str(target_path)
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
                        
                    merged_out = write_dest_dir / merged_filename
                    
                    # Sort file paths strictly by assigned track_number order
                    sorted_changes = sorted(changes, key=lambda x: x["track_number"])
                    sorted_paths = [c.get("actual_moved_path", str(target_tracks_dir / c["new_filename"])) for c in sorted_changes]

                    try:
                        # Build chapter timing data from assigned tracks
                        chapter_data = ChapterManager.build_chapter_data(sorted_changes)

                        # FFmpeg merge with automatic fallback verification
                        merge_status = FileMerger.merge_files_with_fallback(sorted_paths, str(merged_out))
                        print(f"[Merge Status] {merge_status}")
                        
                        merged_file_path = str(merged_out)
                        
                        # Determine pure episode title (without '04 - ' prefix) for Plex from UI form
                        episode_title = self.form_entries["episode_title"].get().strip() if "episode_title" in self.form_entries else ""
                        if not episode_title:
                            episode_title = self.current_metadata.episode_title if (self.current_metadata and self.current_metadata.episode_title) else (album_name.split(" - ", 1)[-1] if " - " in album_name else album_name)

                        try:
                            episode_num = int(self.form_entries["series_part"].get().strip())
                        except Exception:
                            episode_num = 1

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
                            composer=composer,
                            publisher=publisher,
                            comment=comment,
                            disc_number=disc_number,
                            cover_bytes=self.cover_bytes,
                            chapters=chapter_data
                        )
                        # Clean up original tracks directory if delete option is active
                        if self.delete_tracks_var.get():
                            import shutil
                            try:
                                shutil.rmtree(target_tracks_dir, ignore_errors=True)
                            except Exception as e:
                                print(f"Error removing Tracks directory: {e}")
                    except Exception as merge_err:
                        self.after(0, lambda err=merge_err: messagebox.showwarning("ffmpeg Merge Fehler", f"Zusammenführung der MP3s schlug fehl: {err}"))

            # 4. Folder Renaming and Parent Series Folder Organization
            if not is_flat:
                # Determine target folder path (supports subfolders via '/')
                folder_pattern = self.structure_tab.get_folder_pattern() if hasattr(self, "structure_tab") else ""
                if self.rename_folder_var.get() and folder_pattern:
                    ctx = {
                        "series": album_artist,
                        "album_artist": album_artist,
                        "album": album_name,
                        "year": year,
                        "artist": album_artist
                    }
                    target_ep_folder_raw = self._format_pattern(folder_pattern, ctx)
                else:
                    target_ep_folder_raw = album_name if (self.rename_folder_var.get() and album_name) else album["folder_name"]

                import re
                raw_segs = [seg.strip(" -_\t\r\n") for seg in re.split(r'[/\\]', target_ep_folder_raw) if seg.strip()]
                clean_segs = []
                for seg in raw_segs:
                    for char in [':', '*', '?', '"', '<', '>', '|']:
                        seg = seg.replace(char, "_")
                    seg = seg.strip(" -_\t\r\n")
                    if seg:
                        clean_segs.append(seg)

                if not clean_segs:
                    clean_segs = [album_name or "Unbenannter Ordner"]

                if self.parent_series_var.get() and album_artist:
                    clean_series = album_artist.strip(" -_\t\r\n")
                    for char in [':', '*', '?', '"', '<', '>', '|', '/', '\\']:
                        clean_series = clean_series.replace(char, "_")
                    if clean_segs[0].lower() != clean_series.lower():
                        clean_segs.insert(0, clean_series)

                parent_base = folder_path.parent
                target_dir = parent_base
                for seg in clean_segs:
                    target_dir = target_dir / seg
                final_folder_path = target_dir

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
            else:
                # In flat mode, update album's folder path to the newly created subfolder
                album["folder_path"] = str(write_dest_dir)

            # Operations completed
            if not is_batch:
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
            if not is_batch:
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

    def _open_google_cover_search(self):
        """Opens a web browser with a Google Images query for the current audio drama cover."""
        import urllib.parse
        import webbrowser
        
        artist = self.form_entries["album_artist"].get().strip()
        album = self.form_entries["album"].get().strip()
        
        query = f"{artist} {album} Cover".strip()
        if not query or query == "Cover":
            query = "Hörspiel Cover"
            
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=isch"
        webbrowser.open(search_url)

    def _open_series_db_dialog(self):
        """Opens modal dialog for managing the series knowledge base database."""
        from series_db_dialog import SeriesDatabaseDialog
        SeriesDatabaseDialog(self)

if __name__ == "__main__":
    app = HoerspielTaggerGUI()
    app.mainloop()
