import io
import customtkinter as ctk
from PIL import Image

class CoverCropDialog(ctk.CTkToplevel):
    """Modal dialog for interactive cover art cropping."""
    def __init__(self, parent, img_bytes: bytes, on_crop_complete):
        super().__init__(parent)
        self.title("✂ Cover Art zuschneiden")
        self.geometry("780x660")
        self.minsize(700, 580)
        self.grab_set()

        # Center relative to parent
        self.update_idletasks()
        if parent:
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
            win_w = 780
            win_h = 660
            x = parent_x + (parent_w - win_w) // 2
            y = parent_y + (parent_h - win_h) // 2
            self.geometry(f"{win_w}x{win_h}+{x}+{y}")

        self.original_bytes = img_bytes
        self.on_crop_complete = on_crop_complete
        self.pil_image = Image.open(io.BytesIO(img_bytes))
        self.cropped_bytes = img_bytes

        self.left_var = ctk.DoubleVar(value=0.0)
        self.top_var = ctk.DoubleVar(value=0.0)
        self.right_var = ctk.DoubleVar(value=100.0)
        self.bottom_var = ctk.DoubleVar(value=100.0)

        self._build_ui()
        self._update_preview()

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header / Presets frame
        preset_frame = ctk.CTkFrame(self)
        preset_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(preset_frame, text="Schnell-Vorlagen:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)

        ctk.CTkButton(preset_frame, text="Rechte Hälfte (Frontcover 1:1)", command=lambda: self._set_preset(50, 0, 100, 100)).pack(side="left", padx=5)
        ctk.CTkButton(preset_frame, text="Linke Hälfte", command=lambda: self._set_preset(0, 0, 50, 100)).pack(side="left", padx=5)
        ctk.CTkButton(preset_frame, text="Quadratisch (Mitte)", command=lambda: self._set_square_preset()).pack(side="left", padx=5)
        ctk.CTkButton(preset_frame, text="Zurücksetzen (100%)", command=lambda: self._set_preset(0, 0, 100, 100), fg_color="gray").pack(side="left", padx=5)

        # Main preview area
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=2)
        main_frame.grid_columnconfigure(1, weight=1)

        # Preview Image Label
        self.preview_lbl = ctk.CTkLabel(main_frame, text="", fg_color="#1e1e1e", corner_radius=8)
        self.preview_lbl.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Sliders panel
        slider_panel = ctk.CTkFrame(main_frame)
        slider_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(slider_panel, text="Ausschnitt anpassen (%)", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 15))

        # Left slider
        ctk.CTkLabel(slider_panel, text="Links abschneiden:").pack(anchor="w", padx=10)
        self.slider_left = ctk.CTkSlider(slider_panel, from_=0, to=90, variable=self.left_var, command=lambda v: self._update_preview())
        self.slider_left.pack(fill="x", padx=10, pady=(0, 10))

        # Right slider
        ctk.CTkLabel(slider_panel, text="Rechts abschneiden:").pack(anchor="w", padx=10)
        self.slider_right = ctk.CTkSlider(slider_panel, from_=10, to=100, variable=self.right_var, command=lambda v: self._update_preview())
        self.slider_right.pack(fill="x", padx=10, pady=(0, 10))

        # Top slider
        ctk.CTkLabel(slider_panel, text="Oben abschneiden:").pack(anchor="w", padx=10)
        self.slider_top = ctk.CTkSlider(slider_panel, from_=0, to=90, variable=self.top_var, command=lambda v: self._update_preview())
        self.slider_top.pack(fill="x", padx=10, pady=(0, 10))

        # Bottom slider
        ctk.CTkLabel(slider_panel, text="Unten abschneiden:").pack(anchor="w", padx=10)
        self.slider_bottom = ctk.CTkSlider(slider_panel, from_=10, to=100, variable=self.bottom_var, command=lambda v: self._update_preview())
        self.slider_bottom.pack(fill="x", padx=10, pady=(0, 10))

        # Info dimension label
        self.info_dim_lbl = ctk.CTkLabel(slider_panel, text="", text_color="gray")
        self.info_dim_lbl.pack(pady=10)

        # Footer actions
        action_frame = ctk.CTkFrame(self)
        action_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkButton(action_frame, text="Zuschneiden & Übernehmen", command=self._apply_crop, fg_color="#1f538d").pack(side="right", padx=10)
        ctk.CTkButton(action_frame, text="Abbrechen", command=self.destroy, fg_color="gray").pack(side="left", padx=10)

    def _set_preset(self, l, t, r, b):
        self.left_var.set(l)
        self.top_var.set(t)
        self.right_var.set(r)
        self.bottom_var.set(b)
        self._update_preview()

    def _set_square_preset(self):
        w, h = self.pil_image.size
        if w > h:
            offset_pct = ((w - h) / (2.0 * w)) * 100.0
            self._set_preset(offset_pct, 0, 100.0 - offset_pct, 100.0)
        elif h > w:
            offset_pct = ((h - w) / (2.0 * h)) * 100.0
            self._set_preset(0, offset_pct, 100.0, 100.0 - offset_pct)
        else:
            self._set_preset(0, 0, 100.0, 100.0)

    def _update_preview(self):
        l = self.left_var.get()
        t = self.top_var.get()
        r = max(l + 5, self.right_var.get())
        b = max(t + 5, self.bottom_var.get())

        w, h = self.pil_image.size
        box = (int(w * l / 100.0), int(h * t / 100.0), int(w * r / 100.0), int(h * b / 100.0))
        cropped = self.pil_image.crop(box)

        crop_w, crop_h = cropped.size
        self.info_dim_lbl.configure(text=f"Größe: {crop_w} x {crop_h} px")

        preview_copy = cropped.copy()
        preview_copy.thumbnail((360, 360))
        self.ctk_img = ctk.CTkImage(light_image=preview_copy, dark_image=preview_copy, size=(preview_copy.width, preview_copy.height))
        self.preview_lbl.configure(image=self.ctk_img)

        out = io.BytesIO()
        if cropped.mode in ("RGBA", "P"):
            cropped = cropped.convert("RGB")
        cropped.save(out, format="JPEG", quality=95)
        self.cropped_bytes = out.getvalue()

    def _apply_crop(self):
        if self.on_crop_complete and self.cropped_bytes:
            self.on_crop_complete(self.cropped_bytes)
        self.destroy()
