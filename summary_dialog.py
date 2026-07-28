import tkinter as tk
import customtkinter as ctk
from typing import List, Callable

class SummaryDialog(ctk.CTkToplevel):
    """Confirmation modal dialog displaying proposed tagging/renaming changes before execution."""

    def __init__(self, parent, log_msgs: List[str], is_dry_run: bool, on_confirm_callback: Callable[[], None]):
        super().__init__(parent)
        self.parent = parent
        self.log_msgs = log_msgs
        self.is_dry_run = is_dry_run
        self.on_confirm_callback = on_confirm_callback

        self.title("Bestätigung der Änderungen")
        self.geometry("720x540")
        self.transient(parent)
        self.grab_set()

        self._build_ui()
        self.after(10, self._center_window)

    def _center_window(self):
        try:
            self.update_idletasks()
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
            win_w, win_h = 720, 540
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            self.lift()
            self.focus_force()
        except Exception:
            pass

    def _build_ui(self):
        tb = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=11))
        tb.pack(expand=True, fill="both", padx=15, pady=15)
        tb.insert("0.0", "\n".join(self.log_msgs))

        if self.is_dry_run:
            hint_lbl = ctk.CTkLabel(
                self,
                text="💡 TESTLAUF-MODUS AKTIV: Es werden keine Dateien verändert.\nEntferne das Häkchen bei 'Dry-Run (Testlauf)' in der linken Seitenleiste, um echte Änderungen zu speichern.",
                text_color="#e2b93b",
                font=ctk.CTkFont(weight="bold")
            )
            hint_lbl.pack(padx=15, pady=(0, 10))

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        def on_confirm():
            self.destroy()
            self.on_confirm_callback()

        confirm_btn = ctk.CTkButton(
            btn_frame,
            text="Echte Änderungen anwenden!" if not self.is_dry_run else "Dry-Run simulieren",
            command=on_confirm,
            fg_color="#1f538d" if not self.is_dry_run else "#2b712b"
        )
        confirm_btn.pack(side="right", padx=10)

        cancel_btn = ctk.CTkButton(btn_frame, text="Abbrechen", command=self.destroy, fg_color="gray")
        cancel_btn.pack(side="left", padx=10)
