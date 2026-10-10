"""Gemini settings from the environment or the workspace .env file. The key is never displayed."""
import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'

# gemini-2.5-flash is still listed by the API but returned HTTP 404 for this
# project; gemini-3.8-flash is the model the measured runs used.
DEFAULT_MODEL = 'gemini-3.8-flash'

def gemini_settings() -> tuple[str, str]:
    """Return (key, model). Re-read on every call so a key saved while the app runs is picked up.

    Process environment variables win over .env, so a one-off override needs no file edit.
    """
    local = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    key = (os.getenv('GEMINI_API_KEY') or local.get('GEMINI_API_KEY') or '').strip()
    model = (os.getenv('GEMINI_MODEL') or local.get('GEMINI_MODEL') or DEFAULT_MODEL).strip()
    return key, model

def configuration_status() -> dict:
    key, model = gemini_settings()
    return {'env_file_exists': ENV_PATH.exists(), 'key_configured': bool(key), 'model': model}

def setting(name, default=''):
    local = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return str(os.environ.get(name, local.get(name) or default)).strip()


def local_only():
    return setting('AR_LOCAL_ONLY', '1').lower() not in ('0', 'false', 'no')


def providers():
    return ['ollama', 'demo'] + ([] if local_only() else ['gemini'])


def ollama_settings():
    endpoint = setting('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')
    if endpoint != 'http://127.0.0.1:11434':
        raise ValueError('Ollama endpoint must be http://127.0.0.1:11434')
    model = setting('OLLAMA_MODEL', 'qwen3:8b')
    if model != 'qwen3:8b':
        raise ValueError('Only the installed local qwen3:8b model is supported')
    return endpoint, model
