import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import List

class FileMerger:
    """Merges multiple MP3 files into a single MP3 file using ffmpeg (lossless stream copy with automatic re-encoding fallback)."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Checks if ffmpeg is available in the system PATH."""
        return shutil.which("ffmpeg") is not None

    @classmethod
    def merge_files(cls, file_paths: List[str], output_path: str, reencode: bool = False) -> str:
        """
        Merges the list of files into output_path using ffmpeg concat demuxer.
        If reencode is True, uses libmp3lame re-encoding instead of stream copy.
        Returns ffmpeg stderr output for diagnostic logging.
        """
        if not cls.is_ffmpeg_available():
            raise RuntimeError("ffmpeg executable not found in system PATH. Cannot merge files.")

        if not file_paths:
            raise ValueError("No files provided for merging.")

        # Convert to Path objects
        paths = [Path(p).resolve() for p in file_paths]
        out_path = Path(output_path).resolve()

        # Create temporary file list for ffmpeg concat demuxer
        parent_dir = paths[0].parent
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=parent_dir, delete=False, encoding='utf-8') as f:
            list_file_path = Path(f.name)
            for path in paths:
                # Escape single quotes in filenames for ffmpeg concat demuxer format
                safe_rel_path = path.name.replace("'", "'\\''")
                f.write(f"file '{safe_rel_path}'\n")

        try:
            # Build ffmpeg concat command
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file_path)
            ]

            if reencode:
                cmd.extend(["-c:a", "libmp3lame", "-q:a", "2"])
            else:
                cmd.extend(["-c", "copy"])

            cmd.append(str(out_path))

            # Run in parent directory context
            result = subprocess.run(
                cmd,
                cwd=str(parent_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}. Error: {result.stderr}")

            return result.stderr

        finally:
            # Clean up list file
            if list_file_path.exists():
                list_file_path.unlink()

    @classmethod
    def merge_files_with_fallback(cls, file_paths: List[str], output_path: str) -> str:
        """
        Attempts a fast lossless stream-copy merge first.
        If stream-copy fails or produces a truncated/corrupted output file,
        automatically falls back to re-encoding (-c:a libmp3lame).
        Uses a temporary output file during merging to protect input files and existing target files.
        Returns a human-readable status message indicating which method succeeded.
        """
        out_path = Path(output_path).resolve()
        
        # Prevent output file from being included in the input tracks list (e.g. from a previous merge)
        clean_input_paths = [p for p in file_paths if Path(p).resolve() != out_path]
        if not clean_input_paths:
            raise ValueError("Keine gültigen Quell-Dateien für die Zusammenführung vorhanden.")

        # Use a temporary output file to avoid overwriting inputs mid-process
        temp_out_path = out_path.with_name(f".tmp_merge_{out_path.name}")
        if temp_out_path.exists():
            try:
                temp_out_path.unlink()
            except Exception:
                pass

        err_msg = ""
        try:
            # Attempt 1: Lossless Stream Copy (-c copy)
            cls.merge_files(clean_input_paths, str(temp_out_path), reencode=False)
            cls.verify_merged_file(clean_input_paths, str(temp_out_path))
            
            # Move temporary file to final target
            if out_path.exists():
                out_path.unlink()
            temp_out_path.rename(out_path)
            return "Lossless Stream-Copy (ohne Re-Encoding) erfolgreich."
        except Exception as e:
            err_msg = str(e)
            print(f"[FileMerger Warning] Stream-Copy Merge fehlgeschlagen ({e}). Starte Re-Encode Fallback...")
            if temp_out_path.exists():
                try:
                    temp_out_path.unlink()
                except Exception:
                    pass

        # Attempt 2: Re-Encoding Fallback (-c:a libmp3lame)
        try:
            cls.merge_files(clean_input_paths, str(temp_out_path), reencode=True)
            cls.verify_merged_file(clean_input_paths, str(temp_out_path))
            
            # Move temporary file to final target
            if out_path.exists():
                out_path.unlink()
            temp_out_path.rename(out_path)
            print(f"[FileMerger Success] Re-Encode Fallback erfolgreich abgeschlossen.")
            return f"Re-Encode Fallback erfolgreich (Originaler Stream-Copy schlug fehl: {err_msg})."
        except Exception as fallback_err:
            if temp_out_path.exists():
                try:
                    temp_out_path.unlink()
                except Exception:
                    pass
            raise RuntimeError(
                f"Zusammenführung schlug sowohl per Stream-Copy ({err_msg}) als auch per Re-Encoding ({fallback_err}) fehl."
            )

    @staticmethod
    def verify_merged_file(input_paths: List[str], output_path: str) -> None:
        """
        Verifies that the merged file was created correctly:
        - Checks if output file exists.
        - Checks that output file size is greater than 0.
        - Checks that output audio duration is within a reasonable threshold (+/- 4s) of total input duration.
        """
        from mutagen.mp3 import MP3
        from pathlib import Path

        out_path = Path(output_path).resolve()
        if not out_path.exists():
            raise RuntimeError(f"Zusammengefügte Datei existiert nicht: {output_path}")

        out_size = out_path.stat().st_size
        if out_size == 0:
            raise RuntimeError("Zusammengefügte Datei ist leer (0 Bytes).")

        # Sum up input sizes and durations
        total_input_duration = 0.0
        total_input_size = 0
        for p in input_paths:
            path_obj = Path(p).resolve()
            if path_obj.exists():
                total_input_size += path_obj.stat().st_size
                try:
                    audio = MP3(str(path_obj))
                    if hasattr(audio, "info") and audio.info:
                        total_input_duration += audio.info.length
                except Exception:
                    pass

        # Read output duration
        try:
            out_audio = MP3(str(out_path))
            out_duration = out_audio.info.length if (hasattr(out_audio, "info") and out_audio.info) else 0.0
        except Exception as e:
            raise RuntimeError(f"Zusammengefügte Datei konnte nicht als MP3 gelesen werden: {e}")

        # Check size threshold (at least 80% of inputs size)
        if out_size < total_input_size * 0.80:
            raise RuntimeError(
                f"Die zusammengefügte Datei ist verdächtig klein: "
                f"{out_size / (1024*1024):.2f} MB vs. erwartet {total_input_size / (1024*1024):.2f} MB"
            )

        # Check duration difference with dynamic tolerance (1.5s per track or 2% total duration, min 15s)
        if total_input_duration > 0 and out_duration > 0:
            diff = abs(out_duration - total_input_duration)
            max_allowed_diff = max(15.0, len(input_paths) * 1.5, total_input_duration * 0.02)
            if diff > max_allowed_diff:
                raise RuntimeError(
                    f"Die Dauer der zusammengefügten Datei weicht ab: "
                    f"{out_duration:.2f}s vs. erwartet {total_input_duration:.2f}s (Diff: {diff:.2f}s, max. erlaubt: {max_allowed_diff:.1f}s)"
                )

