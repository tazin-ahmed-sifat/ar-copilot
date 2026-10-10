"""Scan a publication allowlist without printing any secret values."""
import sys
from pathlib import Path

if not __package__:
    # Run as `python scripts/<name>.py`: put the repo root on the path so
    # `ar_copilot` imports the same way it does under `python -m scripts.<name>`.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import io
import json
import re
import subprocess
import zipfile
from dotenv import dotenv_values
from ar_copilot.config import ROOT, gemini_settings

PUBLIC_DIRECTORIES = ['ar_copilot', 'excel', 'views', 'tests', 'scripts', 'docs', 'results', '.vscode', '.streamlit']
PUBLIC_FILES = ['app.py', 'README.md', 'requirements.txt', 'requirements.lock.txt', '.gitignore', '.env.example']

def is_publishable(path: Path) -> bool:
    """Files in an allowed directory, minus caches, local secrets and Office lock files.

    A lock file (~$name.xlsx) exists only while Excel has the workbook open, and Windows
    refuses to let anything else read it.
    """
    return (not path.is_symlink() and '__pycache__' not in path.parts and path.name != 'secrets.toml'
            and not path.name.startswith('~$'))


def _searchable(content: bytes) -> bytes:
    """Raw bytes plus, for zip-based files such as .xlsx, every decompressed member."""
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return content + b''.join(archive.read(name) for name in archive.namelist())


def _leaks(content: bytes, key: str, patterns: list[bytes]) -> bool:
    content = _searchable(content)
    return bool(key and key.encode() in content) or any(re.search(p, content) for p in patterns)


def audit():
    candidates = [ROOT/p for p in PUBLIC_FILES]
    for directory in PUBLIC_DIRECTORIES:
        candidates.extend(path for path in (ROOT/directory).rglob('*')
                          if path.is_file() and is_publishable(path))
    candidates=sorted(set(candidates))
    key,_=gemini_settings()
    private_values = [value for name, value in dotenv_values(ROOT / '.env').items()
                      if name != 'GEMINI_MODEL' and value and len(value) >= 8]
    if key:
        private_values.append(key)
    patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              rb'gh[pousr]_[A-Za-z0-9]{20,}', rb'github_pat_[A-Za-z0-9_]{30,}',
              rb'AIza[A-Za-z0-9_-]{30,}', rb'AKIA[A-Z0-9]{16}']
    findings=[]
    for path in candidates:
        if any(_leaks(path.read_bytes(), value, patterns) for value in private_values or ['']):
            findings.append(path.relative_to(ROOT).as_posix())
    if findings:
        raise SystemExit('Potential credential detected in these files (values withheld): '+', '.join(findings))
    env_example=(ROOT/'.env.example').read_text()
    if any(line.startswith('GEMINI_API_KEY=') and line.partition('=')[2].strip() for line in env_example.splitlines()):
        raise SystemExit('.env.example contains a nonempty credential field')
    staged=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}', 'diff','--cached','--name-only','--diff-filter=ACMRT'],cwd=ROOT,check=True,capture_output=True,text=True).stdout.splitlines()
    allowed={p.relative_to(ROOT).as_posix() for p in candidates}
    if set(staged)-allowed:
        raise SystemExit('Staged files outside publication allowlist: '+', '.join(sorted(set(staged)-allowed)))
    for filename in staged:
        content=subprocess.run(['git','-c',f'safe.directory={ROOT.as_posix()}', 'show',f':{filename}'],
            cwd=ROOT,check=True,capture_output=True).stdout
        if any(_leaks(content, value, patterns) for value in private_values or ['']):
            raise SystemExit('Potential credential found in staged content (value withheld): '+filename)
    print(json.dumps(dict(candidate_files=len(candidates),staged_files=len(staged),credential_findings=0,
                         configured_private_values_compared_without_display=True),indent=2))

if __name__=='__main__':
    audit()
