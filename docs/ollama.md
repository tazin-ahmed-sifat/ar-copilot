# Ollama settings and limits

Extraction uses one model: `qwen3:8b`, served by Ollama at `http://127.0.0.1:11434`. Ollama is
the runtime and Qwen is the model. The client is Python's standard `urllib`, so there is no SDK
to install.

## Setup

```powershell
ollama pull qwen3:8b
ollama list
```

Ollama must be running when you extract (the Windows app starts it in the background). `.env`
is optional:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
```

Those are the only values accepted. [`ar_copilot/config.py`](../ar_copilot/config.py) raises an
error for any other endpoint or model, and the document goes to review with that message. To try
a different model you would have to change `DEFAULT_MODEL` in the code and re-run the
evaluation.

## What a request looks like

[`ar_copilot/ollama.py`](../ar_copilot/ollama.py) does three things for each document:

1. **Size check.** It adds up the UTF-8 byte length of the prompt, schema and PDF text, plus 512
   tokens of headroom and the 768-token output allowance. If that comes to more than 4,096, the
   document is rejected without calling the model. Bytes are a pessimistic stand-in for tokens,
   so some documents that would fit get rejected anyway. Nothing is ever truncated.
2. **Model check.** It calls `/api/show` and refuses the model if Ollama reports it as remote
   (cloud-backed).
3. **Chat.** It sends a `/api/chat` request with `format` set to the JSON schema, `stream: false`,
   `think: false`, and the options `num_ctx 4096`, `num_predict 768`, `temperature 0`, `seed 42`.
   The timeout is 120 seconds.

The response is rejected if generation didn't finish normally (`done_reason` other than `stop`),
if Ollama's reported prompt size leaves no room for the output, or if the JSON fails strict
Pydantic validation. The validation requires all twelve keys, allows no extra keys, and only
accepts strings or null, so a number like `1722.41` instead of `"1722.41"` is rejected.

The HTTP opener has no proxy handler and refuses redirects. The request can only go to the
loopback address.

Each rejection or connection failure is stored with the document as a short message and a
category: `timeout`, `model_unavailable`, `runtime_unavailable` or `invalid_response_or_input`.
The document still appears in the review queue, and the reviewer enters the fields by hand.

## Prompt

The prompt is in [`ar_copilot/extract.py`](../ar_copilot/extract.py). It tells the model to
treat the document as data, copy printed values only, keep dates and amounts as printed strings,
use null for anything missing, and never fix totals or guess a PO number. Keeping instructions in
the system message and the document in the user message makes prompt injection harder. It
doesn't make it impossible, which is one more reason every result is reviewed.

## Network

Only the extraction call is restricted to loopback. Nothing in the app blocks other network use,
and the Microsoft 365 flow (see [microsoft365.md](microsoft365.md)) works separately over the
internet. Once the packages and model are installed, extraction, review and export shouldn't need
internet access, but running fully offline hasn't been tested. Streamlit's usage statistics are
turned off in [`.streamlit/config.toml`](../.streamlit/config.toml). Ollama itself may still check
for updates.

Ollama API references: [chat](https://docs.ollama.com/api/chat),
[structured outputs](https://docs.ollama.com/capabilities/structured-outputs).
