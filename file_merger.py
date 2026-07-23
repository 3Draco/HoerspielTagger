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
