import tkinter as tk
import customtkinter as ctk

class AnalysisProgressDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title("🤖 LLM Analyse läuft...")
        self.geometry("500x200")
        self.resizable(False, False)

        # Disable closing the dialog via the close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)

        # Make modal and block parent window clicks
        self.attributes("-topmost", True)
        self.lift()
        self.focus_force()
        self.grab_set()

        # Center window relative to parent
        self.update_idletasks()
        if parent:
            try:
                parent_x = parent.winfo_rootx()
                parent_y = parent.winfo_rooty()
                parent_w = parent.winfo_width()
                parent_h = parent.winfo_height()
                win_w, win_h = 500, 200
                x = max(0, parent_x + (parent_w - win_w) // 2)
                y = max(0, parent_y + (parent_h - win_h) // 2)
                self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

        self._build_ui()
        self.after(200, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        self.title_lbl = ctk.CTkLabel(
            self, 
            text="🤖 LLM Batch-Analyse läuft...", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.title_lbl.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.info_lbl = ctk.CTkLabel(
            self, 
            text="Bereite Analyse vor...", 
            font=ctk.CTkFont(size=12),
            text_color="gray",
            wraplength=460,
            justify="left"
        )
        self.info_lbl.grid(row=1, column=0, padx=20, pady=5, sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate", width=460)
        self.progress_bar.grid(row=2, column=0, padx=20, pady=15, sticky="ew")
        self.progress_bar.set(0.0)

        self.status_lbl = ctk.CTkLabel(
            self, 
            text="Warte auf Start...", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.status_lbl.grid(row=3, column=0, padx=20, pady=(0, 15), sticky="w")

    def update_progress(self, current: int, total: int, folder_name: str):
        ratio = float(current) / float(total) if total > 0 else 0.0
        self.progress_bar.set(ratio)
        self.info_lbl.configure(text=f"Ordner: {folder_name}")
        self.status_lbl.configure(text=f"Analysiere Ordner {current} von {total} ({int(ratio * 100)}%)")
        self.update_idletasks()

    def close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
