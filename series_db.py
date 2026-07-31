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
    def load_db(cls) -> Dict[str, Dict[str, Any]]:
        path = cls._get_db_file_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"[SeriesDB] Error loading database: {e}")
        return {}

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
            return {
                "display_name": entry.get("display_name", query.strip()),
                "genre": entry.get("genre", "Hörspiel"),
                "aliases": entry.get("aliases", [])
            }

        # 2. Match against display_name or aliases
        for norm_key, entry in db.items():
            disp = entry.get("display_name", "")
            if cls._normalize_key(disp) == norm_query:
                return {
                    "display_name": disp,
                    "genre": entry.get("genre", "Hörspiel"),
                    "aliases": entry.get("aliases", [])
                }
            aliases = entry.get("aliases", [])
            for alias in aliases:
                if cls._normalize_key(alias) == norm_query:
                    return {
                        "display_name": disp,
                        "genre": entry.get("genre", "Hörspiel"),
                        "aliases": aliases
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
                    "genre": info["genre"],
                    "episode_num": int(num_str)
                }

        # Try matching full folder start against all registered aliases / series names
        db = cls.load_db()
        for norm_key, entry in db.items():
            disp_name = entry.get("display_name", "")
            aliases = entry.get("aliases", [])
            candidates = [disp_name] + aliases

            for cand in candidates:
                if not cand:
                    continue
                norm_cand = cls._normalize_key(cand)
                norm_folder = cls._normalize_key(folder_name)
                if norm_folder.startswith(norm_cand):
                    # Check if followed by digit or separator
                    remainder = norm_folder[len(norm_cand):].strip(" -_:")
                    num_match = re.match(r'^(\d{1,4})', remainder)
                    ep_num = int(num_match.group(1)) if num_match else None
                    return {
                        "series_name": disp_name,
                        "genre": entry.get("genre", "Hörspiel"),
                        "episode_num": ep_num
                    }
        return None

    @classmethod
    def set_series_genre(cls, series_name: str, genre: str, aliases: Optional[Any] = None, overwrite_existing: bool = True) -> bool:
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

        db[norm_key] = {
            "display_name": display_name,
            "genre": genre.strip(),
            "aliases": parsed_aliases
        }
        return cls.save_db(db)

    @classmethod
    def get_all_series_full(cls) -> List[Dict[str, Any]]:
        """Returns sorted list of dicts for GUI table display: [{"display_name": ..., "genre": ..., "aliases_str": "LB, LarryBrent"}]"""
        db = cls.load_db()
        result = []
        for norm_key, data in db.items():
            disp = data.get("display_name", norm_key)
            gen = data.get("genre", "Hörspiel")
            aliases = data.get("aliases", [])
            aliases_str = ", ".join(aliases)
            result.append({
                "display_name": disp,
                "genre": gen,
                "aliases": aliases,
                "aliases_str": aliases_str
            })
        return sorted(result, key=lambda x: x["display_name"].lower())

    @classmethod
    def get_all_series(cls) -> Dict[str, str]:
        """Returns a dict mapping display_name -> genre sorted alphabetically."""
        db = cls.load_db()
        result = {}
        for norm_key, data in db.items():
            disp = data.get("display_name", norm_key)
            gen = data.get("genre", "Hörspiel")
            result[disp] = gen
        return dict(sorted(result.items(), key=lambda x: x[0].lower()))

    @classmethod
    def get_prompt_aliases_summary(cls) -> str:
        """Formats a clean list of series acronyms/aliases for LLM system prompt context."""
        db = cls.load_db()
        lines = []
        for norm_key, data in db.items():
            disp = data.get("display_name", "")
            aliases = data.get("aliases", [])
            gen = data.get("genre", "")
            if aliases:
                alias_str = ", ".join(aliases)
                lines.append(f"- Kürzel '{alias_str}' -> Serie: '{disp}' (Genre: '{gen}')")
        return "\n".join(lines)

    @classmethod
    def delete_series(cls, series_name: str) -> bool:
        norm_key = cls._normalize_key(series_name)
        db = cls.load_db()
        if norm_key in db:
            del db[norm_key]
            return cls.save_db(db)
        return False
