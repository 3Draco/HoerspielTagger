import requests
import re
from typing import Optional, List, Dict

class CoverDownloader:
    """Fetches high-resolution album cover art using the iTunes Search API."""

    @staticmethod
    def _clean_string(text: str) -> str:
        if not text:
            return ""
        # Strip prefixes like '01 - ', 'Folge 01 - ', 'CD 1 - ', 'Track 01 - '
        cleaned = re.sub(r'^(?:folge|track|cd|disk)?\s*\d+[\s\-_:]*', '', text, flags=re.IGNORECASE)
        # Remove extra symbols
        cleaned = re.sub(r'[\-_:\*\|\?\"]', ' ', cleaned)
        return ' '.join(cleaned.split())

    @classmethod
    def search_cover_candidates(cls, album_artist: str, album: str, episode_title: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Searches iTunes API for cover art candidates across music albums and audiobooks.
        Returns a list of candidate dicts: [{'title': ..., 'artist': ..., 'url': ..., 'thumb': ...}]
        """
        clean_artist = cls._clean_string(album_artist)
        raw_title = episode_title or album
        clean_title = cls._clean_string(raw_title)

        if clean_artist and clean_title and clean_artist.lower() in clean_title.lower():
            clean_title = re.sub(re.escape(clean_artist), '', clean_title, flags=re.IGNORECASE).strip()

        queries = []
        if clean_artist and clean_title:
            queries.append(f"{clean_artist} {clean_title}")
        if clean_title:
            queries.append(clean_title)
        if album_artist and album:
            queries.append(f"{album_artist} {cls._clean_string(album)}")

        url = "https://itunes.apple.com/search"
        candidates = []
        seen_urls = set()

        # Prioritize ("music", "album") FIRST for German radio plays (Fünf Freunde, Die drei ???, TKKG)
        for media, entity in [("music", "album"), ("audiobook", None)]:
            for query in queries:
                if not query.strip():
                    continue

                params = {"term": query.strip(), "media": media, "limit": 6}
                if entity:
                    params["entity"] = entity

                try:
                    response = requests.get(url, params=params, timeout=8)
                    if response.status_code == 200:
                        results = response.json().get("results", [])
                        for res in results:
                            artwork_url = res.get("artworkUrl100")
                            if not artwork_url or artwork_url in seen_urls:
                                continue
                            seen_urls.add(artwork_url)

                            col_name = res.get("collectionName") or res.get("trackName") or ""
                            art_name = res.get("artistName") or ""
                            high_res = artwork_url.replace("100x100bb.jpg", "600x600bb.jpg")

                            # Simple title relevance score calculation
                            score = 0
                            if clean_title and clean_title.lower() in col_name.lower():
                                score += 10
                            if clean_artist and clean_artist.lower() in art_name.lower():
                                score += 5
                            if media == "music":
                                score += 2  # Prefer music entity for radio plays

                            candidates.append({
                                "title": col_name,
                                "artist": art_name,
                                "url": high_res,
                                "thumb": artwork_url,
                                "score": score
                            })
                except Exception:
                    pass

        # Sort candidates by relevance score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    @classmethod
    def search_cover_url(cls, album_artist: str, album: str, episode_title: Optional[str] = None) -> Optional[str]:
        """Returns the best matching high-resolution cover URL from candidate search."""
        candidates = cls.search_cover_candidates(album_artist, album, episode_title)
        if candidates:
            return candidates[0]["url"]
        return None

    @staticmethod
    def download_image(url: str) -> Optional[bytes]:
        """Downloads the image from the given URL and returns bytes."""
        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception:
            pass
        return None

