import urllib.request
import urllib.parse
import re
from typing import List

class WebSearcher:
    """Performs lightweight web pre-searches to enrich LLM prompt context for audio dramas."""

    @staticmethod
    def search(query: str, max_results: int = 4) -> List[str]:
        if not query or not query.strip():
            return []

        clean_q = query.strip()
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(clean_q)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
                clean_snippets = []
                for s in snippets[:max_results + 2]:
                    text = re.sub(r'<[^>]+>', '', s).strip()
                    # Filter out generic promotional / cookie snippets
                    if len(text) > 25 and not any(ignore in text.lower() for ignore in ["höre was du willst", "datenschutz", "cookie"]):
                        clean_snippets.append(text)
                    if len(clean_snippets) >= max_results:
                        break
                return clean_snippets
        except Exception as e:
            print(f"[WebSearcher Info] Pre-search notice: {e}")
            return []
