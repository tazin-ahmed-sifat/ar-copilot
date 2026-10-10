"""Scripts must run both as files (`python scripts/x.py`) and as modules (`python -m scripts.x`)."""
import subprocess
import sys

import pytest

from ar_copilot.config import ROOT

SCRIPTS = ['audit_public_files', 'local_verify', 'publish_results', 'summarize_evaluation']


@pytest.mark.parametrize('name', SCRIPTS)
def test_script_imports_when_run_as_a_file_from_any_directory(name, tmp_path):
    # run_path with a non-main name loads the file exactly as `python scripts/x.py`
    # would, but without executing main(), so nothing is written.
    probe = f"import runpy; runpy.run_path({str(ROOT / 'scripts' / f'{name}.py')!r}, run_name='probe')"
    result = subprocess.run([sys.executable, '-c', probe], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_script_runs_as_a_module():
    result = subprocess.run([sys.executable, '-m', 'scripts.summarize_evaluation', '--help'],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
