---
title: Bug Triage OpenEnv
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
tags:
  - openenv
---

# Bug Triage OpenEnv

A typed OpenEnv environment for software bug triage. The agent must classify tickets, assign them to the right team, detect duplicates, request missing information, and escalate urgent incidents.

## Why this environment

This is a real workflow, not a toy task. Software teams do bug triage every day, and progress can be measured step by step. The medium and hard tasks use varied, natural-language tickets instead of repeating a single template.

The environment includes:

- Typed `Observation`, `Action`, `Reward`, and `State` models with Pydantic
- Standard OpenEnv methods: `reset()`, `step()`, and `state()`
- Three deterministic tasks: easy, medium, and hard
- Programmatic graders with final task scores strictly in `(0, 1)`
- Dense rewards for partial progress

## Observation and action space

Observation includes:

- Current ticket details
- Queue stats
- Available teams and components
- Steps used and remaining
- Partial score and last action result

Actions supported:

- `classify`
- `assign`
- `mark_duplicate`
- `request_info`
- `defer`
- `close`
- `escalate_incident`
- `next_ticket`

## Tasks

### `bug_triage_easy`

- Difficulty: easy
- 8 tickets
- Mostly clear bug reports with minimal duplicates

### `bug_triage_medium`

- Difficulty: medium
- 15 tickets
- Mixed-quality reports with duplicates and missing information

### `bug_triage_hard`

- Difficulty: hard
- 25 tickets
- Noisy tickets with SLA pressure and escalation trade-offs

## Reward and grading

The reward function gives feedback during the episode, not only at the end.

It rewards:

- Correct severity, priority, and component classification
- Correct team assignment
- Correct duplicate handling
- Correct information requests
- Correct escalation of critical tickets

It penalizes:

- Invalid actions
- Repeated loop behavior
- Missing escalation on critical tickets
- Incorrect close or defer decisions

Each task has deterministic grader logic in `server/graders/`.
For validator compatibility, final task scores are epsilon-clamped to a strict open interval:

- minimum: `> 0.0`
- maximum: `< 1.0`

## Setup

Install dependencies:

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
pip install -r server/requirements.txt
```

macOS/Linux:

```bash
source venv/bin/activate
pip install -r server/requirements.txt
```

Validate:

```bash
openenv validate
```

Configure submission variables (required by `inference.py`):

```bash
API_BASE_URL=https://router.huggingface.co/v1
MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
HF_TOKEN=<your_hf_token>
```

## Run locally

Start the API:

```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

Web UI:

- Open `http://127.0.0.1:7860/` (served from `static/`)

Main endpoints:

- `GET /reset`
- `POST /reset` (accepts empty body and optional JSON body)
- `POST /step`
- `GET /state`
- `GET /tasks`
- `GET /health`

## Baseline inference

Submission runner:

```bash
python inference.py
```

`inference.py` emits strict structured stdout logs in this order only:

- `[START] ...`
- `[STEP] ...` (one line per call to `step()`)
- `[END] ...`

By default, `action=` uses a compact human-readable format for easier scanning.
Set `OPENENV_LOG_ACTION_JSON=1` to emit raw JSON action payloads instead.

Deterministic offline baseline:

```powershell
$env:OPENENV_OFFLINE = "1"
venv\Scripts\python.exe inference.py
```

Offline baseline snapshots are computed from the current shared policy and task fixtures.
Use either of these to inspect live scores instead of relying on stale hardcoded numbers:

- `python inference.py` with `OPENENV_OFFLINE=1`
- `GET /baseline`

Submission check note:

- Ensure every task score is strictly between `0` and `1` (not exactly `0.0` or `1.0`).

## Docker and Hugging Face

Build:

```bash
docker build -t bug-triage-openenv .
```

Run:

```bash
docker run --rm -p 7860:7860 bug-triage-openenv
```

This repo is set up for a Docker-based Hugging Face Space and tagged with `openenv`.
