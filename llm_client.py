import json
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from config import LLM_MODEL_ID, get_llm_client_kwargs, DEFAULT_SYSTEM_PROMPT, LLM_SYSTEM_PROMPT
from encoding_utils import fix_encoding_corruptions, sanitize_metadata_obj

# Pydantic models for strict validation
class TrackMetadata(BaseModel):
    original_filename: str = Field(description="The exact original filename from the input.")
    clean_title: str = Field(default="", description="The cleaned title of the track/chapter.")
    chapter_title: Optional[str] = Field(default=None, description="Alias for clean_title.")
    track_number: int = Field(default=1, description="Sequential track number starting from 1.")
    chapter_index: Optional[int] = Field(default=None, description="Alias for track_number.")
    new_filename: Optional[str] = Field(default="", description="Target filename.")

    def model_post_init(self, __context: Any) -> None:
        if not self.clean_title and self.chapter_title:
            self.clean_title = self.chapter_title
        elif not self.chapter_title and self.clean_title:
            self.chapter_title = self.clean_title
        if self.chapter_index is not None and self.track_number == 1:
            self.track_number = self.chapter_index
        if not self.new_filename:
            self.new_filename = f"{self.track_number:02d} - {self.clean_title}.mp3"

class AlbumMetadata(BaseModel):
    album_artist: str = Field(default="Hörspiel", description="The series name / main artist (e.g. 'Fünf Freunde').")
    series_name: Optional[str] = Field(default=None, description="Alias for series / album_artist.")
    series: str = Field(default="Hörspiel", description="The series name.")
    series_part: Optional[int] = Field(default=None, description="The episode or volume number of the series.")
    episode_number: Optional[int] = Field(default=None, description="Alias for series_part.")
    album: str = Field(default="", description="Full album title format: '04 - Episode Title'.")
    episode_title: Optional[str] = Field(default=None, description="Clean episode title without episode number prefix.")
    year: Optional[int] = Field(default=None, description="The release year.")
    composer: Optional[str] = Field(default=None, description="Composer or soundtrack author.")
    author: Optional[str] = Field(default=None, description="Author / creator alias for composer.")
    publisher: Optional[str] = Field(default=None, description="Hörspiel label / publisher (e.g. 'EUROPA', 'Kiddinx', 'Maritim').")
    comment: Optional[str] = Field(default=None, description="Comment or additional notes.")
    disc_number: Optional[int] = Field(default=1, description="Disc number.")
    primary_genre: Optional[str] = Field(default=None, description="Primary genre.")
    secondary_genre: Optional[str] = Field(default=None, description="Secondary genre / subgenre.")
    formatted_genre: Optional[str] = Field(default=None, description="Formatted genre string.")
    genre: Optional[str] = Field(default=None, description="Legacy genre string for ID3 tags.")
    genres: List[str] = Field(default_factory=lambda: ["Hörspiel"], description="Multi-genre list (e.g. ['Hörspiel', 'Comedy']).")
    tracks: List[TrackMetadata] = Field(default_factory=list, description="List of tracks/chapters.")
    chapters: Optional[List[TrackMetadata]] = Field(default=None, description="Alias for tracks.")

    def model_post_init(self, __context: Any) -> None:
        if self.author and not self.composer:
            self.composer = self.author
        elif self.composer and not self.author:
            self.author = self.composer
        # Normalize multi-genre list
        parsed_genres: List[str] = []
        if isinstance(self.genres, list) and self.genres:
            for item in self.genres:
                if isinstance(item, str):
                    for sub in item.replace(';', ',').split(','):
                        clean_sub = sub.strip()
                        if clean_sub and clean_sub not in parsed_genres:
                            parsed_genres.append(clean_sub)
        elif isinstance(self.genres, str) and self.genres:
            for sub in str(self.genres).replace(';', ',').split(','):
                clean_sub = sub.strip()
                if clean_sub and clean_sub not in parsed_genres:
                    parsed_genres.append(clean_sub)

        # Fallback from legacy genre fields if genres list was empty
        legacy_str = self.formatted_genre or self.genre
        if not legacy_str and self.primary_genre and self.secondary_genre:
            legacy_str = f"{self.primary_genre}; {self.secondary_genre}"

        if legacy_str:
            for sub in str(legacy_str).replace(';', ',').split(','):
                clean_sub = sub.strip()
                if clean_sub and clean_sub not in parsed_genres:
                    parsed_genres.append(clean_sub)

        if not parsed_genres:
            parsed_genres = ["Hörspiel"]

        self.genres = parsed_genres
        self.genre = "; ".join(self.genres)
        self.formatted_genre = self.genre

        if self.series_name and not self.album_artist:
            self.album_artist = self.series_name
        if self.series_name and not self.series:
            self.series = self.series_name
        if self.episode_number is not None and self.series_part is None:
            self.series_part = self.episode_number
        if self.chapters and not self.tracks:
            self.tracks = self.chapters
        elif self.tracks and not self.chapters:
            self.chapters = self.tracks

        # Sanitize episode_title if it was mistakenly parsed as just digits (e.g. "08")
        if self.episode_title and re.match(r"^\d+$", self.episode_title.strip()):
            self.episode_title = None

        # Ensure album format is zero-padded '{series_part:02d} - {episode_title}' if both are present
        if self.series_part is not None and self.episode_title:
            self.album = f"{self.series_part:02d} - {self.episode_title}"
        elif self.series_part is not None and self.album and not self.episode_title:
            # If album has title like "08 - Das Grauen von Blackwood Castle", extract pure episode_title
            match = re.match(r"^(?:[A-Za-z]+)?\d+\s*[-_\s:]\s*(.+)$", self.album)
            if match:
                self.episode_title = match.group(1).strip()
                self.album = f"{self.series_part:02d} - {self.episode_title}"

class LLMClient:
    """Handles communication with the LLM to get cleaned metadata and file names."""

    def __init__(self):
        kwargs = get_llm_client_kwargs()
        self.client = OpenAI(**kwargs["client_init"])
        self.extra_headers = kwargs["extra_headers"]
        self.extra_body = kwargs["extra_body"]

    def analyze_album(self, folder_name: str, tracks: List[Dict[str, Any]], custom_prompt: Optional[str] = None) -> AlbumMetadata:
        """Sends folder name and tracks context to the LLM and returns validated AlbumMetadata."""
        
        # Prepare context
        context_data = {
            "folder_name": folder_name,
            "tracks": [
                {
                    "filename": t["filename"],
                    "current_title": t["title"],
                    "current_track_number": t["track_number"],
                    "current_album": t["album"],
                    "current_artist": t["artist"],
                    "current_album_artist": t["album_artist"],
                    "current_year": t["year"]
                }
                for t in tracks
            ]
        }

        system_prompt = custom_prompt or getattr(config, 'LLM_SYSTEM_PROMPT', DEFAULT_SYSTEM_PROMPT) or DEFAULT_SYSTEM_PROMPT

        user_content = f"Please analyze this folder context and generate the clean metadata:\n\n{json.dumps(context_data, indent=2, ensure_ascii=False)}"

        try:
            # We try using json_object response format, but catch errors if the model/backend doesn't support it
            response = self.client.chat.completions.create(
                model=LLM_MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                extra_headers=self.extra_headers,
                extra_body=self.extra_body
            )
            raw_content = response.choices[0].message.content
        except Exception:
            # Fallback without response_format
            response = self.client.chat.completions.create(
                model=LLM_MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                extra_headers=self.extra_headers,
                extra_body=self.extra_body
            )
            raw_content = response.choices[0].message.content

        # Parse and validate response
        parsed_json = self._clean_and_parse_json(raw_content)
        sanitized_json = sanitize_metadata_obj(parsed_json)
        return AlbumMetadata(**sanitized_json)

    def _clean_and_parse_json(self, raw_content: str) -> Dict[str, Any]:
        """Cleans potential markdown markers and parses JSON string."""
        if not raw_content:
            raise ValueError("Empty response from LLM API.")
            
        cleaned = raw_content.strip()
        # Remove ```json and ``` codeblocks if present
        if cleaned.startswith("```"):
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()

        return json.loads(cleaned)
