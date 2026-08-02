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
    def _calculate_score(cls, clean_artist: str, clean_title: str, cand_artist: str, cand_title: str, episode_num: Optional[str] = None, extra_bonus: int = 0) -> int:
        score = extra_bonus
        cand_art_lower = (cand_artist or "").lower().strip()
        cand_title_lower = (cand_title or "").lower().strip()
        clean_art_lower = (clean_artist or "").lower().strip()
        clean_title_lower = (clean_title or "").lower().strip()

        # Artist / Series Matching
        if clean_art_lower:
            artist_match = (clean_art_lower in cand_art_lower) or (cand_art_lower in clean_art_lower)
            title_has_artist = clean_art_lower in cand_title_lower

            if artist_match or title_has_artist:
                score += 15
            else:
                # Penalty only if clean_artist appears neither in artist nor in candidate title
                score -= 30

        # Episode Number Matching
        if episode_num:
            ep_str = str(episode_num).strip().lstrip("0")
            if ep_str:
                ep_patterns = [
                    r'\b' + re.escape(ep_str) + r'\b',
                    r'\b0+' + re.escape(ep_str) + r'\b',
                    r'folge\s*' + re.escape(ep_str)
                ]
                if any(re.search(pat, cand_title_lower, re.IGNORECASE) for pat in ep_patterns):
                    score += 15

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
    def search_cover_candidates(
        cls, 
        album_artist: str, 
        album: str, 
        episode_title: Optional[str] = None, 
        sources: Optional[List[str]] = None, 
        episode_num: Optional[Any] = None,
        provider_limits: Optional[Dict[str, int]] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches active APIs for cover art candidates with per-provider limits.
        sources can contain "itunes", "deezer", "musicbrainz", "discogs".
        """
        if not sources:
            sources = ["discogs", "itunes", "deezer", "musicbrainz"]

        if provider_limits is None:
            import config
            provider_limits = getattr(config, 'COVER_LIMITS', {"discogs": 3, "itunes": 3, "deezer": 3, "musicbrainz": 3})

        clean_artist = cls._clean_string(album_artist)
        raw_title = episode_title or album
        clean_title = cls._clean_string(raw_title)

        if clean_artist and clean_title and clean_artist.lower() in clean_title.lower():
            clean_title = re.sub(re.escape(clean_artist), '', clean_title, flags=re.IGNORECASE).strip()

        # Extract episode number if not explicitly passed
        ep_num_str = str(episode_num).strip() if episode_num is not None else ""
        if not ep_num_str and album:
            match = re.search(r'^(?:folge|track|cd)?\s*(\d{1,3})\b', album, flags=re.IGNORECASE)
            if match:
                ep_num_str = match.group(1)

        # Build artist variants (e.g. "Asterix & Obelix" -> ["Asterix & Obelix", "Asterix"])
        artist_variants = []
        if clean_artist:
            artist_variants.append(clean_artist)
            if " & " in clean_artist:
                sub_art = clean_artist.split(" & ")[0].strip()
                if sub_art and sub_art not in artist_variants:
                    artist_variants.append(sub_art)
            if " und " in clean_artist.lower():
                sub_art = re.split(r'\bund\b', clean_artist, flags=re.IGNORECASE)[0].strip()
                if sub_art and sub_art not in artist_variants:
                    artist_variants.append(sub_art)

        queries = []
        # 1. Primary queries: Artist variant + clean title (e.g. "Asterix der Gallier", "Asterix 01 der Gallier")
        for art in artist_variants:
            if clean_title:
                queries.append(f"{art} {clean_title}")
            if ep_num_str and clean_title:
                try:
                    ep_int = int(ep_num_str)
                    queries.append(f"{art} {ep_int:02d} {clean_title}")
                except Exception:
                    pass
                queries.append(f"{art} {ep_num_str} {clean_title}")

        # 2. Hörspiel prefix queries
        for art in artist_variants:
            if clean_title:
                queries.append(f"Hörspiel {art} {clean_title}")

        # 3. Fallback queries with album / title alone
        if clean_title:
            queries.append(f"Hörspiel {clean_title}")
            queries.append(clean_title)

        if clean_artist and album:
            clean_album = cls._clean_string(album)
            if clean_album and clean_album != clean_title:
                queries.append(f"{clean_artist} {clean_album}")

        unique_queries = []
        for q in queries:
            q_strip = q.strip()
            if q_strip and q_strip not in unique_queries:
                unique_queries.append(q_strip)
        queries = unique_queries

        candidates = []
        seen_urls = set()

        # 1. Discogs Source
        discogs_limit = provider_limits.get("discogs", 3)
        if "discogs" in sources and discogs_limit > 0:
            cls._search_discogs(queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=discogs_limit)

        # 2. iTunes Source
        itunes_limit = provider_limits.get("itunes", 3)
        if "itunes" in sources and itunes_limit > 0:
            cls._search_itunes(queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=itunes_limit)

        # 3. Deezer Source
        deezer_limit = provider_limits.get("deezer", 3)
        if "deezer" in sources and deezer_limit > 0:
            cls._search_deezer(queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=deezer_limit)

        # 4. MusicBrainz Source
        mb_limit = provider_limits.get("musicbrainz", 3)
        if "musicbrainz" in sources and mb_limit > 0:
            cls._search_musicbrainz(queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=mb_limit)

        # Sort candidates by relevance score descending
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    @classmethod
    def _search_discogs(cls, queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=3):
        added = 0
        import config
        token = getattr(config, 'DISCOGS_API_TOKEN', '')
        headers = {"User-Agent": "HoerspielTagger/1.3.0 (+https://github.com/3Draco/HoerspielTagger)"}
        if token:
            headers["Authorization"] = f"Discogs token={token}"

        discogs_url = "https://api.discogs.com/database/search"
        for query in queries:
            if not query.strip():
                continue
            params = {"q": query.strip(), "type": "release", "per_page": 15}
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
                        score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, episode_num=ep_num_str, extra_bonus=extra_bonus)

                        candidates.append({
                            "title": f"[Discogs] {col_name}",
                            "artist": art_name,
                            "url": artwork_url,
                            "thumb": thumb,
                            "year": year,
                            "score": score,
                            "source": "discogs"
                        })
                        added += 1
                        if added >= max_results:
                            return
            except Exception:
                pass

    @classmethod
    def _search_itunes(cls, queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=3):
        added = 0
        url = "https://itunes.apple.com/search"
        for media, entity in [("music", "album"), ("audiobook", None)]:
            for query in queries:
                if not query.strip():
                    continue
                params = {"term": query.strip(), "country": "DE", "media": media, "limit": 12}
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
                            score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, episode_num=ep_num_str, extra_bonus=extra_bonus)
                            
                            candidates.append({
                                "title": f"[iTunes] {col_name}",
                                "artist": art_name,
                                "url": high_res,
                                "thumb": artwork_url,
                                "year": year,
                                "score": score,
                                "source": "itunes"
                            })
                            added += 1
                            if added >= max_results:
                                return
                except Exception:
                    pass

    @classmethod
    def _search_deezer(cls, queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=3):
        added = 0
        url = "https://api.deezer.com/search/album"
        for query in queries:
            if not query.strip():
                continue
            try:
                response = requests.get(url, params={"q": query.strip(), "limit": 10}, timeout=5)
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

                        score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, episode_num=ep_num_str)
                        
                        candidates.append({
                            "title": f"[Deezer] {col_name}",
                            "artist": art_name,
                            "url": artwork_url,
                            "thumb": thumb,
                            "year": year,
                            "score": score,
                            "source": "deezer"
                        })
                        added += 1
                        if added >= max_results:
                            return
            except Exception:
                pass

    @classmethod
    def _search_musicbrainz(cls, queries, clean_artist, clean_title, ep_num_str, candidates, seen_urls, max_results=3):
        added = 0
        headers = {"User-Agent": "HoerspielTagger/1.3.0 (+https://github.com/3Draco/HoerspielTagger)"}
        if not queries:
            return
        query = queries[0]
        mb_url = "https://musicbrainz.org/ws/2/release"
        try:
            params = {"query": query.strip(), "limit": 5, "fmt": "json"}
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
                                    
                                    score = cls._calculate_score(clean_artist, clean_title, art_name, col_name, episode_num=ep_num_str)
                                    
                                    candidates.append({
                                        "title": f"[MusicBrainz] {col_name}",
                                        "artist": art_name,
                                        "url": high_res,
                                        "thumb": thumb,
                                        "year": year,
                                        "score": score,
                                        "source": "musicbrainz"
                                    })
                                    added += 1
                                    if added >= max_results:
                                        return
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
