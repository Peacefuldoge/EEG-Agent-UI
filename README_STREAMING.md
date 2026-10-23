# EEG-Agent UI v0.3.2 — Live CLI + Chainlit

The UI is a separate optional project. It depends on `eeg-agent-core[agent]>=0.3.2,<0.4` and has **no own copy** of MNE processing, LangGraph strategy graphs or Qwen weights.

## Install into an Agent environment

```bash
conda activate eeg_agent
uv pip install -e './EEG-Agent-Core[agent]' -e './EEG-Agent-UI[all]' \
  --python "$CONDA_PREFIX/bin/python"
```

Do not install this into the running `vllm` Conda environment. Start vLLM from your existing `vllm` environment first; test `curl http://127.0.0.1:8000/v1/models`.

## Terminal UI

```bash
eeg-agent-chat --data-root /mnt/d/EEG --output-root ./agent_runs --strategy react
```

Commands:

- `/file /mnt/d/EEG/subject01.edf`: select a recording
- `/chat`, `/agent`: chat/analysis modes
- `/strategy plan-execute`, `/strategy react`, `/strategy rewoo`: change next task strategy
- `/sessions`: list stored sessions; `/use SESSION_ID`: restore session after restart
- `/history`: show saved conversation; `/runs`: list stored task threads
- `/approve THREAD_ID` and `/reject THREAD_ID`: resolve an EEG operation approval
- `/resume THREAD_ID`: resume a non-HITL interrupted task (or display error if approval is required)
- `/clear`, `/status`, `/exit`

To reopen a particular conversation immediately:

```bash
eeg-agent-chat --data-root /mnt/d/EEG --output-root ./agent_runs --session-id YOUR_ID
```

## Web UI

```bash
export EEG_DATA_ROOT=/mnt/d/EEG
export EEG_OUTPUT_ROOT=$PWD/agent_runs
eeg-agent-web
```

Visit `http://127.0.0.1:8002`. The UI streams generated answer tokens, creates live Step records when LangGraph nodes start and update, and prompts for approval before gated EEG operations.

You can reload a saved Core session via `/sessions`, then `/use SESSION_ID`. `/history` displays saved messages; `/runs` and `/resume THREAD_ID` display/reopen pending tasks. **This is Core-managed history restoration, not Chainlit's own multi-user conversation data layer.**

## Warnings

- This client targets a trusted local workstation. For public hosting add user authentication and isolate Core data roots/session databases per user.
- If a browser tab closes during approval, the graph stays checkpointed in `awaiting_approval` and can be resumed later.
- The Web UI uses a small worker thread to consume the synchronous Core event generator; it does not install or host vLLM itself.
- The `tool_progress` events report tool start/finish; per-subject ICA/file progress requires further instrumentation in scientific tools.
- Files and sessions stored in SQLite may include identifiable local paths; use appropriate privacy controls for participant data.

## Non-interactive command / automation

```bash
eeg-agent-run \
  --data-root /mnt/d/EEG --output-root ./agent_runs \
  --input /mnt/d/EEG/subject01.edf \
  --task 'Inspect and preprocess this recording' \
  --strategy plan-execute
```

Exit code 2 indicates the run is **awaiting human approval**; note the `session_id` and `thread_id` in JSON, then resume explicitly:

```bash
eeg-agent-run --data-root /mnt/d/EEG --output-root ./agent_runs \
  --session-id SESSION_ID --thread-id THREAD_ID --approve
```

For rejected requests use `--reject`. The batch CLI now uses the same Core session and checkpoint APIs; it does not bypass HITL. `--no-checkpoint` explicitly disables the default approval gate and durable task state, and is not recommended for scientific workflows.
