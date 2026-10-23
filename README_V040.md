# EEG-Agent UI 0.4.0

This is an **optional** interface that requires `eeg-agent-core[agent]>=0.4,<0.5`.
Core can be installed and used without it. Web UI and interactive CLI remain in **one UI project**.

Changes:
- `/edit THREAD_ID {"target_sfreq":200}` allows an explicit parameter modification at a pending approval, followed by a mandatory second approval (`/approve THREAD_ID`).
- Chainlit approvals offer **Approve / Reject / Modify parameters**, with JSON editing and a new approval prompt.
- Batch file-level progress events are rendered in both CLI and Chainlit when running `batch_preprocess`.
- Existing session retrieval commands (`/sessions`, `/use`, `/runs`, `/resume`) and model streams remain intact.

From the directory containing both projects:

```
conda activate eeg_agent
uv pip install -e './EEG-Agent-Core[agent]' -e './EEG-Agent-UI[all]' --python "$CONDA_PREFIX/bin/python"
```

Keep vLLM running in a separate Conda environment. The UI reads `EEG_DATA_ROOT`, `EEG_OUTPUT_ROOT`, `EEG_LLM_MODEL`, and `EEG_LLM_BASE_URL` as before. For data-intensive tasks prefer direct Python API until your real-data QC and scientific numerical validation are complete.
