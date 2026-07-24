import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
from audio_scanner import AudioScanner
from llm_client import LLMClient
from cover_downloader import CoverDownloader
from tag_writer import TagWriter
from file_merger import FileMerger
import config

from chapter_manager import ChapterManager

def run_split(mp3_path: str, output_dir: Optional[str] = None):
    """Losslessly splits a merged MP3 file into tracks using embedded ID3v2 CHAP frames."""
    source_file = Path(mp3_path).resolve()
    if not source_file.exists():
        print(f"❌ Datei nicht gefunden: {mp3_path}")
        sys.exit(1)

    out_directory = Path(output_dir).resolve() if output_dir else source_file.parent / f"{source_file.stem}_Kapitel"
    
    print("==================================================")
    print("✂ HoerspielTag - Lossless Chapter Splitter")
    print(f"Datei: {source_file.name}")
    print(f"Ziel:  {out_directory}")
    print("==================================================")

    try:
        created = ChapterManager.split_by_chapters(str(source_file), str(out_directory))
        print(f"\n✓ Erfolgreich {len(created)} Kapitel ausgelesen und verlustfrei geschnitten:")
        for f in created:
            print(f"  * {Path(f).name}")
    except Exception as e:
        print(f"❌ Fehler beim Teilen der Kapitel: {e}")
        sys.exit(1)

def run_cli(target_dir: str, dry_run: bool, merge: bool):
    """Executes the metadata tagging pipeline via the Command Line Interface."""
    print("==================================================")
    print("📻 HoerspielTag - AI-Powered Audio Drama Tagger")
    print(f"Modus: {'[DRY-RUN (Simulationslauf)]' if dry_run else '[LIVE (Schreibmodus)]'}")
    print("==================================================")

    try:
        albums = AudioScanner.scan_directory(target_dir)
    except Exception as e:
        print(f"❌ Fehler beim Einlesen des Verzeichnisses: {e}")
        sys.exit(1)

    if not albums:
        print("Keine MP3-Dateien in der Ordnerstruktur gefunden.")
        return

    print(f"{len(albums)} Audio-Drama-Ordner gefunden.\n")
    llm_client = LLMClient()

    for idx, album in enumerate(albums):
        print(f"--- [{idx+1}/{len(albums)}] Analysiere Ordner: {album['folder_name']} ---")
        try:
            # 1. LLM metadata query
            metadata = llm_client.analyze_album(album["folder_name"], album["tracks"])
            series_name = metadata.series_name or metadata.album_artist or metadata.series
            episode_num = metadata.series_part or metadata.episode_number or 1
            episode_title = metadata.episode_title or (metadata.album.split(" - ", 1)[-1] if " - " in metadata.album else metadata.album)
            
            # Format zero-padded album name: "04 - Episode Title"
            formatted_album = f"{episode_num:02d} - {episode_title}"

            print(f"📝 Erkannte Serie (albumartist): {series_name}")
            print(f"📝 Episoden-Nummer:             {episode_num}")
            print(f"📝 Album / Folge (album):        {formatted_album}")
            print(f"📝 Reiner Folgentitel (title):   {episode_title}")
            print(f"📝 Jahr:                        {metadata.year}")
            print(f"📝 Genre:                       {metadata.genre}")

            # 2. Cover art query
            cover_bytes = None
            if not album["has_embedded_cover"]:
                cover_url = CoverDownloader.search_cover_url(series_name, formatted_album, episode_title)
                if cover_url:
                    print(f"🎨 Cover gefunden auf iTunes: {cover_url}")
                    cover_bytes = CoverDownloader.download_image(cover_url)
                else:
                    print("🎨 iTunes Cover-Suche erfolglos.")
            else:
                print("🎨 Bereits eingebettetes Cover vorhanden.")

            # 3. Print track mapping
            print("\nTrack-Mapping:")
            changes = []
            for track in album["tracks"]:
                prop = next((t for t in metadata.tracks if t.original_filename == track["filename"]), None)
                clean_title = prop.clean_title if prop else track["title"] or Path(track["filename"]).stem
                track_num = prop.track_number if prop else 1
                new_filename = f"{track_num:02d} - {clean_title}.mp3"
                
                print(f"  * {track['filename']}  ==>  {new_filename} (Track: {track_num}, Titel: {clean_title})")
                
                changes.append({
                    "orig_filepath": track["filepath"],
                    "filename": track["filename"],
                    "new_filename": new_filename,
                    "track_number": track_num,
                    "clean_title": clean_title,
                    "duration_ms": track.get("duration_ms", 0)
                })

            if dry_run:
                print("\n[Dry-Run] Keine Änderungen vorgenommen.")
                continue

            # 4. Apply Changes
            folder_path = Path(album["folder_path"])
            
            # Save cover
            if cover_bytes:
                with open(folder_path / "cover.jpg", "wb") as f:
                    f.write(cover_bytes)

            new_file_paths = []
            # Sort changes by track_number
            changes.sort(key=lambda x: x["track_number"])

            for change in changes:
                orig_path = Path(change["orig_filepath"])
                
                # Tag file according to Plex rules
                TagWriter.write_tags(
                    filepath=str(orig_path),
                    title=change["clean_title"],
                    album=formatted_album,
                    artist=series_name,
                    album_artist=series_name,
                    track_number=change["track_number"],
                    genre=metadata.genre or "Hörspiel",
                    year=metadata.year,
                    cover_bytes=cover_bytes
                )

                # Rename file
                target_path = orig_path.parent / change["new_filename"]
                if orig_path != target_path:
                    counter = 1
                    test_path = target_path
                    while test_path.exists() and test_path != orig_path:
                        test_path = orig_path.parent / f"{target_path.stem} ({counter}){target_path.suffix}"
                        counter += 1
                    target_path = test_path
                    os.rename(orig_path, target_path)

                new_file_paths.append(str(target_path))

            print("✓ Tags geschrieben und Einzel-Dateien umbenannt.")

            # 5. Lossless Merge with ID3v2 Chapters (CHAP/CTOC)
            if merge and len(new_file_paths) >= 2:
                merged_filename = f"{formatted_album}.mp3"
                for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    merged_filename = merged_filename.replace(char, "_")
                merged_out = folder_path / merged_filename
                
                print(f"🔗 Führe {len(new_file_paths)} Tracks verlustfrei zusammen & bette ID3v2-Kapitel (CHAP) ein...")
                try:
                    # Build chapter timing data
                    chapter_data = ChapterManager.build_chapter_data(changes)

                    # Lossless merge
                    FileMerger.merge_files(new_file_paths, str(merged_out))
                    
                    # Verify integrity
                    FileMerger.verify_merged_file(new_file_paths, str(merged_out))
                    
                    # Tag merged file: TIT2 = PURE episode_title ONLY! TRCK = episode_num!
                    TagWriter.write_tags(
                        filepath=str(merged_out),
                        title=episode_title,
                        album=formatted_album,
                        artist=series_name,
                        album_artist=series_name,
                        track_number=episode_num,
                        genre=metadata.genre or "Hörspiel",
                        year=metadata.year,
                        cover_bytes=cover_bytes,
                        chapters=chapter_data
                    )
                    print(f"✓ Verlustfreie Zusammenführung & ID3v2 Kapitel-Einbettung abgeschlossen: {merged_out.name}")
                except Exception as merge_err:
                    print(f"⚠️ Merge fehlgeschlagen: {merge_err}")

            # Folder renaming
            cleaned_folder_name = f"{series_name} - {formatted_album}" if series_name.lower() not in formatted_album.lower() else formatted_album
            for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                cleaned_folder_name = cleaned_folder_name.replace(char, "_")
            
            new_folder_path = folder_path.parent / cleaned_folder_name
            if folder_path != new_folder_path and not new_folder_path.exists():
                try:
                    os.rename(folder_path, new_folder_path)
                    print(f"✓ Ordner umbenannt: {cleaned_folder_name}")
                except Exception:
                    print("⚠️ Ordnerumbenennung blockiert.")

        except Exception as e:
            print(f"❌ Fehler bei der Verarbeitung des Ordners {album['folder_name']}: {e}")
        
        print("-" * 50)

def main():
    parser = argparse.ArgumentParser(description="AI-gestütztes Tool zum automatischen Bereinigen, Taggen, Mergen mit ID3-Kapiteln und Splitter von Hörspielen.")
    parser.add_argument("directory", nargs="?", help="Zielverzeichnis mit den Hörspielen (wenn leer, wird die GUI gestartet)")
    parser.add_argument("--dry-run", action="store_true", help="Simuliert die Operationen (keine Schreibzugriffe)")
    parser.add_argument("--merge", action="store_true", help="Fügt MP3s eines Ordners verlustfrei zusammen und bettet ID3-Kapitel ein")
    parser.add_argument("--split", type=str, metavar="MP3_PATH", help="Teilt eine zusammengefügte MP3-Datei anhand ihrer eingebetteten ID3-Kapitel (CHAP) wieder in Einzeldateien auf")
    parser.add_argument("--cli", action="store_true", help="Erzwingt den CLI-Modus")

    args = parser.parse_args()

    # If --split parameter is provided, run chapter splitter
    if args.split:
        run_split(args.split)
        return

    # If directory is provided or --cli is set, run CLI mode. Otherwise, launch GUI.
    if args.directory or args.cli:
        if not args.directory:
            print("Fehler: CLI-Modus erfordert ein Zielverzeichnis.")
            parser.print_help()
            sys.exit(1)
        run_cli(args.directory, args.dry_run, args.merge)
    else:
        # Launch CustomTkinter GUI
        try:
            from gui import HoerspielTaggerGUI
            app = HoerspielTaggerGUI()
            app.mainloop()
        except ImportError as e:
            print(f"Konnte GUI-Abhängigkeiten nicht laden: {e}")
            print("Führe die Installation mit 'pip install -r requirements.txt' aus oder starte im CLI-Modus.")

    # If directory is provided or --cli is set, run CLI mode. Otherwise, launch GUI.
    if args.directory or args.cli:
        if not args.directory:
            print("Fehler: CLI-Modus erfordert ein Zielverzeichnis.")
            parser.print_help()
            sys.exit(1)
        run_cli(args.directory, args.dry_run, args.merge)
    else:
        # Launch CustomTkinter GUI
        try:
            from gui import HoerspielTaggerGUI
            app = HoerspielTaggerGUI()
            app.mainloop()
        except ImportError as e:
            print(f"Konnte GUI-Abhängigkeiten nicht laden: {e}")
            print("Führe die Installation mit 'pip install -r requirements.txt' aus oder starte im CLI-Modus.")

if __name__ == "__main__":
    main()
