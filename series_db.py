import os
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

class SeriesDatabase:
    """
    Manages persistent series-to-genre mappings and acronym/alias resolution
    to ensure 100% consistent genres and immediate series recognition
    across all episodes of audio drama series (e.g. 'LB08' -> 'Larry Brent', 'Hörspiel; Horror').
    """

    @staticmethod
    def _get_db_file_path() -> Path:
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        return base_dir / "series_database.json"

    @classmethod
    def _normalize_key(cls, name: str) -> str:
        if not name:
            return ""
        cleaned = re.sub(r'\s+', ' ', name.strip().lower())
        return cleaned

    @classmethod
    def _parse_aliases_input(cls, raw_aliases: Any) -> List[str]:
        if isinstance(raw_aliases, list):
            return [str(a).strip() for a in raw_aliases if str(a).strip()]
        elif isinstance(raw_aliases, str):
            parts = raw_aliases.split(",")
            return [p.strip() for p in parts if p.strip()]
        return []

    @classmethod
    def _parse_genres(cls, raw_genres: Any) -> List[str]:
        if isinstance(raw_genres, list):
            res = []
            for item in raw_genres:
                if isinstance(item, str):
                    for sub in item.replace(';', ',').split(','):
                        clean_sub = sub.strip()
                        if clean_sub and clean_sub not in res:
                            res.append(clean_sub)
            return res if res else ["Hörspiel"]
        elif isinstance(raw_genres, str) and raw_genres.strip():
            res = []
            for sub in raw_genres.replace(';', ',').split(','):
                clean_sub = sub.strip()
                if clean_sub and clean_sub not in res:
                    res.append(clean_sub)
            return res if res else ["Hörspiel"]
        return ["Hörspiel"]

    DEFAULT_SERIES_DB = {
        "die drei ???": {
            "display_name": "Die drei ???",
            "genres": ["Hörspiel", "Detektiv"],
            "aliases": ["Drei ???", "Die 3 ???", "D3?"],
            "composer": "Carsten Bohn",
            "publisher": "EUROPA",
            "comment": "Jugend-Detektiv Hörspiel von EUROPA."
        },
        "tkkg": {
            "display_name": "TKKG",
            "genres": ["Hörspiel", "Krimi"],
            "aliases": ["T.K.K.G."],
            "composer": "Carsten Bohn",
            "publisher": "EUROPA",
            "comment": "Jugend-Krimi Hörspiel von EUROPA."
        },
        "fünf freunde": {
            "display_name": "Fünf Freunde",
            "genres": ["Hörspiel", "Abenteuer"],
            "aliases": ["5 Freunde", "F5"],
            "composer": "Enid Blyton",
            "publisher": "EUROPA",
            "comment": "Abenteuer-Hörspiel nach Enid Blyton."
        },
        "larry brent": {
            "display_name": "Larry Brent",
            "genres": ["Hörspiel", "Horror"],
            "aliases": ["LB"],
            "composer": "H.G. Francis",
            "publisher": "EUROPA",
            "comment": "Grusel-Hörspiel nach den Romanen von A. F. Morland."
        },
        "macabros": {
            "display_name": "Macabros",
            "genres": ["Hörspiel", "Horror"],
            "aliases": ["MB"],
            "composer": "H.G. Francis",
            "publisher": "EUROPA",
            "comment": "Dämonen-Hörspiel von H.G. Francis."
        },
        "bibi blocksberg": {
            "display_name": "Bibi Blocksberg",
            "genres": ["Hörspiel", "Kinder"],
            "aliases": ["Bibi"],
            "composer": "Elfie Donnelly",
            "publisher": "Kiddinx",
            "comment": "Kinder-Hörspiel von Kiddinx."
        },
        "bibi und tina": {
            "display_name": "Bibi und Tina",
            "genres": ["Hörspiel", "Jugend"],
            "aliases": ["Bibi & Tina"],
            "composer": "Elfie Donnelly",
            "publisher": "Kiddinx",
            "comment": "Pferde-Abenteuer Hörspiel von Kiddinx."
        },
        "benjamin blümchen": {
            "display_name": "Benjamin Blümchen",
            "genres": ["Hörspiel", "Kinder"],
            "aliases": ["Benjamin"],
            "composer": "Elfie Donnelly",
            "publisher": "Kiddinx",
            "comment": "Kinder-Hörspiel von Kiddinx."
        },
        "geisterjäger john sinclair": {
            "display_name": "Geisterjäger John Sinclair",
            "genres": ["Hörspiel", "Horror"],
            "aliases": ["John Sinclair", "JS"],
            "composer": "Jason Dark",
            "publisher": "Lübbe Audio",
            "comment": "Grusel-Hörspiel nach den Romanen von Jason Dark."
        },
        "gabriel burns": {
            "display_name": "Gabriel Burns",
            "genres": ["Hörspiel", "Thriller"],
            "aliases": ["GB"],
            "composer": "Volker Sponholz",
            "publisher": "Folgenreich",
            "comment": "Mystery-Hörspielserie von Folgenreich."
        },
        "jan tenner": {
            "display_name": "Jan Tenner",
            "genres": ["Hörspiel", "Science-Fiction"],
            "aliases": ["JT"],
            "composer": "Dick Farlow",
            "publisher": "Karussell",
            "comment": "Science-Fiction Hörspielserie von Karussell."
        },
        "sherlock holmes": {
            "display_name": "Sherlock Holmes",
            "genres": ["Hörspiel", "Krimi"],
            "aliases": ["SH"],
            "composer": "Arthur Conan Doyle",
            "publisher": "Maritim",
            "comment": "Kriminal-Hörspiel nach Sir Arthur Conan Doyle."
        },
        "offenbarung 23": {
            "display_name": "Offenbarung 23",
            "genres": ["Hörspiel", "Thriller"],
            "aliases": ["O23"],
            "composer": "Jan Gaspard",
            "publisher": "Lübbe Audio",
            "comment": "Verschwörungs-Thriller Hörspiel."
        },
        "alf": {
            "display_name": "ALF",
            "genres": ["Hörspiel", "Comedy"],
            "aliases": ["Alf"],
            "composer": "Siegfried Rabe",
            "publisher": "Karussell",
            "comment": "Kult-Comedy Hörspiel nach der US-Sitcom."
        }
    }

    @classmethod
    def load_db(cls) -> Dict[str, Dict[str, Any]]:
        path = cls._get_db_file_path()
        if not path.exists():
            # Seed default JSON database
            cls.save_db(cls.DEFAULT_SERIES_DB)
            return dict(cls.DEFAULT_SERIES_DB)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Ensure defaults exist in DB
                    updated = False
                    for default_key, default_val in cls.DEFAULT_SERIES_DB.items():
                        if default_key not in data:
                            data[default_key] = default_val
                            updated = True
                        else:
                            for field in ["composer", "publisher", "comment"]:
                                if field not in data[default_key]:
                                    data[default_key][field] = default_val[field]
                                    updated = True
                    if updated:
                        cls.save_db(data)
                    return data
        except Exception as e:
            print(f"[SeriesDB] Error loading database: {e}")
        return dict(cls.DEFAULT_SERIES_DB)

    @classmethod
    def save_db(cls, db: Dict[str, Dict[str, Any]]) -> bool:
        path = cls._get_db_file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[SeriesDB] Error saving database: {e}")
            return False

    @classmethod
    def get_genre(cls, series_name: str) -> Optional[str]:
        info = cls.get_series_info(series_name)
        return info["genre"] if info else None

    @classmethod
    def get_series_info(cls, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        norm_query = cls._normalize_key(query)
        if not norm_query:
            return None

        db = cls.load_db()

        # 1. Exact match on normalized primary key
        if norm_query in db:
            entry = db[norm_query]
            genres_list = cls._parse_genres(entry.get("genres") or entry.get("genre"))
            return {
                "display_name": entry.get("display_name", query.strip()),
                "genres": genres_list,
                "genre": "; ".join(genres_list),
                "aliases": entry.get("aliases", []),
                "composer": entry.get("composer", ""),
                "publisher": entry.get("publisher", ""),
                "comment": entry.get("comment", "")
            }

        # 2. Match against display_name or aliases
        for norm_key, entry in db.items():
            disp = entry.get("display_name", "")
            aliases = entry.get("aliases", [])
            genres_list = cls._parse_genres(entry.get("genres") or entry.get("genre"))

            if cls._normalize_key(disp) == norm_query:
                return {
                    "display_name": disp,
                    "genres": genres_list,
                    "genre": "; ".join(genres_list),
                    "aliases": aliases,
                    "composer": entry.get("composer", ""),
                    "publisher": entry.get("publisher", ""),
                    "comment": entry.get("comment", "")
                }
            for alias in aliases:
                if cls._normalize_key(alias) == norm_query:
                    return {
                        "display_name": disp,
                        "genres": genres_list,
                        "genre": "; ".join(genres_list),
                        "aliases": aliases,
                        "composer": entry.get("composer", ""),
                        "publisher": entry.get("publisher", ""),
                        "comment": entry.get("comment", "")
                    }
        return None

    @classmethod
    def resolve_folder_prefix(cls, folder_name: str) -> Optional[Dict[str, Any]]:
        """
        Extracts prefix shortcuts (e.g. 'LB08', 'LB 08', 'JS120', 'F08') from folder names
        and matches them against registered series aliases.
        """
        if not folder_name:
            return None

        # Regex for prefix code followed by number (e.g. 'LB08', 'LB 08', 'JS-12')
        match = re.match(r'^([A-Za-zäöüÄÖÜß]{1,10})\s*[-_:]?\s*(\d{1,4})', folder_name.strip())
        if match:
            code_prefix, num_str = match.groups()
            info = cls.get_series_info(code_prefix)
            if info:
                return {
                    "series_name": info["display_name"],
                    "genres": info["genres"],
                    "genre": info["genre"],
                    "episode_num": int(num_str)
                }

        # Try matching full folder start against all registered aliases / series names
        db = cls.load_db()
        for norm_key, entry in db.items():
            disp_name = entry.get("display_name", "")
            aliases = entry.get("aliases", [])
            candidates = [disp_name] + aliases
            genres_list = cls._parse_genres(entry.get("genres") or entry.get("genre"))

            for cand in candidates:
                if not cand:
                    continue
                norm_cand = cls._normalize_key(cand)
                norm_folder = cls._normalize_key(folder_name)
                if norm_folder.startswith(norm_cand):
                    remainder = norm_folder[len(norm_cand):].strip(" -_:")
                    num_match = re.match(r'^(\d{1,4})', remainder)
                    ep_num = int(num_match.group(1)) if num_match else None
                    return {
                        "series_name": disp_name,
                        "genres": genres_list,
                        "genre": "; ".join(genres_list),
                        "episode_num": ep_num
                    }
        return None

    @classmethod
    def set_series_genre(
        cls,
        series_name: str,
        genre: Any,
        aliases: Optional[Any] = None,
        composer: Optional[str] = None,
        publisher: Optional[str] = None,
        comment: Optional[str] = None,
        overwrite_existing: bool = True
    ) -> bool:
        if not series_name or not genre:
            return False
        norm_key = cls._normalize_key(series_name)
        if not norm_key:
            return False

        db = cls.load_db()
        existing = db.get(norm_key, {})
        if norm_key in db and not overwrite_existing:
            return False

        display_name = series_name.strip()
        parsed_aliases = cls._parse_aliases_input(aliases) if aliases is not None else existing.get("aliases", [])
        genres_list = cls._parse_genres(genre)

        db[norm_key] = {
            "display_name": display_name,
            "genres": genres_list,
            "genre": "; ".join(genres_list),
            "aliases": parsed_aliases,
            "composer": composer if composer is not None else existing.get("composer", ""),
            "publisher": publisher if publisher is not None else existing.get("publisher", ""),
            "comment": comment if comment is not None else existing.get("comment", "")
        }
        return cls.save_db(db)

    @classmethod
    def get_all_series_full(cls) -> List[Dict[str, Any]]:
        """Returns sorted list of dicts for GUI table display: [{"display_name": ..., "genre": ..., "aliases_str": "LB, LarryBrent"}]"""
        db = cls.load_db()
        result = []
        for norm_key, data in db.items():
            disp = data.get("display_name", norm_key)
            genres_list = cls._parse_genres(data.get("genres") or data.get("genre"))
            gen_str = "; ".join(genres_list)
            aliases = data.get("aliases", [])
            aliases_str = ", ".join(aliases)
            result.append({
                "display_name": disp,
                "genres": genres_list,
                "genre": gen_str,
                "aliases": aliases,
                "aliases_str": aliases_str,
                "composer": data.get("composer", ""),
                "publisher": data.get("publisher", ""),
                "comment": data.get("comment", "")
            })
        return sorted(result, key=lambda x: x["display_name"].lower())

    @classmethod
    def get_all_series(cls) -> Dict[str, str]:
        """Returns a dict mapping display_name -> genre sorted alphabetically."""
        db = cls.load_db()
        result = {}
        for norm_key, data in db.items():
            disp = data.get("display_name", norm_key)
            genres_list = cls._parse_genres(data.get("genres") or data.get("genre"))
            result[disp] = "; ".join(genres_list)
        return dict(sorted(result.items(), key=lambda x: x[0].lower()))

    @classmethod
    def get_prompt_aliases_summary(cls) -> str:
        """Formats a clean list of series acronyms/aliases, genres, composer, and publisher for LLM system prompt context."""
        db = cls.load_db()
        lines = []
        for norm_key, data in db.items():
            disp = data.get("display_name", "")
            aliases = data.get("aliases", [])
            genres_list = cls._parse_genres(data.get("genres") or data.get("genre"))
            gen_str = "; ".join(genres_list)
            comp = data.get("composer", "")
            pub = data.get("publisher", "")
            
            extra = []
            if comp:
                extra.append(f"Komponist/Autor: '{comp}'")
            if pub:
                extra.append(f"Label: '{pub}'")
            extra_str = f" ({', '.join(extra)})" if extra else ""

            if aliases:
                alias_str = ", ".join(aliases)
                lines.append(f"- Kürzel '{alias_str}' -> Serie: '{disp}' (Genre: '{gen_str}'){extra_str}")
            elif disp:
                lines.append(f"- Serie: '{disp}' (Genre: '{gen_str}'){extra_str}")
        return "\n".join(lines)

    @classmethod
    def delete_series(cls, series_name: str) -> bool:
        norm_key = cls._normalize_key(series_name)
        db = cls.load_db()
        if norm_key in db:
            del db[norm_key]
            return cls.save_db(db)
        return False

    @classmethod
    def get_known_series_defaults(cls, series_query: str) -> Optional[Dict[str, str]]:
        if not series_query:
            return None
        info = cls.get_series_info(series_query)
        if info and (info.get("composer") or info.get("publisher") or info.get("comment")):
            return {
                "composer": info.get("composer", ""),
                "publisher": info.get("publisher", ""),
                "comment": info.get("comment", "")
            }
        return None
