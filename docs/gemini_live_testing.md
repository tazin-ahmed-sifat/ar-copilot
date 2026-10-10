# Live Gemini testing

Status: full 40-document run executed on 10 October 2026 with `gemini-3.8-flash`: four successful extractions, 36 failures (34 HTTP 429, two HTTP 503), 10% overall field/document accuracy including failures. See the measured full results in [README](../README.md). Review data was unchanged. The earlier three-layout smoke test passed; it does not establish full-corpus performance. Key setup instructions below remain for future configuration.

## Create and save the key locally

1. Open [Google AI Studio API Keys](https://aistudio.google.com/api-keys), sign in, and choose **Create API key**. Select/create a Google Cloud project for this prototype. If your existing project is not listed, import it through Dashboard → Projects → Import projects. Organization-managed projects may require administrator permissions.
2. Name the key for AR Copilot. Current AI Studio keys are authorization keys restricted to the Gemini API by default. If you use an existing standard key marked Unrestricted, use **Add restrictions → Restrict to Gemini API only**. See [Google's current key guide](https://ai.google.dev/gemini-api/docs/api-key). Check project quota and billing before running evaluation; the full evaluation makes 40 requests. No automatic quota purchase or billing change is performed here.
3. In VS Code's Explorer, open the `.env` file in the workspace root. If it does not exist, copy `.env.example` to `.env`; it contains an empty `GEMINI_API_KEY=` and `GEMINI_MODEL=gemini-3.8-flash`. Paste the key **only into that local file**, after `GEMINI_API_KEY=`, and save. Do not paste it into chat, a terminal command, screenshots or a tracked file. Keep `.env.example` empty. Do not use `Get-Content .env` to check it. Keep the file out of shared/synced folders and backups that others can access; this is a plaintext local development secret, not an encrypted secret store.
4. Optionally limit file access from PowerShell in the workspace:

```powershell
$localIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls .env /inheritance:r /grant:r "${localIdentity}:(F)"
```

This removes inherited permissions and grants your account access. Review explicit grants with `icacls .env`; it displays permissions, not content. ACLs do not encrypt the key or override administrators. Do not share the file.

5. Check configuration without displaying the key:

```
python -m ar_copilot.evaluate --check-config
```

Expect `key_configured: true`. The check prints only presence and the model, never the credential. Process `GEMINI_API_KEY`/`GEMINI_MODEL` variables take precedence over `.env`; stale process variables must be cleared locally if you intend to use the file. `GOOGLE_API_KEY` is deliberately not used by this app, because the client receives the configured Gemini key explicitly. The app reads this exact workspace file on each Gemini extraction, so saving the key does not require regenerating documents or clearing the database.

`.gitignore` includes `.env`, verified with Git. Git ignores prevent accidental additions, not force-adds or disclosure outside Git. Run `git check-ignore .env` before committing. Never force-add `.env`.

## Three-document smoke test

After saving, tell the assistant **“The key is saved locally”** without including the key. The authorized next action is:

```
python -m ar_copilot.evaluate --mode gemini --sample per-layout
```

This reads NC-0001, NC-0002 and NC-0003 (layouts 1, 2 and 3). It sends their extracted text to Gemini, not the reference answers, and compares the actual structured fields afterward. There is no offline fallback. The model is configurable; account access to the default model must be verified by this call.

The evaluator has no Store dependency and never opens SQLite for writing. A read-only before/after file fingerprint checks `runtime/ar.sqlite`; avoid simultaneous review changes during the run so this check is meaningful. Each run gets a unique `reports/gemini/per-layout_<UTC-run-id>.json`, including actual output fields, printed truth, field mismatches, extraction errors/HTTP status when available, field/document accuracy, validation flags, per-document elapsed seconds and total/mean elapsed seconds. Elapsed time includes text extraction, client setup, network and JSON parsing, not just model latency. Missing keys stop before any request/report. Exceptions are sanitized so provider messages cannot echo secrets.

Smoke-test success means all three requests succeed, every printed field matches, and independent validation passes. Three clean documents do not test intentional anomaly detection; that requires the full corpus. Extraction failures count as failed matches and review flags. Review flags caused by API errors are distinct from evidence of accounting anomaly detection; read the per-document error and validation details.

## Full evaluation, prepared after success

The successful smoke-test report sets `full_evaluation_ready: true` and prints:

```
python -m ar_copilot.evaluate --mode gemini --sample full
```

This is 40 sequential requests with a 60-second per-request timeout. There is no automatic retry or rate-limit bypass. Quota/model/authentication/network errors are recorded and reported; no accuracy is invented. Report files are unique under `reports/gemini/`. Offline CLI runs go to `reports/demo/`; historical `reports/evaluation_demo.json` remains explicitly labelled fixtures. Never aggregate those results into Gemini accuracy. Full evaluation is prepared, not automatically launched by the smoke test.
