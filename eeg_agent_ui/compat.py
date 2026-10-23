"""Centralized compatibility boundary between optional UI and EEG-Agent Core.

UI may be upgraded independently as long as the installed core is compatible.
"""
from __future__ import annotations


def check_core():
    try:
        from eeg_agent import __version__ as core_version
        from eeg_agent import EEGSession, STRATEGIES, SUPPORTED_RAW
    except ImportError as exc:
        raise RuntimeError('Missing EEG-Agent Core: install eeg-agent-core[agent] first.') from exc
    major_minor = tuple(int(x) for x in core_version.split('.')[:2])
    if major_minor != (0, 3) or tuple(int(x) for x in core_version.split('.')[:3]) < (0,3,2):
        raise RuntimeError(f'EEG-Agent UI 0.3.x requires EEG-Agent Core >=0.3.2,<0.4; found {core_version}')
    return EEGSession, STRATEGIES, SUPPORTED_RAW


# Lazy bindings are not needed here: core imports no UI or model until used.
EEGSession, STRATEGIES, SUPPORTED_RAW = check_core()
