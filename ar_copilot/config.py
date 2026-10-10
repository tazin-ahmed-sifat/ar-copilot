"""Workspace-local configuration; status checks never expose credentials."""
import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'

# gemini-2.5-flash is still listed by the API but returned HTTP 404 for this
# project; gemini-3.8-flash is the model the measured runs used.
DEFAULT_MODEL = 'gemini-3.8-flash'

def gemini_settings():
    # Read on each extraction so a key saved while Streamlit is running is seen.
    # Explicit process environment variables take precedence over .env.
    local = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = (os.getenv('GEMINI_API_KEY') or local.get('GEMINI_API_KEY') or '').strip()
    model = (os.getenv('GEMINI_MODEL') or local.get('GEMINI_MODEL') or DEFAULT_MODEL).strip()
    return key, model

def configuration_status():
    key, model = gemini_settings()
    return {'env_file_exists': ENV_PATH.exists(), 'key_configured': bool(key), 'model': model}
