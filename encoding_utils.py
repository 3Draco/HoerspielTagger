import re
from typing import Any, Dict, List, Union

def fix_encoding_corruptions(text: str) -> str:
    """
    Sanitizes and repairs corrupted German text string (replacing replacement characters \\ufffd
    and UTF-8/CP1252 Mojibake like 'Ã¼' -> 'ü', 'Ã¤' -> 'ä', 'Ã¶' -> 'ö', 'ÃŸ' -> 'ß').
    """
    if not text:
        return ""

    # 1. Repair UTF-8 / CP1252 Mojibake (e.g. 'Ã¼' -> 'ü')
    if any(c in text for c in ["Ã", "Â"]):
        try:
            fixed = text.encode("latin1").decode("utf-8")
            text = fixed
        except Exception:
            pass

    # 2. Repair Unicode Replacement Characters (\\ufffd) for German umlauts
    if "\ufffd" in text:
        patterns = [
            (r'vorz\ufffdg', 'vorzüg'),
            (r'f\ufffdnf', 'fünf'),
            (r'zur\ufffdck', 'zurück'),
            (r'f\ufffdr', 'für'),
            (r'gr\ufffd\ufffd', 'groß'),
            (r'\ufffdber', 'über'),
            (r'sp\ufffdter', 'später'),
            (r'r\ufffdtsel', 'rätsel'),
            (r'm\ufffdg', 'mög'),
            (r'h\ufffdr', 'hör'),
            (r'b\ufffdd', 'böd'),
            (r'k\ufffdnn', 'könn'),
            (r'gl\ufffdck', 'glück'),
            (r'br\ufffdck', 'brück'),
            (r'\ufffd', 'ü'),  # Fallback single replacement character
        ]
        for p, r in patterns:
            text = re.sub(p, r, text, flags=re.IGNORECASE)

    return text

def sanitize_metadata_obj(data: Union[Dict[str, Any], List[Any], str]) -> Union[Dict[str, Any], List[Any], str]:
    """Recursively applies fix_encoding_corruptions to all string values in data dict or list."""
    if isinstance(data, str):
        return fix_encoding_corruptions(data)
    elif isinstance(data, dict):
        return {k: sanitize_metadata_obj(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_metadata_obj(item) for item in data]
    return data
