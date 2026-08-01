import os
import threading
import tkinter as tk
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import customtkinter as ctk
from tag_writer import TagWriter

class BatchEditTab(ctk.CTkFrame):
    """
    Modular tab for batch-editing metadata tags across multiple audio drama albums/files.
    Mp3tag-style: inspects selected files, pre-fills matching values, provides dropdowns
    for differing values, and selectively overwrites only active fields.
    """

    KEEP_VALUE = "< beibehalten >"

    def __init__(self, parent: Any, get_scan_results_cb: Callable[[], List[Dict[str, Any]]], on_status_update_cb: Optional[Callable[[str, str], None]] = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.get_scan_results_cb = get_scan_results_cb
        self.on_status_update_cb = on_status_update_cb

        # Data state
        self.album_checkbox_vars: List[tuple[Dict[str, Any], ctk.BooleanVar]] = []

        self._build_ui()

    def _build_ui(self):
        # Configure layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header Title
        header_lbl = ctk.CTkLabel(
            self,
            text="⚡ Massenbearbeitung (Batch Tag Edit)",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header_lbl.grid(row=0, column=0, columnspan=2, padx=15, pady=(15, 5), sticky="w")

        sub_lbl = ctk.CTkLabel(
            self,
            text="Wähle Dateien aus. Gleiche Tags werden angezeigt; bei verschiedenen Tags bietet das Dropdown alle vorhandenen Werte an. Nur geänderte/aktivierte Tags werden überschrieben.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        sub_lbl.grid(row=0, column=0, columnspan=2, padx=15, pady=(0, 10), sticky="w")

        # LEFT FRAME: File Selection List
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=1, column=0, padx=(15, 7), pady=10, sticky="nsew")
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        file_list_title = ctk.CTkLabel(left_frame, text="📁 Ausgewählte Hörspiele / Dateien", font=ctk.CTkFont(size=14, weight="bold"))
        file_list_title.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.select_all_var = ctk.BooleanVar(value=True)
        self.select_all_cb = ctk.CTkCheckBox(
            left_frame,
            text="Alle auswählen / abwählen",
            variable=self.select_all_var,
            command=self._toggle_select_all,
            font=ctk.CTkFont(weight="bold")
        )
        self.select_all_cb.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="e")

        # Scrollable container for file checkboxes
        self.files_scroll_frame = ctk.CTkScrollableFrame(left_frame)
        self.files_scroll_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # RIGHT FRAME: Tag Overwrite Fields
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=1, column=1, padx=(7, 15), pady=10, sticky="nsew")
        right_frame.grid_columnconfigure(1, weight=1)

        fields_title = ctk.CTkLabel(right_frame, text="✏️ Metadaten bearbeiten (Mp3tag-Stil)", font=ctk.CTkFont(size=14, weight="bold"))
        fields_title.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 15), sticky="w")

        # Field Controls (Checkbox + CTkComboBox for high contrast & dropdown list)
        self.field_vars: Dict[str, ctk.BooleanVar] = {}
        self.field_combos: Dict[str, ctk.CTkComboBox] = {}

        fields_def = [
            ("album_artist", "Album-Interpret / Serie"),
            ("artist", "Track-Interpret"),
            ("composer", "Komponist"),
            ("genre", "Genre (z. B. Hörspiel; Comedy)"),
            ("year", "Erscheinungsjahr"),
            ("disc_number", "Disc-Nummer (z. B. 1)"),
            ("comment", "Kommentar")
        ]

        row_idx = 1
        for key, label_text in fields_def:
            chk_var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                right_frame,
                text=label_text,
                variable=chk_var,
                font=ctk.CTkFont(weight="bold")
            )
            chk.grid(row=row_idx, column=0, padx=10, pady=8, sticky="w")
            self.field_vars[key] = chk_var

            combo = ctk.CTkComboBox(
                right_frame,
                values=[self.KEEP_VALUE],
                font=ctk.CTkFont(size=12),
                dropdown_font=ctk.CTkFont(size=12),
                command=lambda val, k=key: self._on_combo_changed(k, val)
            )
            combo.set(self.KEEP_VALUE)
            combo.grid(row=row_idx, column=1, padx=10, pady=8, sticky="ew")
            combo.bind("<KeyRelease>", lambda e, k=key: self._on_combo_typed(k))
            self.field_combos[key] = combo

            row_idx += 1

        # Action Buttons Section
        btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        btn_frame.grid(row=row_idx, column=0, columnspan=2, padx=10, pady=(25, 10), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=1)

        self.apply_batch_btn = ctk.CTkButton(
            btn_frame,
            text="💾 Ausgewählte Tags auf selektierte Dateien anwenden",
            font=ctk.CTkFont(weight="bold", size=13),
            fg_color="#1f538d",
            hover_color="#14375e",
            height=40,
            command=self._start_batch_apply
        )
        self.apply_batch_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

    def refresh_file_list(self):
        """Rebuilds the list of scrollable album/file checkboxes based on scanned results."""
        for widget in self.files_scroll_frame.winfo_children():
            widget.destroy()

        self.album_checkbox_vars.clear()
        scan_results = self.get_scan_results_cb()

        if not scan_results:
            empty_lbl = ctk.CTkLabel(self.files_scroll_frame, text="Keine Hörspiele / Alben im Scanner geladen.", text_color="gray")
            empty_lbl.pack(padx=10, pady=20)
            self._update_field_values_from_selection()
            return

        for idx, album in enumerate(scan_results):
            folder_name = album.get("folder_name") or Path(album.get("folder_path", "")).name
            album_title = album.get("album") or folder_name
            num_tracks = len(album.get("tracks", []))

            display_text = f"[{idx+1:02d}] {album_title} ({num_tracks} Track{'s' if num_tracks != 1 else ''})"

            var = ctk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(
                self.files_scroll_frame,
                text=display_text,
                variable=var,
                command=self._on_file_selection_changed
            )
            cb.pack(anchor="w", padx=5, pady=4)
            self.album_checkbox_vars.append((album, var))

        self._update_field_values_from_selection()

    def _toggle_select_all(self):
        val = self.select_all_var.get()
        for _, var in self.album_checkbox_vars:
            var.set(val)
        self._update_field_values_from_selection()

    def _on_file_selection_changed(self):
        self._update_field_values_from_selection()

    def _on_combo_changed(self, key: str, val: str):
        if val != self.KEEP_VALUE:
            self.field_vars[key].set(True)
        else:
            self.field_vars[key].set(False)

    def _on_combo_typed(self, key: str):
        val = self.field_combos[key].get().strip()
        if val and val != self.KEEP_VALUE:
            self.field_vars[key].set(True)
        else:
            self.field_vars[key].set(False)

    def _update_field_values_from_selection(self):
        """
        Inspects all currently selected files.
        If all selected files have the same value for a field, populates the combobox with it.
        If values differ, sets combobox to '< beibehalten >' and populates the dropdown list with all unique values!
        """
        selected_albums = [album for album, var in self.album_checkbox_vars if var.get()]

        field_values: Dict[str, List[str]] = {
            "album_artist": [],
            "artist": [],
            "composer": [],
            "genre": [],
            "year": [],
            "disc_number": [],
            "comment": []
        }

        for album in selected_albums:
            tracks = album.get("tracks", [])
            album_artist = album.get("album_artist") or (tracks[0].get("album_artist") if tracks else "") or ""
            if album_artist:
                field_values["album_artist"].append(album_artist)

            for t in tracks:
                if t.get("artist"):
                    field_values["artist"].append(t["artist"])
                if t.get("composer"):
                    field_values["composer"].append(t["composer"])
                if t.get("genre"):
                    g_val = t["genre"] if isinstance(t["genre"], str) else "; ".join(t["genre"])
                    field_values["genre"].append(g_val)
                if t.get("year"):
                    field_values["year"].append(str(t["year"]))
                if t.get("disc_number"):
                    field_values["disc_number"].append(str(t["disc_number"]))
                if t.get("comment"):
                    field_values["comment"].append(t["comment"])

        for key, combo in self.field_combos.items():
            vals = field_values[key]
            unique_vals = list(dict.fromkeys([v for v in vals if v]))

            if not unique_vals:
                combo.configure(values=[self.KEEP_VALUE])
                combo.set(self.KEEP_VALUE)
                self.field_vars[key].set(False)
            elif len(unique_vals) == 1:
                single_val = unique_vals[0]
                combo.configure(values=[single_val, self.KEEP_VALUE])
                combo.set(single_val)
                # Uncheck checkbox by default so user must check or modify to overwrite
                self.field_vars[key].set(False)
            else:
                dropdown_options = [self.KEEP_VALUE] + unique_vals
                combo.configure(values=dropdown_options)
                combo.set(self.KEEP_VALUE)
                self.field_vars[key].set(False)

    def _start_batch_apply(self):
        selected_albums = [album for album, var in self.album_checkbox_vars if var.get()]
        if not selected_albums:
            tk.messagebox.showwarning("Keine Auswahl", "Bitte wähle mindestens ein Hörspiel/Album in der linken Liste aus.")
            return

        active_fields = {}
        for k, var in self.field_vars.items():
            val = self.field_combos[k].get().strip()
            if var.get() or (val and val != self.KEEP_VALUE):
                active_fields[k] = val if val != self.KEEP_VALUE else ""

        if not active_fields:
            tk.messagebox.showwarning("Kein Feld aktiviert", "Bitte aktiviere mindestens ein Häkchen oder wähle/tippe einen Wert in den Feldern rechts.")
            return

        confirm_msg = f"Möchtest du die aktivierten Tags ({', '.join(active_fields.keys())}) wirklich auf {len(selected_albums)} Hörspiele anwenden?"
        if not tk.messagebox.askyesno("Massenbearbeitung Bestätigung", confirm_msg):
            return

        self.apply_batch_btn.configure(state="disabled", text="Bearbeite Dateien...")

        def run():
            success_count = 0
            for album in selected_albums:
                tracks = album.get("tracks", [])
                for t in tracks:
                    filepath = t["filepath"]
                    if not Path(filepath).exists():
                        continue
                    try:
                        # Read existing tags first to preserve untouched tags
                        from mutagen.id3 import ID3
                        try:
                            existing_id3 = ID3(filepath)
                        except Exception:
                            existing_id3 = None

                        orig_title = t.get("title") or Path(filepath).stem
                        orig_album = album.get("album") or album.get("folder_name", "")
                        orig_artist = album.get("album_artist", "Hörspiel")
                        orig_album_artist = album.get("album_artist", "Hörspiel")
                        orig_trck = t.get("track_number", 1)

                        # Existing fallbacks from ID3 frame if present
                        orig_year = None
                        orig_genre = "Hörspiel"
                        orig_composer = None
                        orig_comment = None
                        orig_disc = None

                        if existing_id3:
                            if "TDRC" in existing_id3:
                                try:
                                    orig_year = int(str(existing_id3["TDRC"]))
                                except Exception:
                                    pass
                            if "TCON" in existing_id3:
                                orig_genre = list(existing_id3["TCON"].text) if hasattr(existing_id3["TCON"], 'text') else str(existing_id3["TCON"])
                            if "TCOM" in existing_id3:
                                orig_composer = str(existing_id3["TCOM"])
                            if "COMM" in existing_id3 or "COMM::deu" in existing_id3:
                                comm_obj = existing_id3.get("COMM::deu") or existing_id3.get("COMM")
                                orig_comment = str(comm_obj) if comm_obj else None
                            if "TPOS" in existing_id3:
                                orig_disc = str(existing_id3["TPOS"])

                        # Merge overloads for activated fields
                        new_album_artist = active_fields["album_artist"] if "album_artist" in active_fields else orig_album_artist
                        new_artist = active_fields["artist"] if "artist" in active_fields else orig_artist
                        new_composer = active_fields["composer"] if "composer" in active_fields else orig_composer
                        new_comment = active_fields["comment"] if "comment" in active_fields else orig_comment
                        new_disc = active_fields["disc_number"] if "disc_number" in active_fields else orig_disc

                        if "year" in active_fields:
                            raw_year = active_fields["year"]
                            new_year = int(raw_year) if (raw_year and raw_year.isdigit()) else None
                        else:
                            new_year = orig_year

                        if "genre" in active_fields:
                            raw_genre = active_fields["genre"]
                            new_genre = [g.strip() for g in raw_genre.replace(';', ',').split(',') if g.strip()] if raw_genre else ["Hörspiel"]
                        else:
                            new_genre = orig_genre

                        # Write updated tags cleanly
                        TagWriter.write_tags(
                            filepath=filepath,
                            title=orig_title,
                            album=orig_album,
                            artist=new_artist,
                            album_artist=new_album_artist,
                            track_number=orig_trck,
                            genre=new_genre,
                            year=new_year,
                            composer=new_composer,
                            comment=new_comment,
                            disc_number=new_disc
                        )
                        success_count += 1
                    except Exception as err:
                        print(f"[BatchEdit Error] {filepath}: {err}")

            def on_done():
                self.apply_batch_btn.configure(state="normal", text="💾 Ausgewählte Tags auf selektierte Dateien anwenden")
                tk.messagebox.showinfo("Massenbearbeitung Abgeschlossen", f"Erfolgreich {success_count} Dateien aktualisiert.")
                if self.on_status_update_cb:
                    self.on_status_update_cb("Massenbearbeitung abgeschlossen", "#2b712b")

            self.after(0, on_done)

        threading.Thread(target=run, daemon=True).start()
