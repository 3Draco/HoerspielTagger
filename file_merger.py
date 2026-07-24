import subprocess
import shutil
import tempfile
from pathlib import Path
from typing import List

class FileMerger:
    """Merges multiple MP3 files into a single MP3 file losslessly using ffmpeg."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Checks if ffmpeg is available in the system PATH."""
        return shutil.which("ffmpeg") is not None

    @classmethod
    def merge_files(cls, file_paths: List[str], output_path: str) -> None:
        """
        Merges the list of files into output_path using ffmpeg concat demuxer.
        Assumes all file paths exist.
        """
        if not cls.is_ffmpeg_available():
            raise RuntimeError("ffmpeg executable not found in system PATH. Cannot merge files.")

        if not file_paths:
            raise ValueError("No files provided for merging.")

        # Convert to Path objects
        paths = [Path(p).resolve() for p in file_paths]
        out_path = Path(output_path).resolve()

        # We will create a temporary file list for the ffmpeg concat demuxer
        # Using a temporary file inside the same parent directory to avoid cross-drive/path issues
        parent_dir = paths[0].parent
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=parent_dir, delete=False, encoding='utf-8') as f:
            list_file_path = Path(f.name)
            for path in paths:
                # Use relative paths or safe escaping for ffmpeg
                # Using forward slashes is safer for ffmpeg on Windows
                relative_path = path.name
                f.write(f"file '{relative_path}'\n")

        try:
            # Run ffmpeg concat command
            # -safe 0 allows absolute/relative paths in the file list
            # -c copy does lossless stream copying without re-encoding
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file_path),
                "-c", "copy",
                str(out_path)
            ]

            # Run in the parent directory context
            result = subprocess.run(
                cmd,
                cwd=str(parent_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed with exit code {result.returncode}. Error: {result.stderr}")

        finally:
            # Clean up list file
            if list_file_path.exists():
                list_file_path.unlink()

    @staticmethod
    def verify_merged_file(input_paths: List[str], output_path: str) -> None:
        """
        Verifies that the merged file was created correctly:
        - Checks if output file exists.
        - Checks that the output file size is greater than 0.
        - Checks that the audio duration is within a reasonable threshold (e.g., +/- 4 seconds)
          of the sum of the input files' durations.
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

        # Check duration difference
        if total_input_duration > 0 and out_duration > 0:
            diff = abs(out_duration - total_input_duration)
            if diff > 4.0: # Margin of 4 seconds
                raise RuntimeError(
                    f"Die Dauer der zusammengefügten Datei weicht ab: "
                    f"{out_duration:.2f}s vs. erwartet {total_input_duration:.2f}s (Diff: {diff:.2f}s)"
                )
