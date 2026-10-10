"""Mocked Ollama evaluation and ignore rules; no inference calls."""
import json
import subprocess
from pathlib import Path
from ar_copilot import evaluate as evaluation
from ar_copilot.generate import generate
from ar_copilot.core import FIELDS

def test_dotenv_is_ignored_by_git(tmp_path):
    # Check the real ignore rules in a throwaway repository, so the test works
    # in an exported copy of the project that has no .git directory.
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
        assert mode=='ollama'
        index = next(i for i,row in enumerate(rows) if (data/'invoices'/row['filename']).read_bytes()==pdf)
        calls.append(index)
        return dict(fields={f: rows[index][f] for f in FIELDS}, error=None,
                    error_code=None, seconds=.25, text='mock', mode='ollama', model='mock-only')
    monkeypatch.setattr(evaluation,'extract',fake_extract)
    report = evaluation.evaluate(data,'ollama','per-layout')
    assert calls == [0,1,2]
    assert report['documents']==3 and report['overall_field_accuracy']==1
    assert report['seconds_total']==.75 and report['full_evaluation_ready']
    assert [r['layout'] for r in report['details']] == ['1','2','3']
    assert not (tmp_path/'runtime').exists()

def test_failed_extraction_is_not_perfect_missing_field_match(tmp_path, monkeypatch):
    data=tmp_path/'data'; generate(data)
    monkeypatch.setattr(evaluation,'extract',lambda *args: dict(fields={}, error='mock error',
        seconds=.1, text='', mode='ollama', model='mock-only'))
    report=evaluation.evaluate(data,'ollama','per-layout')
    assert report['overall_field_accuracy']==0 and report['document_accuracy']==0
    assert not report['full_evaluation_ready'] and not report['measured_ollama_accuracy']

