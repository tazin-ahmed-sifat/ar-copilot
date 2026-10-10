"""Fixed loopback HTTP transport: no proxies, redirects, downloads or cloud models."""
import json
import urllib.request
from .config import ollama_settings

OPTIONS = {'num_ctx': 4096, 'num_predict': 768, 'temperature': 0, 'seed': 42}
TIMEOUT = 120

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Ollama redirects are disabled')

def request(path, payload=None):
    endpoint, _ = ollama_settings()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(endpoint + path, data=data, headers={'Content-Type': 'application/json'})
    with opener.open(req, timeout=TIMEOUT) as response:
        return json.load(response)

def extract_text(text, schema, validator, prompt):
    _, model = ollama_settings()
    system = prompt + 'Return JSON matching this schema: ' + json.dumps(schema, separators=(',', ':'))
    # UTF-8 byte count is a conservative upper bound for Qwen byte-level tokens.
    # Reserve 512 tokens for chat template/schema grammar overhead plus output.
    upper = len((system + text).encode('utf-8')) + 512
    if upper + OPTIONS['num_predict'] > OPTIONS['num_ctx']:
        raise ValueError('Invoice exceeds conservative 4096-token context budget; manual review required. No text was truncated.')
    info = request('/api/show', {'model': model})
    if info.get('remote_model') or info.get('remote_host'):
        raise ValueError('Cloud-backed Ollama models are disabled')
    response = request('/api/chat', {'model': model, 'stream': False, 'think': False,
        'format': schema, 'keep_alive': '5m', 'options': OPTIONS,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': text}]})
    if response.get('done') is not True or response.get('done_reason') != 'stop':
        raise ValueError('Ollama output incomplete or output limit reached; manual review required')
    if response.get('prompt_eval_count', 0) + OPTIONS['num_predict'] > OPTIONS['num_ctx']:
        raise ValueError('Ollama reported an unsafe context budget; manual review required')
    try:
        fields = validator.model_validate_json(response['message']['content'], strict=True).model_dump()
    except Exception as exc:
        exc.local_metadata = {'raw_output': response.get('message', {}).get('content', '')}
        raise
    stats = {k: response.get(k) for k in ('prompt_eval_count', 'eval_count', 'total_duration', 'load_duration')}
    return fields, {'model_settings': dict(OPTIONS, think=False, timeout_seconds=TIMEOUT),
                    'runtime': stats, 'raw_output': response['message']['content']}
