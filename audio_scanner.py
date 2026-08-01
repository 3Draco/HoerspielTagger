import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from encoding_utils import fix_encoding_corruptions

class AudioScanner:
    """Scans directories and extracts MP3 file structure, metadata context, and checks for cover art."""

    @staticmethod
    def is_mp3(filepath: Path) -> bool:
        """Checks if a file has an MP3 extension."""
        return filepath.suffix.lower() == ".mp3"

    @classmethod
    def scan_directory(cls, target_dir: str) -> List[Dict[str, Any]]:
        """
        Recursively scans the directory and groups files by their parent folder.
        Each group represents an 'album' or 'episode' folder containing MP3 tracks.
        """
        target_path = Path(target_dir).resolve()
        if not target_path.exists() or not target_path.is_dir():
            raise ValueError(f"Target path '{target_dir}' does not exist or is not a directory.")

        groups: Dict[Path, List[Path]] = {}
        for root, _, files in os.walk(target_path):
            root_path = Path(root)
            for file in files:
                file_path = root_path / file
                if cls.is_mp3(file_path):
                    if root_path not in groups:
                        groups[root_path] = []
                    groups[root_path].append(file_path)

        scan_results = []
        for folder, file_paths in groups.items():
            # Sort files alphabetically to keep logical order
            file_paths.sort()
            
            tracks = []
            has_embedded_cover = False
            has_chapters = False

            for path in file_paths:
                track_info = cls.extract_mp3_info(path)
                tracks.append(track_info)
                if track_info["has_cover"]:
                    has_embedded_cover = True
                if track_info["has_chapters"]:
                    has_chapters = True

            scan_results.append({
                "folder_path": str(folder),
                "folder_name": folder.name,
                "relative_folder_path": str(folder.relative_to(target_path)) if folder != target_path else "",
                "tracks": tracks,
                "has_embedded_cover": has_embedded_cover,
                "has_chapters": has_chapters
            })

        return scan_results

    @staticmethod
    def extract_mp3_info(filepath: Path) -> Dict[str, Any]:
        """Extracts existing ID3 tags and cover status from an MP3 file."""
        info = {
            "filepath": str(filepath),
            "filename": filepath.name,
            "title": "",
            "album": "",
            "artist": "",
            "album_artist": "",
            "track_number": None,
            "year": None,
            "genre": "",
            "duration_ms": 0,
            "has_cover": False,
            "has_chapters": False
        }

        try:
            audio = MP3(filepath)
            if hasattr(audio, "info") and audio.info and hasattr(audio.info, "length"):
                info["duration_ms"] = int(audio.info.length * 1000)

            if audio.tags:
                tags = audio.tags
                
                # Check for cover art & chapters
                for key in tags.keys():
                    if key.startswith("APIC"):
                        info["has_cover"] = True
                    elif key.startswith("CHAP"):
                        info["has_chapters"] = True
                
                # Extract common ID3v2 tags
                # TIT2 = Title, TALB = Album, TPE1 = Artist, TPE2 = Album Artist, TRCK = Track, TDRC/TYER = Year, TCON = Genre
                info["title"] = fix_encoding_corruptions(str(tags.get("TIT2", "")))
                info["album"] = fix_encoding_corruptions(str(tags.get("TALB", "")))
                info["artist"] = fix_encoding_corruptions(str(tags.get("TPE1", "")))
                info["album_artist"] = fix_encoding_corruptions(str(tags.get("TPE2", "")))
                
                trck = tags.get("TRCK")
                if trck:
                    # Often track number is represented as '1/12' or just '1'
                    trck_str = str(trck).split("/")[0]
                    try:
                        info["track_number"] = int(trck_str)
                    except ValueError:
                        pass
                
                # Try getting year from TDRC (Date) or TYER (Year)
                year_tag = tags.get("TDRC") or tags.get("TYER")
                if year_tag:
                    try:
                        info["year"] = int(str(year_tag)[:4])
                    except ValueError:
                        pass
                
                tcon = tags.get("TCON")
                if tcon:
                    if hasattr(tcon, "genres") and tcon.genres:
                        info["genre"] = "; ".join([fix_encoding_corruptions(str(g)) for g in tcon.genres if str(g)])
                    elif hasattr(tcon, "text") and isinstance(tcon.text, list):
                        info["genre"] = "; ".join([fix_encoding_corruptions(str(g)) for g in tcon.text if str(g)])
                    else:
                        info["genre"] = fix_encoding_corruptions(str(tcon)).replace('\x00', '; ')

                tcom = tags.get("TCOM")
                if tcom:
                    info["composer"] = fix_encoding_corruptions(str(tcom)).replace('\x00', '; ')

                tpub = tags.get("TPUB")
                if tpub:
                    info["publisher"] = fix_encoding_corruptions(str(tpub)).replace('\x00', '; ')

                comm = tags.get("COMM::deu") or tags.get("COMM")
                if comm:
                    info["comment"] = fix_encoding_corruptions(str(comm)).replace('\x00', ' ')

                tpos = tags.get("TPOS")
                if tpos:
                    info["disc_number"] = fix_encoding_corruptions(str(tpos)).replace('\x00', '')

        except Exception as e:
            # If mutagen fails or file is corrupt, log it or fallback
            pass

        info["filename"] = fix_encoding_corruptions(info["filename"])

        return info
