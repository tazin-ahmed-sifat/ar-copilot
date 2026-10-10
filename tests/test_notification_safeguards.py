"""Run the actual local Office Script and notification-journal tests; never send mail."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_office_script_and_journal_safeguards():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node 24+ required for Office Script type stripping')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, '--test', 'tests/notification_safeguards.mjs'],
                            cwd=root, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
