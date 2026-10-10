"""Workspace settings for the sole real LLM: loopback Ollama."""
import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'
DEFAULT_MODEL = 'qwen3:8b'
OLLAMA_ENDPOINT = 'http://127.0.0.1:11434'


def setting(name, default=''):
    local = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
    return str(os.environ.get(name, local.get(name) or default)).strip()


def ollama_settings():
    endpoint = setting('OLLAMA_BASE_URL', OLLAMA_ENDPOINT)
    if endpoint != OLLAMA_ENDPOINT:
        raise ValueError('Ollama endpoint must be http://127.0.0.1:11434')
    model = setting('OLLAMA_MODEL', DEFAULT_MODEL)
    if model != DEFAULT_MODEL:
        raise ValueError('Only the installed local qwen3:8b model is supported')
    return endpoint, model
