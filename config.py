import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

APP_VERSION = "v1.5.3"

# API Configuration
LLM_API_BASE_URL = os.getenv("LLM_API_BASE_URL", "http://127.0.0.1:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "meta-llama-3-8b-instruct")
DISCOGS_API_TOKEN = os.getenv("DISCOGS_API_TOKEN", "")


DEFAULT_SYSTEM_PROMPT = (
    "You are a professional metadata tagging assistant for media servers (like Jellyfin, Plex) and offline hardware MP3 players.\n"
    "Your task is to analyze audio drama (Hörspiel) folder names and track information, and return a clean, correct, unified metadata structure.\n\n"
    "CRITICAL RULES FOR AUDIO DRAMAS (HÖRSHPIELE):\n"
    "1. Series Name (series / album_artist):\n"
    "   - Identify the main series name (e.g., 'Larry Brent', 'Fünf Freunde', 'Die drei ???', 'TKKG', 'John Sinclair').\n"
    "   - Notice folder prefixes: e.g. 'LB08' or 'LB16' -> 'LB' stands for 'Larry Brent'. 'F08' -> 'Fünf Freunde'.\n\n"
    "2. Episode Number (series_part):\n"
    "   - Extract the episode or volume number as an INTEGER (e.g. 'LB08' -> 8, 'LB16' -> 16, '08 - Title' -> 8).\n\n"
    "3. Episode Title (episode_title):\n"
    "   - Extract ONLY the clean title of the episode WITHOUT the series name, WITHOUT series code prefixes (like LB08, LB16), and WITHOUT episode numbers!\n"
    "   - Examples:\n"
    "     * Folder 'LB08 - Das Grauen von Blackwood Castle' -> series_part: 8, episode_title: 'Das Grauen von Blackwood Castle', series: 'Larry Brent'\n"
    "     * Folder 'LB16 - Orungu, Fratze aus dem Dschungel' -> series_part: 16, episode_title: 'Orungu, Fratze aus dem Dschungel', series: 'Larry Brent'\n"
    "     * Folder '03 - Der Fluch des Drachen' -> series_part: 3, episode_title: 'Der Fluch des Drachen'\n"
    "   - NEVER set episode_title to just a number or code like '08' or 'LB08'. It must be the full text name of the episode.\n\n"
    "4. Album Title (album):\n"
    "   - Format for maximum hardware compatibility: Include the Series Name, zero-padded episode number, and clean episode title:\n"
    "     '{series} {series_part:02d} - {episode_title}'\n"
    "   - Example: 'Larry Brent 08 - Das Grauen von Blackwood Castle'\n\n"
    "5. GENRE & SUBGENRE RULES:\n"
    "   - 'primary_genre' MUST ALWAYS be 'Hörspiel'.\n"
    "   - 'secondary_genre' MUST be selected from ONE of the following allowed categories based on context:\n"
    "     * 'Horror' (Grusel, Dämonen, Monster, Geister)\n"
    "     * 'Krimi' (Kriminalfälle, Polizei, Mordermittlung)\n"
    "     * 'Detektiv' (Jugend-Detektive, Rätsel, Spürnasen)\n"
    "     * 'Science-Fiction' (Weltraum, Zukunft, Zukunfts-Technologie)\n"
    "     * 'Fantasy' (Magie, Mythen, Fabelwesen)\n"
    "     * 'Abenteuer' (Reisen, Schätze, Action, Wildnis)\n"
    "     * 'Jugend' (Jugendhörspiele, Schule, Alltag)\n"
    "     * 'Kinder' (Vorschule, Märchen, Kleinkinder)\n"
    "     * 'Comedy' (Humor, Satire, Klamauk)\n"
    "     * 'Thriller' (Psychothriller, Spionage, Spannung)\n"
    "     * 'Klassiker' (Literaturverfilmung/Adaptionen, historische Stoffe)\n"
    "     If none fits accurately, default to 'Allgemein'.\n"
    "   - 'formatted_genre' MUST combine primary and secondary genre with a semicolon and space for maximum media server & MP3 player compatibility:\n"
    "     'Hörspiel; {secondary_genre}' (e.g., 'Hörspiel; Horror' or 'Hörspiel; Detektiv')\n\n"
    "6. CRITICAL ENCODING & LANGUAGE INSTRUCTIONS:\n"
    "   - The metadata and track titles are in German.\n"
    "   - ALWAYS preserve German umlauts (ä, ö, ü, Ä, Ö, Ü, ß) and special characters directly in UTF-8 format.\n"
    "   - NEVER convert German umlauts into ?, ASCII replacements (ae, oe, ue), or unicode escapes (\\uXXXX).\n"
    "   - '???' in series like 'Die drei ???' is literal punctuation and MUST NOT be used as replacement for letters.\n\n"
    "Strict Output Format:\n"
    "You must return ONLY a single, valid JSON object matching this schema:\n"
    "{\n"
    '  "album_artist": "Larry Brent",\n'
    '  "artist": "Larry Brent",\n'
    '  "series": "Larry Brent",\n'
    '  "series_part": 8,\n'
    '  "episode_title": "Das Grauen von Blackwood Castle",\n'
    '  "album": "Larry Brent 08 - Das Grauen von Blackwood Castle",\n'
    '  "year": 1983,\n'
    '  "primary_genre": "Hörspiel",\n'
    '  "secondary_genre": "Horror",\n'
    '  "formatted_genre": "Hörspiel; Horror",\n'
    '  "tracks": [\n'
    "    {\n"
    '      "original_filename": "01 - Intro.mp3",\n'
    '      "clean_title": "Intro",\n'
    '      "track_number": 1,\n'
    '      "new_filename": "01 - Intro.mp3"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Do not include any explanation, preamble, or markdown formatting (like ```json). Return raw JSON."
)

LLM_SYSTEM_PROMPT = os.getenv("LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)


# Merge settings
MERGE_THRESHOLD = int(os.getenv("MERGE_THRESHOLD", "10"))

# Special headers/body if we detect custom Agent URLs or agent_ model IDs
def get_llm_client_kwargs() -> dict:
    """Returns extra headers and body arguments for compatibility with custom agent endpoints."""
    kwargs = {
        "base_url": LLM_API_BASE_URL,
        "api_key": LLM_API_KEY
    }
    
    extra_headers = {}
    extra_body = {}
    
    # If the URL or model ID looks like a custom Agent API, add agent headers and body
    if "/api/agents/" in LLM_API_BASE_URL.lower() or LLM_MODEL_ID.startswith("agent_"):
        extra_headers = {
            "X-Agent-ID": LLM_MODEL_ID,
            "Agent-Id": LLM_MODEL_ID,
            "X-Agent-Id": LLM_MODEL_ID
        }
        extra_body = {
            "agent_id": LLM_MODEL_ID
        }
            
    return {
        "client_init": kwargs,
        "extra_headers": extra_headers,
        "extra_body": extra_body
    }
