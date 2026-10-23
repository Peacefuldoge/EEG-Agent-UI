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
        def __init__(self, *, data_root, output_root, model, base_url, strategy, checkpoint):
            self.strategy = strategy
            self.model_name = model
            self.base_url = base_url
            self.current_file = None
            self.tools = type('Tools', (), {'output_root': tmp_path})()
        def set_strategy(self, x):
            self.strategy = x
            events.append(('strategy', x))
        def set_file(self, path):
            self.current_file = path
            events.append(('file', path))
            return path
        def chat(self, text):
            events.append(('chat', text))
            return 'mock_chat'
        def run_agent(self, text, on_node):
            events.append(('agent', text))
            on_node('inspect_eeg', {'status': 'completed'})
            return {'status': 'completed', 'answer': 'mock_agent', 'manifest': 'agent_run.json'}
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
    assert '→ inspect_eeg' in out
    assert 'mock_agent' in out
