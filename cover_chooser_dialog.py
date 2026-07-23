import io
import threading
from typing import List, Dict, Any
import customtkinter as ctk
from PIL import Image
from cover_downloader import CoverDownloader

class CoverChooserDialog(ctk.CTkToplevel):
    """Modal dialog displaying candidate album covers from iTunes search."""
    def __init__(self, parent, candidates: List[Dict[str, str]], on_select_cover):
        super().__init__(parent)
        self.title("🖼 Cover-Varianten auswählen")
        self.geometry("720x560")
        self.minsize(620, 460)
        self.grab_set()

        # Center relative to parent
        self.update_idletasks()
        if parent:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = 720
            win_h = 560
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self.on_select_cover = on_select_cover
        self.candidates = candidates
        self.keep_image_refs = []

        self._build_ui()

    def _build_ui(self):
        title_lbl = ctk.CTkLabel(self, text="Gefundene Cover-Varianten auf iTunes", font=ctk.CTkFont(size=16, weight="bold"))
        title_lbl.pack(pady=10)

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(expand=True, fill="both", padx=15, pady=10)

        if not self.candidates:
            ctk.CTkLabel(scroll, text="Keine Cover-Varianten auf iTunes gefunden.", text_color="gray").pack(pady=20)
            return

        for idx, cand in enumerate(self.candidates):
            card = ctk.CTkFrame(scroll)
            card.pack(fill="x", padx=5, pady=5)
            card.grid_columnconfigure(1, weight=1)

            # Thumbnail label
            thumb_lbl = ctk.CTkLabel(card, text="Lade...", width=80, height=80, fg_color="#1e1e1e", corner_radius=6)
            thumb_lbl.grid(row=0, column=0, padx=10, pady=10)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.grid(row=0, column=1, padx=10, pady=10, sticky="w")

            ctk.CTkLabel(info_frame, text=cand["title"], font=ctk.CTkFont(weight="bold"), wraplength=380, anchor="w", justify="left").pack(anchor="w")
            ctk.CTkLabel(info_frame, text=cand["artist"], text_color="gray", wraplength=380, anchor="w", justify="left").pack(anchor="w")

            btn = ctk.CTkButton(
                card, text="Übernehmen", width=95,
                command=lambda url=cand["url"]: self._select_candidate(url),
                fg_color="#1f538d"
            )
            btn.grid(row=0, column=2, padx=10, pady=10)

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

    def _select_candidate(self, url: str):
        raw_bytes = CoverDownloader.download_image(url)
        if raw_bytes and self.on_select_cover:
            self.on_select_cover(raw_bytes)
        self.destroy()
