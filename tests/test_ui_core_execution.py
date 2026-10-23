"""Offline cross-project tests: no vLLM server or Chainlit installation required."""
from __future__ import annotations
import builtins
import sys
from pathlib import Path

from eeg_agent_ui import chat_cli
from eeg_agent import EEGSession


def test_existing_llm_injection_works(tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    class ExternalChat:
        def invoke(self, msgs):
            return type('Answer', (), {'content': 'Hello from existing environment'})()
    model = ExternalChat()
    s = EEGSession(data_root=data, output_root=tmp_path/'out', llm=model, checkpoint=False)
    assert s.llm.chat is model
    assert s.data_root == data.resolve()
    assert s.output_root == (tmp_path/'out').resolve()


def test_terminal_ui_routes_to_core_session(monkeypatch, tmp_path, capsys):
    # Exercise UI CLI commands against fake public Core session API, not a second agent.
    events = []
    class FakeSession:
        def __init__(self, *, data_root, output_root, model, base_url, strategy, checkpoint, session_id=None):
            self.strategy = strategy
            self.model_name = model
            self.base_url = base_url
            self.current_file = None
            self.output_root = tmp_path
            self.session_id = session_id or 'offline_mock'
            self.tools = type('Tools', (), {'output_root': tmp_path})()
        def set_strategy(self, x):
            self.strategy = x
            events.append(('strategy', x))
        def set_file(self, path):
            self.current_file = path
            events.append(('file', path))
            return path
        def stream_chat(self, text):
            events.append(('chat', text))
            yield {'type':'token','text':'mock_chat'}
            yield {'type':'completed','answer':'mock_chat'}
        def stream_agent(self, text):
            events.append(('agent', text))
            yield {'type':'run_started','thread_id':'thread_mock'}
            yield {'type':'node_started','node':'inspect_eeg'}
            yield {'type':'node_completed','node':'inspect_eeg','status':'completed'}
            yield {'type':'run_finished','record':{'status':'completed','answer':'mock_agent','manifest':'agent_run.json','thread_id':'thread_mock'}}
        def clear(self):
            events.append(('clear', None))
    monkeypatch.setattr(chat_cli, 'EEGSession', FakeSession)
    # Prompt toolkit is optional; force fallback input() to emulate non-interactive typing.
    monkeypatch.setitem(sys.modules, 'prompt_toolkit', None)
    monkeypatch.setitem(sys.modules, 'rich', None)
    inputs = iter(['/strategy rewoo', '/file /tmp/test.npz', '/agent', 'inspect EEG', '/exit'])
    monkeypatch.setattr(builtins, 'input', lambda prompt='': next(inputs))
    chat_cli.main(['--data-root', str(tmp_path), '--output-root', str(tmp_path/'out')])
    out = capsys.readouterr().out
    assert ('strategy', 'rewoo') in events
    assert ('file', '/tmp/test.npz') in events
    assert ('agent', 'inspect EEG') in events
    assert 'inspect_eeg' in out
    assert 'mock_agent' in out

def test_batch_ui_reports_pending_approval(monkeypatch,tmp_path,capsys):
    import pytest
    from eeg_agent_ui import batch_cli
    class DummySession:
        def __init__(self,**kwargs):self.session_id='s1'
        def set_strategy(self,value):pass
        def set_file(self,value):pass
        def stream_agent(self,text):
            yield {'type':'run_finished','record':{'status':'awaiting_approval','thread_id':'t1',
                    'answer':'','pending':[{'tool':'preprocess_eeg'}],'manifest':'manifest.json'}}
    monkeypatch.setattr(batch_cli,'EEGSession',DummySession)
    with pytest.raises(SystemExit) as e:
        batch_cli.main(['--data-root',str(tmp_path), '--input',str(tmp_path/'file.edf'), '--task','test'])
    assert e.value.code==2
    output=capsys.readouterr().out
    assert 'awaiting_approval' in output and '"thread_id": "t1"' in output
