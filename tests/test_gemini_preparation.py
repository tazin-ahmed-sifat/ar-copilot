"""Credential preparation tests use fake values and make no network calls."""
import json
import subprocess
from pathlib import Path
import pytest
from ar_copilot import config, evaluate as evaluation
from ar_copilot.extract import extract
from ar_copilot.generate import generate
from ar_copilot.core import FIELDS

def test_workspace_dotenv_and_environment_precedence(tmp_path, monkeypatch):
    path = tmp_path/'.env'
    monkeypatch.setattr(config, 'ENV_PATH', path)
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.delenv('GEMINI_MODEL', raising=False)
    path.write_text('GEMINI_API_KEY=FAKE_TEST_VALUE\nGEMINI_MODEL=test-model\n')
    assert config.gemini_settings() == ('FAKE_TEST_VALUE', 'test-model')
    assert 'FAKE_TEST_VALUE' not in json.dumps(config.configuration_status())
    path.write_text('GEMINI_API_KEY=CHANGED_FAKE_VALUE\n')
    assert config.gemini_settings()[0] == 'CHANGED_FAKE_VALUE'
    monkeypatch.setenv('GEMINI_API_KEY','PROCESS_FAKE_VALUE')
    assert config.gemini_settings()[0] == 'PROCESS_FAKE_VALUE'

def test_dotenv_is_ignored_by_git(tmp_path):
    # This workspace need not be a Git repo; validate its real ignore rules
    # inside an isolated temporary repo without initializing the user's repo.
    root = Path(__file__).resolve().parents[1]
    (tmp_path/'.gitignore').write_bytes((root/'.gitignore').read_bytes())
    subprocess.run(['git','init','--quiet',str(tmp_path)], check=True, capture_output=True)
    result = subprocess.run(['git','check-ignore','.env'], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout.strip()=='.env'
    assert subprocess.run(['git','check-ignore','.env.example'], cwd=tmp_path, capture_output=True).returncode == 1

def test_isolated_three_layout_evaluation(tmp_path, monkeypatch):
    data = tmp_path/'data'; rows = generate(data)
    calls = []
    def fake_extract(pdf, mode, fixtures):
        assert mode=='gemini'
        index = next(i for i,row in enumerate(rows) if (data/'invoices'/row['filename']).read_bytes()==pdf)
        calls.append(index)
        return dict(fields={f: rows[index][f] for f in FIELDS}, error=None,
                    error_code=None, seconds=.25, text='mock', mode='gemini', model='mock-only')
    monkeypatch.setattr(evaluation,'extract',fake_extract)
    report = evaluation.evaluate(data,'gemini','per-layout')
    assert calls == [0,1,2]
    assert report['documents']==3 and report['overall_field_accuracy']==1
    assert report['seconds_total']==.75 and report['full_evaluation_ready']
    assert [r['layout'] for r in report['details']] == ['1','2','3']
    assert not (tmp_path/'runtime').exists()

def test_failed_extraction_is_not_perfect_missing_field_match(tmp_path, monkeypatch):
    data=tmp_path/'data'; generate(data)
    monkeypatch.setattr(evaluation,'extract',lambda *args: dict(fields={}, error='mock error',
        seconds=.1, text='', mode='gemini', model='mock-only'))
    report=evaluation.evaluate(data,'gemini','per-layout')
    assert report['overall_field_accuracy']==0 and report['document_accuracy']==0
    assert not report['full_evaluation_ready'] and not report['measured_gemini_accuracy']

def test_provider_error_does_not_expose_exception_message(tmp_path, monkeypatch):
    from google import genai
    folder=tmp_path/'data'; generate(folder)
    monkeypatch.setattr('ar_copilot.extract.gemini_settings',lambda: ('FAKE_VALUE','test-model'))
    class FakeClient:
        def __init__(self, **kwargs):
            raise ValueError('Provider echoed FAKE_VALUE')
    monkeypatch.setattr(genai,'Client',FakeClient)
    result=extract((folder/'invoices/NC-0001.pdf').read_bytes(),'gemini')
    assert result['error'] and 'FAKE_VALUE' not in json.dumps(result)
