import io
import threading
from typing import List, Dict, Any, Optional, Callable
import customtkinter as ctk
from PIL import Image
from cover_downloader import CoverDownloader

class CoverChooserDialog(ctk.CTkToplevel):
    """Modal dialog displaying candidate album covers from online sources with filter tabs and instant open."""

    def __init__(
        self,
        parent,
        artist: str = "",
        album: str = "",
        title: str = "",
        sources: Optional[List[str]] = None,
        on_select_cover: Optional[Callable] = None,
        candidates: Optional[List[Dict[str, Any]]] = None
    ):
        super().__init__(parent)
        self.parent = parent
        self.title("🖼 Cover-Varianten auswählen")
        self.geometry("760x580")
        self.minsize(660, 480)

        # Force window to front immediately
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
                win_w, win_h = 760, 580
                x = max(0, parent_x + (parent_w - win_w) // 2)
                y = max(0, parent_y + (parent_h - win_h) // 2)
                self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

        self.artist = artist
        self.album = album
        self.title_query = title or album
        self.sources = sources or ["discogs", "itunes", "deezer", "musicbrainz"]
        self.on_select_cover = on_select_cover
        self.candidates = candidates or []
        self.episode_num = getattr(parent, 'episode_num', None)
        self.filtered_candidates = []
        self.current_filter = "all"
        self.keep_image_refs = []
        self.filter_buttons = {}

        self._build_ui()

        # Remove topmost after brief delay
        self.after(200, lambda: self.attributes("-topmost", False))

        # If candidates were pre-fetched, render them directly; otherwise start async search
        if candidates:
            self._on_search_completed(candidates)
        else:
            threading.Thread(target=self._run_async_search, daemon=True).start()

    def _build_ui(self):
        # Header title
        title_lbl = ctk.CTkLabel(
            self, 
            text=f"🖼 Cover-Varianten für '{self.album or self.title_query}'", 
            font=ctk.CTkFont(size=15, weight="bold")
        )
        title_lbl.pack(pady=(12, 4))

        # Filter Tabs Frame
        self.tabs_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tabs_frame.pack(fill="x", padx=15, pady=4)

        # Progress bar & Loading status
        self.status_lbl = ctk.CTkLabel(
            self, 
            text="⏳ Suche Cover-Varianten auf Discogs, iTunes, Deezer, MusicBrainz...", 
            font=ctk.CTkFont(size=12),
            text_color="orange"
        )
        self.status_lbl.pack(pady=2)

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate", width=300)
        self.progress_bar.pack(pady=4)
        self.progress_bar.start()

        # Scrollable candidates container
        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(expand=True, fill="both", padx=15, pady=(5, 15))

    def _run_async_search(self):
        """Runs candidate search in background thread."""
        provider_limits = None
        if hasattr(self.parent, "cover_panel") and hasattr(self.parent.cover_panel, "get_provider_limits"):
            provider_limits = self.parent.cover_panel.get_provider_limits()
        elif hasattr(self.parent, "get_provider_limits"):
            provider_limits = self.parent.get_provider_limits()

        cands = CoverDownloader.search_cover_candidates(
            self.artist, self.album, self.title_query, sources=self.sources, episode_num=self.episode_num, provider_limits=provider_limits
        )
        self.after(0, lambda: self._on_search_completed(cands))

    def _on_search_completed(self, cands: List[Dict[str, Any]]):
        """Called on main UI thread when candidate search finishes."""
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

        self.candidates = cands
        if not cands:
            self.status_lbl.configure(
                text="❌ Keine Cover-Varianten auf den aktiven Portalen gefunden.", 
                text_color="#7a2b2b"
            )
            return

        self.status_lbl.configure(
            text=f"✓ {len(cands)} Cover-Varianten auf online Portalen gefunden.", 
            text_color="#2b712b"
        )

        self._build_filter_tabs()
        self._filter_and_render("all")

    def _build_filter_tabs(self):
        """Builds interactive filter tabs/chips for provider sources."""
        for widget in self.tabs_frame.winfo_children():
            widget.destroy()

        # Count per source
        counts = {"all": len(self.candidates)}
        for c in self.candidates:
            src = c.get("source", "other")
            counts[src] = counts.get(src, 0) + 1

        provider_names = [
            ("all", f"Alle ({counts['all']})"),
            ("discogs", f"📻 Discogs ({counts.get('discogs', 0)})"),
            ("itunes", f"🎵 iTunes ({counts.get('itunes', 0)})"),
            ("deezer", f"🎧 Deezer ({counts.get('deezer', 0)})"),
            ("musicbrainz", f"🎼 MusicBrainz ({counts.get('musicbrainz', 0)})"),
        ]

        for code, label_text in provider_names:
            if code != "all" and counts.get(code, 0) == 0:
                continue # Skip providers with 0 results

            btn = ctk.CTkButton(
                self.tabs_frame,
                text=label_text,
                width=110,
                height=26,
                font=ctk.CTkFont(size=11),
                fg_color="#1f538d" if code == "all" else "#333333",
                hover_color="#143960",
                command=lambda c=code: self._filter_and_render(c)
            )
            btn.pack(side="left", padx=3)
            self.filter_buttons[code] = btn

    def _filter_and_render(self, source_code: str):
        """Filters candidates by source and renders candidate cards."""
        self.current_filter = source_code

        # Update button highlight colors
        for code, btn in self.filter_buttons.items():
            if code == source_code:
                btn.configure(fg_color="#1f538d")
            else:
                btn.configure(fg_color="#333333")

        # Clear scrollable container
        for widget in self.scroll.winfo_children():
            widget.destroy()

        if source_code == "all":
            self.filtered_candidates = self.candidates
        else:
            self.filtered_candidates = [c for c in self.candidates if c.get("source") == source_code]

        if not self.filtered_candidates:
            ctk.CTkLabel(self.scroll, text="Keine Treffer für diesen Anbieter.", text_color="gray").pack(pady=20)
            return

        for idx, cand in enumerate(self.filtered_candidates):
            card = ctk.CTkFrame(self.scroll)
            card.pack(fill="x", padx=5, pady=5)
            card.grid_columnconfigure(1, weight=1)

            # Thumbnail label
            thumb_lbl = ctk.CTkLabel(card, text="Lade...", width=80, height=80, fg_color="#1e1e1e", corner_radius=6)
            thumb_lbl.grid(row=0, column=0, padx=10, pady=10)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

            artist_text = cand.get("artist", "")
            if cand.get("year"):
                artist_text += f" ({cand['year']})"

            ctk.CTkLabel(info_frame, text=cand["title"], font=ctk.CTkFont(weight="bold"), wraplength=420, anchor="w", justify="left").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=artist_text, text_color="gray", wraplength=420, anchor="w", justify="left").pack(anchor="w")

            btn = ctk.CTkButton(
                card, text="Übernehmen", width=105,
                command=lambda c=cand: self._select_candidate(c),
                fg_color="#1f538d",
                hover_color="#143960"
            )
            btn.grid(row=0, column=2, padx=15, pady=10)

            # Async thumbnail fetcher
            threading.Thread(target=self._load_thumb, args=(cand["thumb"], thumb_lbl), daemon=True).start()

    def _load_thumb(self, url: str, label_widget: ctk.CTkLabel):
        try:
            raw = CoverDownloader.download_image(url)
            if raw:
                img = Image.open(io.BytesIO(raw))
                img.thumbnail((80, 80))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.keep_image_refs.append(ctk_img)
                self.after(0, lambda: label_widget.configure(image=ctk_img, text=""))
        except Exception:
            pass

    def _select_candidate(self, candidate: Dict[str, Any]):
        url = candidate.get("url", "")
        year = candidate.get("year")
        cand_title = candidate.get("title", "")
        def do_download():
            raw_bytes = CoverDownloader.download_image(url)
            def apply():
                cb = self.on_select_cover
                self.destroy()
                if raw_bytes and cb:
                    try:
                        cb(raw_bytes, year, cand_title)
                    except TypeError:
                        try:
                            cb(raw_bytes, year)
                        except TypeError:
                            cb(raw_bytes)
            self.after(0, apply)

        threading.Thread(target=do_download, daemon=True).start()
