import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Optional
from series_db import SeriesDatabase

PRESET_GENRES = [
    "Hörspiel; Horror",
    "Hörspiel; Krimi",
    "Hörspiel; Detektiv",
    "Hörspiel; Science-Fiction",
    "Hörspiel; Fantasy",
    "Hörspiel; Abenteuer",
    "Hörspiel; Jugend",
    "Hörspiel; Kinder",
    "Hörspiel; Comedy",
    "Hörspiel; Thriller",
    "Hörspiel; Klassiker",
    "Hörspiel; Allgemein",
    "Hörspiel"
]

class SeriesDatabaseDialog(ctk.CTkToplevel):
    """GUI window for viewing, filtering, editing, adding, and deleting full series metadata (Name, Aliases, Genre, Composer, Publisher, Comment)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.title("📚 Serien-Datenbank & Gedächtnis verwalten")
        self.geometry("1150x680")
        self.minsize(980, 560)

        # Bring window to front
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
                win_w, win_h = 1150, 680
                x = max(0, parent_x + (parent_w - win_w) // 2)
                y = max(0, parent_y + (parent_h - win_h) // 2)
                self.geometry(f"{win_w}x{win_h}+{x}+{y}")
            except Exception:
                pass

        self._build_ui()
        self.after(200, lambda: self.attributes("-topmost", False))

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1) # Scrollable area expands

        # Header
        header_lbl = ctk.CTkLabel(
            self, 
            text="📚 Serien-Gedächtnis & Stammdaten verwalten", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.grid(row=0, column=0, padx=20, pady=(15, 2), sticky="w")

        desc_lbl = ctk.CTkLabel(
            self,
            text="Verwalte hier dauerhaft Seriennamen, Kürzel, Genre sowie fest vorgeschlagene Komponisten/Autoren, Labels/Verlage und Kommentar-Texte.",
            wraplength=1100,
            text_color="gray",
            justify="left"
        )
        desc_lbl.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        # Top Bar: Add New Series Frame & Search Bar
        top_frame = ctk.CTkFrame(self)
        top_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        top_frame.grid_columnconfigure(1, weight=1)

        # Row 0 of top_frame: Add New Series inputs
        ctk.CTkLabel(top_frame, text="Neue Serie:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=8, pady=6, sticky="w")
        
        add_inputs_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        add_inputs_frame.grid(row=0, column=1, padx=4, pady=6, sticky="ew")
        add_inputs_frame.grid_columnconfigure(0, weight=3) # Name
        add_inputs_frame.grid_columnconfigure(1, weight=1) # Kürzel
        add_inputs_frame.grid_columnconfigure(2, weight=2) # Genre
        add_inputs_frame.grid_columnconfigure(3, weight=2) # Komponist
        add_inputs_frame.grid_columnconfigure(4, weight=2) # Publisher
        add_inputs_frame.grid_columnconfigure(5, weight=3) # Comment

        self.new_series_ent = ctk.CTkEntry(add_inputs_frame, placeholder_text="Serienname (z. B. Larry Brent)")
        self.new_series_ent.grid(row=0, column=0, padx=2, sticky="ew")

        self.new_alias_ent = ctk.CTkEntry(add_inputs_frame, placeholder_text="Kürzel (LB)")
        self.new_alias_ent.grid(row=0, column=1, padx=2, sticky="ew")

        self.new_genre_combo = ctk.CTkComboBox(add_inputs_frame, values=PRESET_GENRES)
        self.new_genre_combo.set("Hörspiel; Horror")
        self.new_genre_combo.grid(row=0, column=2, padx=2, sticky="ew")

        self.new_composer_ent = ctk.CTkEntry(add_inputs_frame, placeholder_text="Komponist / Autor")
        self.new_composer_ent.grid(row=0, column=3, padx=2, sticky="ew")

        self.new_publisher_ent = ctk.CTkEntry(add_inputs_frame, placeholder_text="Label (z. B. EUROPA)")
        self.new_publisher_ent.grid(row=0, column=4, padx=2, sticky="ew")

        self.new_comment_ent = ctk.CTkEntry(add_inputs_frame, placeholder_text="Kommentar-Vorlage")
        self.new_comment_ent.grid(row=0, column=5, padx=2, sticky="ew")

        add_btn = ctk.CTkButton(top_frame, text="➕ Hinzufügen", width=110, command=self._add_series, fg_color="#2b712b", hover_color="#1e4e1e")
        add_btn.grid(row=0, column=2, padx=8, pady=6)

        # Row 1 of top_frame: Search Filter
        ctk.CTkLabel(top_frame, text="🔍 Suchen:").grid(row=1, column=0, padx=8, pady=(2, 6), sticky="w")
        self.search_ent = ctk.CTkEntry(top_frame, placeholder_text="Filtern nach Serienname, Kürzel, Genre, Komponist oder Label...")
        self.search_ent.grid(row=1, column=1, columnspan=2, padx=8, pady=(2, 6), sticky="ew")
        self.search_ent.bind("<KeyRelease>", lambda e: self._refresh_list())

        # Scrollable Container for Series Entries
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Bottom Close Button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=20, pady=(5, 15), sticky="ew")
        
        close_btn = ctk.CTkButton(btn_frame, text="Schließen", width=120, command=self.destroy, fg_color="gray")
        close_btn.pack(side="right")

        self._refresh_list()

    def _refresh_list(self):
        # Clear existing rows
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        all_series = SeriesDatabase.get_all_series_full()
        query = self.search_ent.get().strip().lower()

        # Table Headers
        header_row = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        header_row.grid(row=0, column=0, padx=5, pady=(0, 4), sticky="ew")
        header_row.grid_columnconfigure(0, weight=3) # Name
        header_row.grid_columnconfigure(1, weight=1) # Alias
        header_row.grid_columnconfigure(2, weight=2) # Genre
        header_row.grid_columnconfigure(3, weight=2) # Composer
        header_row.grid_columnconfigure(4, weight=2) # Publisher
        header_row.grid_columnconfigure(5, weight=3) # Comment

        ctk.CTkLabel(header_row, text="Serienname", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=4, sticky="w")
        ctk.CTkLabel(header_row, text="Kürzel", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(header_row, text="Genre", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=2, padx=4, sticky="w")
        ctk.CTkLabel(header_row, text="Komponist / Autor", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=3, padx=4, sticky="w")
        ctk.CTkLabel(header_row, text="Label / Verlag", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=4, padx=4, sticky="w")
        ctk.CTkLabel(header_row, text="Kommentar-Vorlage", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=5, padx=4, sticky="w")

        row_idx = 1
        for item in all_series:
            name = item["display_name"]
            genre = item["genre"]
            aliases_str = item["aliases_str"]
            composer = item.get("composer", "")
            publisher = item.get("publisher", "")
            comment = item.get("comment", "")

            search_target = f"{name} {genre} {aliases_str} {composer} {publisher} {comment}".lower()
            if query and query not in search_target:
                continue

            item_frame = ctk.CTkFrame(self.scroll_frame, fg_color=("#f1f5f9", "#1e293b"))
            item_frame.grid(row=row_idx, column=0, padx=5, pady=4, sticky="ew")
            item_frame.grid_columnconfigure(0, weight=3)
            item_frame.grid_columnconfigure(1, weight=1)
            item_frame.grid_columnconfigure(2, weight=2)
            item_frame.grid_columnconfigure(3, weight=2)
            item_frame.grid_columnconfigure(4, weight=2)
            item_frame.grid_columnconfigure(5, weight=3)

            # Name entry
            name_ent = ctk.CTkEntry(item_frame, font=ctk.CTkFont(weight="bold"))
            name_ent.insert(0, name)
            name_ent.grid(row=0, column=0, padx=3, pady=6, sticky="ew")

            # Alias entry
            alias_ent = ctk.CTkEntry(item_frame, placeholder_text="z. B. LB")
            alias_ent.insert(0, aliases_str)
            alias_ent.grid(row=0, column=1, padx=3, pady=6, sticky="ew")

            # Genre combo
            genre_combo = ctk.CTkComboBox(item_frame, values=PRESET_GENRES)
            genre_combo.set(genre)
            genre_combo.grid(row=0, column=2, padx=3, pady=6, sticky="ew")

            # Composer entry
            composer_ent = ctk.CTkEntry(item_frame, placeholder_text="Komponist / Autor")
            composer_ent.insert(0, composer)
            composer_ent.grid(row=0, column=3, padx=3, pady=6, sticky="ew")

            # Publisher entry
            publisher_ent = ctk.CTkEntry(item_frame, placeholder_text="Label")
            publisher_ent.insert(0, publisher)
            publisher_ent.grid(row=0, column=4, padx=3, pady=6, sticky="ew")

            # Comment entry
            comment_ent = ctk.CTkEntry(item_frame, placeholder_text="Kommentar")
            comment_ent.insert(0, comment)
            comment_ent.grid(row=0, column=5, padx=3, pady=6, sticky="ew")

            # Save & Delete buttons
            def make_save_cmd(orig_n=name, n_ent=name_ent, a_ent=alias_ent, g_combo=genre_combo, c_ent=composer_ent, p_ent=publisher_ent, cm_ent=comment_ent):
                return lambda: self._save_item(
                    orig_n, 
                    n_ent.get().strip(), 
                    a_ent.get().strip(), 
                    g_combo.get().strip(),
                    c_ent.get().strip(),
                    p_ent.get().strip(),
                    cm_ent.get().strip()
                )

            def make_del_cmd(orig_n=name):
                return lambda: self._delete_item(orig_n)

            save_btn = ctk.CTkButton(item_frame, text="💾", width=36, command=make_save_cmd(name, name_ent, alias_ent, genre_combo, composer_ent, publisher_ent, comment_ent), fg_color="#1f538d")
            save_btn.grid(row=0, column=6, padx=(4, 2), pady=6)

            del_btn = ctk.CTkButton(item_frame, text="🗑️", width=36, command=make_del_cmd(name), fg_color="#7a2b2b", hover_color="#5a1b1b")
            del_btn.grid(row=0, column=7, padx=(2, 6), pady=6)

            row_idx += 1

        if row_idx == 1:
            no_data_lbl = ctk.CTkLabel(self.scroll_frame, text="Keine passenden Serien-Einträge gefunden.", text_color="gray")
            no_data_lbl.grid(row=1, column=0, pady=20)

    def _add_series(self):
        name = self.new_series_ent.get().strip()
        alias_raw = self.new_alias_ent.get().strip()
        genre = self.new_genre_combo.get().strip()
        composer = self.new_composer_ent.get().strip()
        publisher = self.new_publisher_ent.get().strip()
        comment = self.new_comment_ent.get().strip()

        if not name or not genre:
            messagebox.showwarning("Unvollständig", "Bitte gib einen Seriennamen und ein Genre ein.")
            return

        SeriesDatabase.set_series_genre(name, genre, aliases=alias_raw, composer=composer, publisher=publisher, comment=comment)
        self.new_series_ent.delete(0, tk.END)
        self.new_alias_ent.delete(0, tk.END)
        self.new_composer_ent.delete(0, tk.END)
        self.new_publisher_ent.delete(0, tk.END)
        self.new_comment_ent.delete(0, tk.END)
        self._refresh_list()

    def _save_item(self, orig_name: str, new_name: str, new_alias_raw: str, new_genre: str, new_composer: str, new_publisher: str, new_comment: str):
        if not new_name or not new_genre:
            messagebox.showwarning("Ungültig", "Serienname und Genre dürfen nicht leer sein.")
            return

        # If name changed, delete old key
        if orig_name.lower() != new_name.lower():
            SeriesDatabase.delete_series(orig_name)

        SeriesDatabase.set_series_genre(
            new_name, 
            new_genre, 
            aliases=new_alias_raw, 
            composer=new_composer, 
            publisher=new_publisher, 
            comment=new_comment
        )
        self._refresh_list()

    def _delete_item(self, series_name: str):
        if messagebox.askyesno("Löschen bestätigen", f"Möchtest du '{series_name}' wirklich aus der Serien-Datenbank löschen?"):
            SeriesDatabase.delete_series(series_name)
            self._refresh_list()
