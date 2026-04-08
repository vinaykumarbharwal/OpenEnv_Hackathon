---
title: Bug Triage OpenEnv
emoji: "🐞"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
tags:
  - openenv
---

# Bug Triage OpenEnv

Bug Triage OpenEnv is a real-world OpenEnv environment for software issue triage. The agent plays the role of a triage engineer who must classify incoming bug reports, route them to the right team, detect duplicates, request missing information, and escalate urgent incidents under limited time.

This repo is designed for the Meta OpenEnv Hackathon requirements:

- Real workflow, not a toy task
- Fully typed OpenEnv interface with `reset()`, `step()`, and `state()`
- Three deterministic tasks with increasing difficulty
- Dense reward feedback across the episode
- Containerized deployment for Hugging Face Spaces

## Motivation

Bug triage is a common operational workflow in real engineering organizations. Success depends on a sequence of decisions, not a single final answer:

- Correct severity and priority assignment
- Correct component and owner routing
- Detecting duplicates instead of doing redundant work
- Asking for missing logs or repro steps when evidence is weak
- Escalating genuinely urgent incidents quickly

That makes it a strong fit for OpenEnv: the agent gets structured observations, takes typed actions, receives partial reward, and is graded deterministically at the end.

## OpenEnv Interface

The environment entrypoint is `openenv_bug_triage.env:BugTriageEnv`, declared in `openenv.yaml`.

### Observation space

```python
class ObservationModel(BaseModel):
    current_ticket: CurrentTicketModel | None
    queue_stats: QueueStatsModel
    last_action_result: str | None
    available_teams: list[str]
    available_components: list[str]
    steps_used: int
    steps_remaining: int
    partial_score: float | None
```

`current_ticket` includes ticket metadata such as:

- `ticket_id`, `title`, `description`
- `reporter_type`, `service`, `customer_tier`
- `component_candidates`
- `repro_steps_present`, `logs_present`
- `attachments_count`, `suspected_duplicate_ids`

### Action space

```python
class ActionModel(BaseModel):
    action_type: Literal[
        "classify",
        "assign",
        "mark_duplicate",
        "request_info",
        "defer",
        "close",
        "escalate_incident",
        "next_ticket",
    ]
```

Supported action payloads:

- `classify`: set `severity`, `priority`, and `component`
- `assign`: route the ticket to a team
- `mark_duplicate`: point to a canonical ticket id
- `request_info`: ask for `repro_steps`, `logs`, or `both`
- `defer`: backlog a low-value ticket
- `close`: close with a structured reason
- `escalate_incident`: flag sev0/sev1 incidents
- `next_ticket`: move to the next ticket in queue

The action model is strict: it rejects mismatched payloads and illegal references.

### Reward space

```python
class RewardModel(BaseModel):
    step_reward: float
    cumulative_reward: float
    reward_breakdown: dict[str, float]
```

The reward is dense and incremental. It gives credit during the trajectory for:

- Correct severity, priority, and component classification
- Correct team assignment
- Correct duplicate handling
- Correct information requests
- Correct escalation on critical incidents

It also penalizes undesirable behavior:

- Invalid actions
- Looping or repeated no-op behavior
- Missing escalation on critical tickets
- Incorrect close/defer decisions on tickets that still need information

The environment API follows the required methods:

- `reset(task_id=None, seed=None) -> ObservationModel`
- `step(action) -> tuple[ObservationModel, RewardModel, bool, dict]`
- `state() -> StateModel`

## Tasks

The environment includes three deterministic task fixtures in `openenv_bug_triage/data/tasks/`.

### `bug_triage_easy`

- Difficulty: easy
- Size: 8 tickets
- Scenario: mostly clear reports, minimal duplicates, obvious routing signals
- Objective: handle basic classification, routing, and the occasional duplicate cleanly

### `bug_triage_medium`

- Difficulty: medium
- Size: 15 tickets
- Scenario: noisier reports, more duplicates, and missing repro details
- Objective: balance classification quality with duplicate detection and correct `request_info` usage

### `bug_triage_hard`

- Difficulty: hard
- Size: 25 tickets
- Scenario: ambiguous signals, SLA pressure, more urgent incidents, and stricter escalation expectations
- Objective: preserve critical-ticket handling quality while still routing the broader queue well

## Grading

Each task has a deterministic programmatic grader in `openenv_bug_triage/grader.py`. Scores are always in `[0.0, 1.0]`.

Task-specific grading emphasis:

- Easy: severity, priority, component, team, duplicates, and efficiency
- Medium: classification quality, duplicate F1-like handling, info-request accuracy, and efficiency
- Hard: critical severity accuracy, SLA handling, escalation quality, routing, and policy quality

The graders are deterministic and reproducible because task fixtures are static and ticket ordering is seeded.

## Local setup

### Python

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Validate the environment

```bash
openenv validate
```

If the `openenv` executable is not on your path, the helper script also works:

```bash
python precheck.py --skip-space
```

## Running the environment

### Local API server

```bash
uvicorn server.app:app --host 0.0.0.0 --port 7860
```

Endpoints:

- `GET /reset`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET /tasks`
- `GET /health`

### Programmatic usage

```python
from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.models import ActionModel, ClassifyAction

env = BugTriageEnv()
obs = env.reset(task_id="bug_triage_easy", seed=42)

action = ActionModel(
    action_type="classify",
    classify=ClassifyAction(
        severity="sev2",
        priority="p2",
        component="api-gateway",
    ),
)

obs, reward, done, info = env.step(action)
state = env.state()
```

## Baseline inference

There are two inference paths in this repo:

- `inference.py`: submission-style runner with structured `[START]`, `[STEP]`, and `[END]` logs
- `scripts/baseline_inference.py`: deterministic baseline runner that saves aggregate scores

The baseline runner uses the OpenAI Python client and reads credentials from `HF_TOKEN` by default. `OPENAI_API_KEY` is accepted as a fallback for direct OpenAI endpoints.

Example live run:

```powershell
$env:API_BASE_URL = "https://router.huggingface.co/v1"
$env:MODEL_NAME = "Qwen/Qwen2.5-72B-Instruct"
$env:HF_TOKEN = "<your_token>"
venv\Scripts\python.exe scripts\baseline_inference.py --seed 42
```

Example offline deterministic run:

```powershell
$env:OPENENV_OFFLINE = "1"
venv\Scripts\python.exe scripts\baseline_inference.py --offline --seed 42
```

The offline fallback policy is deterministic and produces the baseline artifact at `artifacts/baseline_scores.json`.

### Baseline scores

The current deterministic offline baseline with `seed=42` produces:

| Task | Score |
| --- | ---: |
| `bug_triage_easy` | `0.9920` |
| `bug_triage_medium` | `0.6715` |
| `bug_triage_hard` | `0.6460` |
| Mean | `0.7698` |

## Docker

Build the container:

```bash
docker build -t bug-triage-openenv .
```

Run the container:

```bash
docker run --rm -p 7860:7860 bug-triage-openenv
```

There is also a `server/Dockerfile` for a Space-style layout:

```bash
docker build -f server/Dockerfile -t bug-triage-openenv .
docker run --rm -p 7860:7860 bug-triage-openenv
```

## Hugging Face Spaces

This repo is designed to deploy as a Docker Space.

Checklist:

- Use the repo root `Dockerfile`
- Expose port `7860`
- Keep `openenv.yaml` at the repo root
- Tag the Space with `openenv`
- Verify `GET /reset` and `GET /health` after deployment

The README front matter already includes the `openenv` tag for Space metadata.

## Project structure

```text
openenv_bug_triage/
  app.py
  env.py
  grader.py
  models.py
  reward.py
  tasks.py
  data/tasks/
server/
  app.py
  environment.py
scripts/
  baseline_inference.py
tests/
  test_app_ui.py
  test_determinism.py
  test_env_api.py
  test_graders.py
Dockerfile
openenv.yaml
precheck.py
inference.py
```

## Verification

The repo includes:

- Unit tests for environment API, determinism, graders, and UI asset routing
- `openenv validate` support
- Docker packaging
- A precheck script for submission readiness
