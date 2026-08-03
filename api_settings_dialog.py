import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Callable, Optional
import config
from config import DEFAULT_SYSTEM_PROMPT
from openai import OpenAI

class ApiSettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save_callback: Callable[[str, str, str, str], None]):
        super().__init__(parent)
        self.parent = parent
        self.on_save_callback = on_save_callback

        self.title("⚙️ API & Prompt Einstellungen")
        self.geometry("640x620")
        self.minsize(580, 520)
        
        # Bring window to front immediately
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
                win_w, win_h = 640, 620
                x = max(0, parent_x + (parent_w - win_w) // 2)
                y = max(0, parent_y + (parent_h - win_h) // 2)
                self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

        self._build_ui()
        self._load_values()

        # Unset topmost after brief delay
        self.after(200, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1) # Prompt textbox row expands

        # Title / Description
        header_lbl = ctk.CTkLabel(
            self, 
            text="⚙️ LLM API & System Prompt Einstellungen", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        desc_lbl = ctk.CTkLabel(
            self, 
            text="Hier kannst du den LLM-Server (z. B. LM Studio, Ollama, OpenAI) sowie den KI-Prompt für die Metadaten-Analyse konfigurieren.",
            wraplength=580,
            text_color="gray",
            justify="left"
        )
        desc_lbl.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        # Connection Settings Frame
        conn_frame = ctk.CTkFrame(self)
        conn_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        conn_frame.grid_columnconfigure(1, weight=1)

        # Base URL
        ctk.CTkLabel(conn_frame, text="Base URL:").grid(row=0, column=0, padx=10, pady=6, sticky="w")
        self.api_url_ent = ctk.CTkEntry(conn_frame, placeholder_text="http://127.0.0.1:1234/v1")
        self.api_url_ent.grid(row=0, column=1, padx=10, pady=6, sticky="ew")

        # API Key
        ctk.CTkLabel(conn_frame, text="API Key:").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        self.api_key_ent = ctk.CTkEntry(conn_frame, show="*", placeholder_text="lm-studio")
        self.api_key_ent.grid(row=1, column=1, padx=10, pady=6, sticky="ew")

        # Model ID
        ctk.CTkLabel(conn_frame, text="Modell / Agent ID:").grid(row=2, column=0, padx=10, pady=6, sticky="w")
        self.model_ent = ctk.CTkEntry(conn_frame, placeholder_text="meta-llama-3-8b-instruct")
        self.model_ent.grid(row=2, column=1, padx=10, pady=6, sticky="ew")

        # Discogs API Token (Optional)
        ctk.CTkLabel(conn_frame, text="Discogs Token (Optional):").grid(row=3, column=0, padx=10, pady=6, sticky="w")
        self.discogs_token_ent = ctk.CTkEntry(conn_frame, show="*", placeholder_text="Personal Access Token")
        self.discogs_token_ent.grid(row=3, column=1, padx=10, pady=6, sticky="ew")

        # Test connection button & status label row
        test_frame = ctk.CTkFrame(conn_frame, fg_color="transparent")
        test_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=(4, 8), sticky="ew")
        test_frame.grid_columnconfigure(1, weight=1)

        self.test_btn = ctk.CTkButton(test_frame, text="🔍 Verbindung testen", width=140, command=self._test_connection, fg_color="#333333", hover_color="#444444")
        self.test_btn.grid(row=0, column=0, padx=(0, 10), pady=2)

        self.test_status_lbl = ctk.CTkLabel(test_frame, text="", font=ctk.CTkFont(size=11))
        self.test_status_lbl.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        # Prompt Section
        prompt_header_frame = ctk.CTkFrame(self, fg_color="transparent")
        prompt_header_frame.grid(row=3, column=0, padx=20, pady=(10, 2), sticky="ew")
        prompt_header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(prompt_header_frame, text="🤖 System Prompt (KI-Anweisung):", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        reset_prompt_btn = ctk.CTkButton(
            prompt_header_frame, 
            text="Standard wiederherstellen", 
            width=160, 
            height=24, 
            command=self._reset_default_prompt,
            fg_color="#4a5568",
            hover_color="#2d3748"
        )
        reset_prompt_btn.grid(row=0, column=1, sticky="e")

        self.prompt_txt = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=11))
        self.prompt_txt.grid(row=4, column=0, padx=20, pady=(2, 10), sticky="nsew")

        # Bottom Action Buttons Frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=5, column=0, padx=20, pady=(5, 15), sticky="ew")
        btn_frame.grid_columnconfigure(1, weight=1)

        cancel_btn = ctk.CTkButton(btn_frame, text="Abbrechen", width=100, command=self.destroy, fg_color="gray")
        cancel_btn.pack(side="left", padx=5)

        save_btn = ctk.CTkButton(btn_frame, text="Speichern & Übernehmen", width=180, command=self._save, fg_color="#1f538d", hover_color="#143960")
        save_btn.pack(side="right", padx=5)

    def _load_values(self):
        self.api_url_ent.insert(0, getattr(config, 'LLM_API_BASE_URL', "http://127.0.0.1:1234/v1"))
        self.api_key_ent.insert(0, getattr(config, 'LLM_API_KEY', "lm-studio"))
        self.model_ent.insert(0, getattr(config, 'LLM_MODEL_ID', "meta-llama-3-8b-instruct"))
        self.discogs_token_ent.insert(0, getattr(config, 'DISCOGS_API_TOKEN', ""))
        
        current_prompt = getattr(config, 'LLM_SYSTEM_PROMPT', DEFAULT_SYSTEM_PROMPT) or DEFAULT_SYSTEM_PROMPT
        self.prompt_txt.insert("0.0", current_prompt)

    def _reset_default_prompt(self):
        if messagebox.askyesno("Prompt zurücksetzen", "Möchtest du den System-Prompt wirklich auf den Standard zurücksetzen?"):
            self.prompt_txt.delete("0.0", tk.END)
            self.prompt_txt.insert("0.0", DEFAULT_SYSTEM_PROMPT)

    def _test_connection(self):
        self.test_status_lbl.configure(text="⏳ Verbindung wird geprüft...", text_color="orange")
        if hasattr(self.parent, "llm_status_lbl"):
            self.parent.llm_status_lbl.configure(text="🟡 Verbindung wird geprüft...", text_color="orange")
        self.update_idletasks()

        url = self.api_url_ent.get().strip()
        key = self.api_key_ent.get().strip()
        model = self.model_ent.get().strip()

        try:
            client_kwargs = {"base_url": url, "api_key": key}
            client = OpenAI(**client_kwargs)
            # Fetch models list
            models = client.models.list()
            self.test_status_lbl.configure(text="✓ Verbindung erfolgreich! LLM erreichbar.", text_color="#2b712b")
            if hasattr(self.parent, "llm_status_lbl"):
                self.parent.llm_status_lbl.configure(text="🟢 LLM erreichbar (Verbindungstest)", text_color="#2b712b")
        except Exception as e:
            err_str = str(e)
            self.test_status_lbl.configure(text=f"❌ Fehler: {err_str[:60]}...", text_color="#7a2b2b")
            if hasattr(self.parent, "llm_status_lbl"):
                short_err = err_str[:28] + "..." if len(err_str) > 28 else err_str
                self.parent.llm_status_lbl.configure(text=f"🔴 Nicht erreichbar: {short_err}", text_color="#d9534f")

    def _save(self):
        url = self.api_url_ent.get().strip()
        key = self.api_key_ent.get().strip()
        model = self.model_ent.get().strip()
        discogs_token = self.discogs_token_ent.get().strip()
        prompt = self.prompt_txt.get("0.0", tk.END).strip()

        if not prompt:
            prompt = DEFAULT_SYSTEM_PROMPT

        config.LLM_API_BASE_URL = url
        config.LLM_API_KEY = key
        config.LLM_MODEL_ID = model
        config.DISCOGS_API_TOKEN = discogs_token
        config.LLM_SYSTEM_PROMPT = prompt

        self.on_save_callback(url, key, model, prompt)
        self.destroy()
