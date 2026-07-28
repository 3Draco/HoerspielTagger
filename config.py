import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# API Configuration
LLM_API_BASE_URL = os.getenv("LLM_API_BASE_URL", "http://127.0.0.1:1234/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "lm-studio")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "meta-llama-3-8b-instruct")

# Merge settings
MERGE_THRESHOLD = int(os.getenv("MERGE_THRESHOLD", "10"))

# Special headers/body if we detect custom LibreChat/Agent URLs or agent_ model IDs
def get_llm_client_kwargs() -> dict:
    """Returns extra headers and body arguments for compatibility with LibreChat agent endpoints."""
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
