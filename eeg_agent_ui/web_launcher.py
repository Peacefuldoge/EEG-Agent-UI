"""Run the optional Chainlit Web UI from any working directory."""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import sys


def main(argv=None):
    from .compat import check_core
    check_core()
    cli = shutil.which('chainlit')
    if cli is None:
        raise SystemExit('Chainlit not installed; install eeg-agent-ui[web] first.')
    app_file = Path(__file__).with_name('web_app.py')
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        args = ['--host', '127.0.0.1', '--port', '8002']
    return subprocess.call([cli, 'run', str(app_file), *args])


if __name__ == '__main__':
    raise SystemExit(main())
