import requests
import re
from typing import Optional, List, Dict, Any

class CoverDownloader:
    """Fetches high-resolution album cover art using iTunes, Deezer, and MusicBrainz APIs."""

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
    def search_cover_candidates(cls, album_artist: str, album: str, episode_title: Optional[str] = None, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Searches active APIs for cover art candidates.
        sources can contain "itunes", "deezer", "musicbrainz".
        """
        if not sources:
            sources = ["itunes", "deezer", "musicbrainz"]

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

        candidates = []
        seen_urls = set()

        # 1. iTunes Source
        if "itunes" in sources:
            cls._search_itunes(queries, clean_artist, clean_title, candidates, seen_urls)

        # 2. Deezer Source
        if "deezer" in sources:
            cls._search_deezer(queries, clean_artist, clean_title, candidates, seen_urls)

        # 3. MusicBrainz Source
        if "musicbrainz" in sources:
            cls._search_musicbrainz(queries, clean_artist, clean_title, candidates, seen_urls)

        # Sort candidates by relevance score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    @classmethod
    def _search_itunes(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        url = "https://itunes.apple.com/search"
        for media, entity in [("music", "album"), ("audiobook", None)]:
            for query in queries:
                if not query.strip():
                    continue
                params = {"term": query.strip(), "media": media, "limit": 4}
                if entity:
                    params["entity"] = entity
                try:
                    response = requests.get(url, params=params, timeout=5)
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
                            
                            score = 0
                            if clean_title and clean_title.lower() in col_name.lower():
                                score += 10
                            if clean_artist and clean_artist.lower() in art_name.lower():
                                score += 5
                            if media == "music":
                                score += 2
                            
                            candidates.append({
                                "title": f"[iTunes] {col_name}",
                                "artist": art_name,
                                "url": high_res,
                                "thumb": artwork_url,
                                "score": score
                            })
                except Exception:
                    pass

    @classmethod
    def _search_deezer(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        url = "https://api.deezer.com/search/album"
        for query in queries:
            if not query.strip():
                continue
            try:
                response = requests.get(url, params={"q": query.strip(), "limit": 4}, timeout=5)
                if response.status_code == 200:
                    results = response.json().get("data", [])
                    for res in results:
                        artwork_url = res.get("cover_xl") or res.get("cover_big") or res.get("cover_medium")
                        if not artwork_url or artwork_url in seen_urls:
                            continue
                        seen_urls.add(artwork_url)
                        col_name = res.get("title") or ""
                        art_name = res.get("artist", {}).get("name") or ""
                        thumb = res.get("cover_medium") or res.get("cover_small") or artwork_url
                        
                        score = 0
                        if clean_title and clean_title.lower() in col_name.lower():
                            score += 10
                        if clean_artist and clean_artist.lower() in art_name.lower():
                            score += 5
                        
                        candidates.append({
                            "title": f"[Deezer] {col_name}",
                            "artist": art_name,
                            "url": artwork_url,
                            "thumb": thumb,
                            "score": score
                        })
            except Exception:
                pass

    @classmethod
    def _search_musicbrainz(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        headers = {"User-Agent": "HoerspielTagger/1.0.0 ( https://github.com/3Draco/HoerspielTagger )"}
        if not queries:
            return
        query = queries[0]
        mb_url = "https://musicbrainz.org/ws/2/release"
        try:
            params = {"query": query.strip(), "limit": 3, "fmt": "json"}
            response = requests.get(mb_url, params=params, headers=headers, timeout=6)
            if response.status_code == 200:
                releases = response.json().get("releases", [])
                for rel in releases:
                    mbid = rel.get("id")
                    if not mbid:
                        continue
                    caa_url = f"https://coverartarchive.org/release/{mbid}"
                    try:
                        caa_resp = requests.get(caa_url, timeout=4)
                        if caa_resp.status_code == 200:
                            caa_data = caa_resp.json()
                            for img in caa_data.get("images", []):
                                if img.get("front"):
                                    high_res = img.get("image")
                                    if not high_res or high_res in seen_urls:
                                        continue
                                    seen_urls.add(high_res)
                                    thumbs = img.get("thumbnails", {})
                                    thumb = thumbs.get("250") or thumbs.get("small") or high_res
                                    col_name = rel.get("title") or ""
                                    art_name = rel.get("artist-credit", [{}])[0].get("name") or ""
                                    
                                    score = 0
                                    if clean_title and clean_title.lower() in col_name.lower():
                                        score += 10
                                    if clean_artist and clean_artist.lower() in art_name.lower():
                                        score += 5
                                    
                                    candidates.append({
                                        "title": f"[MusicBrainz] {col_name}",
                                        "artist": art_name,
                                        "url": high_res,
                                        "thumb": thumb,
                                        "score": score
                                    })
                                    break
                    except Exception:
                        pass
        except Exception:
            pass

    @classmethod
    def search_cover_url(cls, album_artist: str, album: str, episode_title: Optional[str] = None, sources: Optional[List[str]] = None) -> Optional[str]:
        """Returns the best matching high-resolution cover URL from candidate search."""
        candidates = cls.search_cover_candidates(album_artist, album, episode_title, sources)
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
