import requests
import re
from typing import Optional, List, Dict, Any

class CoverDownloader:
    """Fetches high-resolution album cover art and release metadata using iTunes, Deezer, MusicBrainz, and Discogs APIs."""

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
    def _calculate_score(cls, clean_artist: str, clean_title: str, cand_artist: str, cand_title: str, extra_bonus: int = 0) -> int:
        score = extra_bonus
        cand_art_lower = (cand_artist or "").lower().strip()
        cand_title_lower = (cand_title or "").lower().strip()
        clean_art_lower = (clean_artist or "").lower().strip()
        clean_title_lower = (clean_title or "").lower().strip()

        # Artist Matching
        if clean_art_lower:
            if clean_art_lower in cand_art_lower or cand_art_lower in clean_art_lower:
                score += 15
            elif cand_art_lower and not any(w in cand_art_lower for w in clean_art_lower.split() if len(w) > 2):
                # Major artist mismatch penalty (e.g. searching "Alf" vs "Rita Falk")
                score -= 30

        # Title Matching
        if clean_title_lower:
            if clean_title_lower in cand_title_lower:
                score += 20
            else:
                # Word match check
                words = [w for w in re.split(r'\W+', clean_title_lower) if len(w) > 2]
                if words:
                    matching_words = [w for w in words if w in cand_title_lower]
                    match_ratio = len(matching_words) / len(words)
                    if match_ratio == 1.0:
                        score += 15
                    elif match_ratio >= 0.5:
                        score += 8
                    elif match_ratio == 0:
                        score -= 20
                else:
                    score -= 10
        return score

    @classmethod
    def search_cover_candidates(cls, album_artist: str, album: str, episode_title: Optional[str] = None, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Searches active APIs for cover art candidates.
        sources can contain "itunes", "deezer", "musicbrainz", "discogs".
        """
        if not sources:
            sources = ["discogs", "itunes", "deezer", "musicbrainz"]

        clean_artist = cls._clean_string(album_artist)
        raw_title = episode_title or album
        clean_title = cls._clean_string(raw_title)

        if clean_artist and clean_title and clean_artist.lower() in clean_title.lower():
            clean_title = re.sub(re.escape(clean_artist), '', clean_title, flags=re.IGNORECASE).strip()

        queries = []
        if clean_artist and clean_title:
            queries.append(f"{clean_artist} {clean_title}")
            queries.append(f"Hörspiel {clean_artist} {clean_title}")
        if clean_artist and album:
            clean_album = cls._clean_string(album)
            if clean_album and clean_album != clean_title:
                queries.append(f"{clean_artist} {clean_album}")

        # Only fallback to searching clean_title alone if clean_artist is completely empty!
        if not clean_artist and clean_title:
            queries.append(clean_title)

        unique_queries = []
        for q in queries:
            q_strip = q.strip()
            if q_strip and q_strip not in unique_queries:
                unique_queries.append(q_strip)
        queries = unique_queries

        candidates = []
        seen_urls = set()

        # 1. Discogs Source
        if "discogs" in sources:
            cls._search_discogs(queries, clean_artist, clean_title, candidates, seen_urls)

        # 2. iTunes Source
        if "itunes" in sources:
            cls._search_itunes(queries, clean_artist, clean_title, candidates, seen_urls)

        # 3. Deezer Source
        if "deezer" in sources:
            cls._search_deezer(queries, clean_artist, clean_title, candidates, seen_urls)

        # 4. MusicBrainz Source
        if "musicbrainz" in sources:
            cls._search_musicbrainz(queries, clean_artist, clean_title, candidates, seen_urls)

        # Sort candidates by relevance score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    @classmethod
    def _search_discogs(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        import config
        token = getattr(config, 'DISCOGS_API_TOKEN', '')
        headers = {"User-Agent": "HoerspielTagger/1.3.0 (+https://github.com/3Draco/HoerspielTagger)"}
        if token:
            headers["Authorization"] = f"Discogs token={token}"

        discogs_url = "https://api.discogs.com/database/search"
        for query in queries:
            if not query.strip():
                continue
            params = {"q": query.strip(), "type": "release", "per_page": 5}
            if token:
                params["token"] = token
            try:
                response = requests.get(discogs_url, params=params, headers=headers, timeout=6)
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    for res in results:
                        artwork_url = res.get("cover_image") or res.get("thumb")
                        resource_url = res.get("resource_url")

                        if not artwork_url and resource_url:
                            try:
                                rel_resp = requests.get(resource_url, headers=headers, timeout=4)
                                if rel_resp.status_code == 200:
                                    imgs = rel_resp.json().get("images", [])
                                    if imgs:
                                        artwork_url = imgs[0].get("resource_url") or imgs[0].get("uri")
                            except Exception:
                                pass

                        if not artwork_url or artwork_url in seen_urls:
                            continue
                        seen_urls.add(artwork_url)
                        full_title = res.get("title") or ""
                        parts = full_title.split(" - ", 1)
                        art_name = parts[0] if len(parts) > 1 else ""
                        col_name = parts[1] if len(parts) > 1 else full_title
                        thumb = res.get("thumb") or artwork_url
                        
                        year_val = res.get("year")
                        year = None
                        if year_val:
                            try:
                                year = int(str(year_val)[:4])
                            except (ValueError, TypeError):
                                year = None
                                
                        extra_bonus = 0
                        formats = [str(f).lower() for f in res.get("format", [])]
                        if any(f in ["cassette", "album", "audiobook"] for f in formats):
                            extra_bonus += 2
                        score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, extra_bonus=extra_bonus)

                        candidates.append({
                            "title": f"[Discogs] {col_name}",
                            "artist": art_name,
                            "url": artwork_url,
                            "thumb": thumb,
                            "year": year,
                            "score": score,
                            "source": "discogs"
                        })
            except Exception:
                pass

    @classmethod
    def _search_itunes(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        url = "https://itunes.apple.com/search"
        for media, entity in [("music", "album"), ("audiobook", None)]:
            for query in queries:
                if not query.strip():
                    continue
                params = {"term": query.strip(), "country": "DE", "media": media, "limit": 6}
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
                            
                            rel_date = str(res.get("releaseDate") or "")
                            year = int(rel_date[:4]) if len(rel_date) >= 4 and rel_date[:4].isdigit() else None

                            extra_bonus = 2 if media == "music" else 0
                            score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, extra_bonus=extra_bonus)
                            
                            candidates.append({
                                "title": f"[iTunes] {col_name}",
                                "artist": art_name,
                                "url": high_res,
                                "thumb": artwork_url,
                                "year": year,
                                "score": score,
                                "source": "itunes"
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
                        
                        rel_date = str(res.get("release_date") or "")
                        year = int(rel_date[:4]) if len(rel_date) >= 4 and rel_date[:4].isdigit() else None

                        score = cls._calculate_score(clean_artist, clean_title, art_name, col_name)
                        
                        candidates.append({
                            "title": f"[Deezer] {col_name}",
                            "artist": art_name,
                            "url": artwork_url,
                            "thumb": thumb,
                            "year": year,
                            "score": score,
                            "source": "deezer"
                        })
            except Exception:
                pass

    @classmethod
    def _search_musicbrainz(cls, queries, clean_artist, clean_title, candidates, seen_urls):
        headers = {"User-Agent": "HoerspielTagger/1.3.0 (+https://github.com/3Draco/HoerspielTagger)"}
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
                    date_str = str(rel.get("first-release-date") or rel.get("date") or "")
                    year = int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else None

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
                                    
                                    score = cls._calculate_score(clean_artist, clean_title, art_name, col_name)
                                    
                                    candidates.append({
                                        "title": f"[MusicBrainz] {col_name}",
                                        "artist": art_name,
                                        "url": high_res,
                                        "thumb": thumb,
                                        "year": year,
                                        "score": score,
                                        "source": "musicbrainz"
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
        if candidates and candidates[0].get("score", 0) >= 10:
            return candidates[0]["url"]
        return None

    @staticmethod
    def download_image(url: str) -> Optional[bytes]:
        """Downloads the image from the given URL with proper browser headers."""
        if not url:
            return None
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        try:
            import config
            token = getattr(config, 'DISCOGS_API_TOKEN', '')
            if "discogs.com" in url.lower() and token:
                headers["Authorization"] = f"Discogs token={token}"
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.content
        except Exception:
            pass
        return None
