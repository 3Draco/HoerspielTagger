import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from mutagen.id3 import ID3, TIT2, TALB, TPE1, TPE2, TRCK, TDRC, TCON, TCOM, TPUB, COMM, TPOS, APIC, ID3NoHeaderError
from chapter_manager import ChapterManager
from encoding_utils import fix_encoding_corruptions

class TagWriter:
    """Writes metadata, cover art, and embedded chapters to MP3 files using mutagen, ensuring clean ID3 tags for Plex."""

    @staticmethod
    def write_tags(
        filepath: str,
        title: str,
        album: str,
        artist: str,
        album_artist: str,
        track_number: int,
        genre: Any = "Hörspiel",
        year: Optional[int] = None,
        composer: Optional[str] = None,
        publisher: Optional[str] = None,
        comment: Optional[str] = None,
        disc_number: Optional[Any] = None,
        author: Optional[str] = None,
        cover_bytes: Optional[bytes] = None,
        chapters: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Sanitize text inputs against encoding corruptions (\ufffd, Mojibake)
        title = fix_encoding_corruptions(title)
        album = fix_encoding_corruptions(album)
        artist = fix_encoding_corruptions(artist)
        album_artist = fix_encoding_corruptions(album_artist)
        composer_val = fix_encoding_corruptions(composer or author) if (composer or author) else None
        publisher_val = fix_encoding_corruptions(publisher) if publisher else None
        comment_val = fix_encoding_corruptions(comment) if comment else None

        # Process multi-genre list for Jellyfin / Plex ID3 multi-genre TCON frame
        genres_list: List[str] = []
        def _add_genre_item(raw_val: str):
            for sub in raw_val.replace(';', ',').replace('/', ',').split(','):
                clean_sub = fix_encoding_corruptions(sub.strip())
                if clean_sub and clean_sub not in genres_list:
                    genres_list.append(clean_sub)

        if isinstance(genre, list):
            for item in genre:
                if isinstance(item, str):
                    _add_genre_item(item)
        elif isinstance(genre, str):
            _add_genre_item(str(genre))

        if not genres_list:
            genres_list = ["Hörspiel"]

        # Delete existing tags first to wipe out ID3v1 and old/messy ID3v2 tags
        try:
            old_tags = ID3(filepath)
            old_tags.delete()
        except ID3NoHeaderError:
            pass

        # Create fresh ID3v2 tags
        tags = ID3()

        # Set text frames (encoding=3 corresponds to UTF-8)
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TALB(encoding=3, text=album))
        tags.add(TPE1(encoding=3, text=artist))        # Track Artist (Series Name)
        tags.add(TPE2(encoding=3, text=album_artist))  # Album Artist (Series Name)
        tags.add(TRCK(encoding=3, text=f"{track_number:02d}" if isinstance(track_number, int) and track_number < 100 else str(track_number)))
        tags.add(TCON(encoding=3, text=genres_list))

        if year:
            tags.add(TDRC(encoding=3, text=str(year)))

        if composer_val:
            tags.add(TCOM(encoding=3, text=composer_val))

        if publisher_val:
            tags.add(TPUB(encoding=3, text=publisher_val))

        if comment_val:
            tags.add(COMM(encoding=3, lang='deu', desc='', text=comment_val))

        if disc_number is not None and str(disc_number).strip():
            tags.add(TPOS(encoding=3, text=str(disc_number).strip()))

        # Embed cover art if provided
        if cover_bytes:
            tags.add(APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,  # 3 = Cover (front)
                desc="Cover",
                data=cover_bytes
            ))

        # Save ID3v2.4 tags for native UTF-8 null-byte multi-genre support in Jellyfin & Plex
        tags.save(filepath, v2_version=4)

        # Embed ID3v2 CHAP & CTOC chapter frames if chapter data is provided
        if chapters:
            try:
                ChapterManager.embed_chapters(filepath, chapters)
            except Exception as chap_err:
                print(f"Warning: Could not embed chapter frames: {chap_err}")

