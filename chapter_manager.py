import os
import re
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, CHAP, CTOC, TIT2, ID3NoHeaderError

class ChapterManager:
    """
    Manages ID3v2 chapter frames (CHAP and CTOC) for MP3 audio drama files.
    Provides functionality to:
      - Calculate cumulative chapter timing (start_ms, end_ms).
      - Embed CHAP and CTOC frames into merged MP3 files via mutagen.
      - Read embedded CHAP frames from single-file MP3s.
      - Losslessly split a merged MP3 back into individual track files using FFmpeg.
    """

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Checks if ffmpeg is available in system PATH."""
        return shutil.which("ffmpeg") is not None

    @classmethod
    def build_chapter_data(cls, tracks_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculates cumulative start and end timestamps in milliseconds for a list of tracks.
        Each track dict should have: 'filename', 'title' (or 'clean_title'), and 'duration_ms'.
        """
        chapters = []
        current_ms = 0

        for idx, track in enumerate(tracks_info, start=1):
            duration_ms = track.get("duration_ms", 0)

            # Fallback duration measurement if not present
            if duration_ms <= 0 and "filepath" in track and os.path.exists(track["filepath"]):
                try:
                    audio = MP3(track["filepath"])
                    duration_ms = int(audio.info.length * 1000)
                except Exception:
                    duration_ms = 0

            start_ms = current_ms
            end_ms = start_ms + duration_ms
            current_ms = end_ms

            title = track.get("clean_title") or track.get("title") or f"Kapitel {idx}"
            orig_filename = track.get("original_filename") or track.get("filename") or f"track_{idx:02d}.mp3"

            chapters.append({
                "chapter_index": idx,
                "element_id": f"ch{idx}",
                "title": title,
                "original_filename": orig_filename,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms
            })

        return chapters

    @classmethod
    def embed_chapters(cls, mp3_filepath: str, chapter_data: List[Dict[str, Any]]) -> None:
        """
        Embeds ID3v2 CHAP and CTOC frames into an existing MP3 file using mutagen.id3.
        """
        path = Path(mp3_filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {mp3_filepath}")

        try:
            tags = ID3(mp3_filepath)
        except ID3NoHeaderError:
            tags = ID3()

        # Remove any existing CHAP / CTOC frames first
        keys_to_delete = [key for key in tags.keys() if key.startswith("CHAP") or key.startswith("CTOC")]
        for key in keys_to_delete:
            del tags[key]

        child_ids = []

        # Create CHAP frames for each chapter
        for chap in chapter_data:
            elem_id = chap.get("element_id", f"ch{chap['chapter_index']}")
            start_ms = chap["start_ms"]
            end_ms = chap["end_ms"]
            title = chap.get("title", f"Kapitel {chap['chapter_index']}")

            child_ids.append(elem_id)

            chap_frame = CHAP(
                element_id=elem_id,
                start_time=start_ms,
                end_time=end_ms,
                start_offset=0xFFFFFFFF,
                end_offset=0xFFFFFFFF,
                sub_frames=[TIT2(encoding=3, text=title)]
            )
            tags.add(chap_frame)

        # Create CTOC (Table of Contents) frame
        if child_ids:
            ctoc_frame = CTOC(
                element_id="toc",
                flags=3,  # Top-level & ordered
                child_element_ids=child_ids,
                sub_frames=[TIT2(encoding=3, text="Table of Contents")]
            )
            tags.add(ctoc_frame)

        tags.save(mp3_filepath, v2_version=4)

    @classmethod
    def extract_chapters(cls, mp3_filepath: str) -> List[Dict[str, Any]]:
        """
        Reads embedded CHAP frames from an MP3 file and returns structured chapter info.
        """
        path = Path(mp3_filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {mp3_filepath}")

        try:
            tags = ID3(mp3_filepath)
        except ID3NoHeaderError:
            return []

        chapters = []
        chap_keys = [k for k in tags.keys() if k.startswith("CHAP")]
        
        # Sort keys to maintain order
        chap_keys.sort(key=lambda k: int(re.search(r'\d+', k).group()) if re.search(r'\d+', k) else k)

        for idx, key in enumerate(chap_keys, start=1):
            frame = tags[key]
            if isinstance(frame, CHAP):
                title = f"Kapitel {idx}"
                for sub in frame.sub_frames:
                    if isinstance(sub, TIT2):
                        title = str(sub.text[0]) if sub.text else title
                        break

                chapters.append({
                    "chapter_index": idx,
                    "element_id": frame.element_id,
                    "title": title,
                    "start_ms": frame.start_time,
                    "end_ms": frame.end_time,
                    "duration_ms": frame.end_time - frame.start_time
                })

        return chapters

    @classmethod
    def split_by_chapters(cls, mp3_path: str, output_dir: str) -> List[str]:
        """
        Reads CHAP frames from a merged MP3 file and losslessly splits it back
        into individual track files using FFmpeg (-c copy).
        Returns a list of created file paths.
        """
        if not cls.is_ffmpeg_available():
            raise RuntimeError("ffmpeg executable not found in system PATH. Cannot split MP3 by chapters.")

        source_path = Path(mp3_path).resolve()
        out_dir = Path(output_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        chapters = cls.extract_chapters(str(source_path))
        if not chapters:
            raise ValueError(f"No ID3v2 CHAP chapter frames found in file: {mp3_path}")

        created_files = []

        for chap in chapters:
            idx = chap["chapter_index"]
            title = chap["title"]
            start_sec = chap["start_ms"] / 1000.0
            end_sec = chap["end_ms"] / 1000.0

            # Clean filename characters
            clean_title = re.sub(r'[/\\:*?"<>|]', '_', title)
            out_filename = f"{idx:02d} - {clean_title}.mp3"
            out_filepath = out_dir / out_filename

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", f"{start_sec:.3f}",
                "-to", f"{end_sec:.3f}",
                "-i", str(source_path),
                "-c", "copy",
                str(out_filepath)
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg split failed for chapter {idx} ({title}): {result.stderr}")

            # Write basic ID3 title tag to the split chapter file
            try:
                split_tags = ID3()
                split_tags.add(TIT2(encoding=3, text=title))
                split_tags.save(str(out_filepath), v2_version=4)
            except Exception:
                pass

            created_files.append(str(out_filepath))

        return created_files
