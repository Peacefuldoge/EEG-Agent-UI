# EEG-Agent UI · v0.3.0

A **separate, optional** frontend project for [EEG-Agent Core](../EEG-Agent-Core/README.md). It contains **both** a Chainlit Web UI and a terminal REPL with strategy/file commands. It does not copy EEG algorithms, LangGraph strategy graphs, or model weights. The core can be installed and used without this UI.

## Local installation (WSL2 Ubuntu, Conda + uv)

Keep your current Qwen/vLLM in its existing `vllm` Conda environment and start it independently on `http://127.0.0.1:8000/v1` with served model name `qwen3-8b`.

```bash
conda activate eeg_agent
cd /path/to/EEG_Agent_Modular_v0_3
uv pip install -e './EEG-Agent-Core[agent]' -e './EEG-Agent-UI[all]' --python "$CONDA_PREFIX/bin/python"
```

You may instead install just the terminal UI with `[cli]` or just Chainlit with `[web]`. Both share `eeg_agent.EEGSession`. This UI requires **eeg-agent-core 0.3.x**.

## Launch from the UI repository

```bash
cd EEG-Agent-UI
bash scripts/start_chat.sh             # interactive terminal: /agent, /file, /strategy
bash scripts/start_web.sh              # http://127.0.0.1:8002
```

Or from any working directory (when installed):

```bash
eeg-agent-chat --data-root /mnt/d/EEG --output-root ./agent_runs
EEG_DATA_ROOT=/mnt/d/EEG EEG_OUTPUT_ROOT=./agent_runs eeg-agent-web
```

Commands: `/chat`, `/agent`, `/strategy react|plan-execute|rewoo`, `/file /absolute/path`, `/status`, `/clear`, `/exit`.

Choose **Chat** for normal local Qwen chat; choose **Agent** for validated EEG tools. EEG inputs must be under your configured `EEG_DATA_ROOT`, outputs under `EEG_OUTPUT_ROOT`. The upload command copies a single supported EEG file into the configured output root.

## Contract between the two independent projects

```
Browser / terminal
    |  eeg_agent_ui.web_app / eeg_agent_ui.chat_cli
    v
UI -> EEGSession(data_root, output_root, model, base_url, strategy)
           |-- .chat(text)
           |-- .set_file(path)
           |-- .set_strategy(name)
           |-- .run_agent(text, on_node=callback) -> dict
                      v
          Core: LangGraph -> EEGTools -> MNE / SciPy / reports
                      |
                  vLLM API (user-owned)
```

`eeg_agent_ui.compat` checks version compatibility at runtime. Installing both editable sources supports local development; they can be tagged/released independently later. Do not publish the UI package on PyPI before publishing `eeg-agent-core` to the chosen index, unless documenting local installation.

## Features and present limits

The current interfaces show node summaries, run reports, and files; they do not provide per-token output, real-time Chainlit node updates, human approval, full session restart restore, or multi-user authentication. Those are future features; **splitting does not remove or simulate them**. Core SQLite run checkpoint facilities and JSON traces remain available for integration.

## Development checks

```bash
python -m pytest -q tests
python -m eeg_agent_ui.chat_cli --help
```
