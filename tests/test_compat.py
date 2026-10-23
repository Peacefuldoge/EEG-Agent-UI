"""Tests for the independent UI->core contract (no browser needed)."""
from pathlib import Path
import importlib
import inspect
import ast
from eeg_agent_ui.compat import EEGSession, STRATEGIES, SUPPORTED_RAW, check_core


def test_matching_core_contract():
    assert check_core()[0] is EEGSession
    assert set(STRATEGIES) == {'react','plan-execute','rewoo'}
    assert '.edf' in SUPPORTED_RAW
    assert {'data_root', 'output_root', 'model', 'base_url'} <= set(inspect.signature(EEGSession).parameters)


def test_ui_does_not_own_eeg_or_agent_implementations():
    package = Path(importlib.import_module('eeg_agent_ui').__file__).parent
    assert not (package/'tools.py').exists()
    assert not (package/'strategies.py').exists()
    assert not (package/'model.py').exists()
    assert (package/'web_app.py').exists()
    assert (package/'chat_cli.py').exists()


def test_web_and_cli_parse_without_optional_ui_imports():
    package = Path(importlib.import_module('eeg_agent_ui').__file__).parent
    for name in ('chat_cli.py','web_app.py','web_launcher.py'):
        ast.parse((package/name).read_text(encoding='utf-8'))
