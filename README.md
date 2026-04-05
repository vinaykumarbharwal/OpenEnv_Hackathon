
# Bug Triage OpenEnv

A real-world simulation environment for software bug triage workflows, implementing the OpenEnv specification.

## Overview

This environment simulates a realistic bug triage workflow where an AI agent acts as a triage engineer responsible for:

- Assigning severity and priority to incoming bug reports
- Identifying duplicate tickets
- Routing bugs to the correct team/component
- Requesting missing information when needed
- Deciding whether to close/defer/escalate tickets

## Why This Is Real-World

Bug triage is a common operational workflow in software engineering teams with concrete measurable outcomes:
- **SLA Compliance**: Critical bugs must be triaged within time windows
- **Issue Resolution Speed**: Proper classification accelerates fixes
- **Triage Correctness**: Accurate routing reduces handoff delays and rework

## Environment API

### Observation Space

```python
class ObservationModel(BaseModel):
    current_ticket: Optional[CurrentTicketModel]  # Focused ticket details
    queue_stats: QueueStatsModel                   # Remaining, urgent, SLA-at-risk counts
    last_action_result: Optional[str]              # Feedback from previous action
    available_teams: list[str]                     # Valid team assignments
    available_components: list[str]                # Valid component labels
    steps_used: int
    steps_remaining: int
    partial_score: Optional[float]                 # Intermediate score (optional)
```

**Ticket Details**:
- `ticket_id`, `title`, `description`
- `reporter_type`: `"user"`, `"qa"`, or `"monitoring"`
- `service`, `component_candidates`
- `customer_tier`: `"free"`, `"pro"`, or `"enterprise"`
- `repro_steps_present`, `logs_present`, `attachments_count`
- `suspected_duplicate_ids`

### Action Space

```python
class ActionModel(BaseModel):
    action_type: Literal[
        "classify",           # Set severity + priority + component
        "assign",             # Set owner team
        "mark_duplicate",     # Link to canonical ticket
        "request_info",       # Ask for missing repro/logs
        "defer",              # Move to backlog
        "close",              # Close with reason
        "escalate_incident",  # Escalate urgent production impact
        "next_ticket"         # Move focus to next ticket
    ]
    # Payload fields (one must match action_type)
    classify: Optional[ClassifyAction]
    assign: Optional[AssignAction]
    # ... etc
```

**Action Validation**:
- Invalid field combinations are rejected with penalty
- References to unknown ticket IDs are rejected
- Destructive actions (`close`, `defer`) penalized if inconsistent with ground truth

### Reward Function

Rewards are in range `[0.0, 1.0]` per step, with a base reward of 0.50 for any valid action. Final episode score is normalized to `[0.0, 1.0]`.

**Dense Progress Signals** (bonuses added to base):
- `+0.20`: Correct severity classification
- `+0.15`: Correct priority classification
- `+0.15`: Correct component assignment
- `+0.10`: Correct team assignment
- `+0.15`: Correct duplicate linking
- `+0.10`: Correct request for more info
- `+0.15`: Correct escalation for sev0/sev1 incidents

**Negative Signals** (penalties subtracted from base):
- `-0.20`: Incorrect close/defer on valid bug
- `-0.15`: Missed critical escalation
- `-0.30`: Invalid action schema
- `-0.10`: Repeated no-op / loop behavior
- `-0.05`: Unnecessary ticket switches

**Terminal Bonuses/Penalties**:
- `+0.10`: All critical tickets triaged within budget
- `-0.10`: Step budget exhausted with high-severity tickets untriaged

## Tasks

### Task A - Easy (`bug_triage_easy`)
- **Scenario**: 8 tickets, mostly clear reports, minimal duplicates, obvious component mapping
- **Grader**: Weighted accuracy on severity/priority/component/team, no more than 1 major mistake
- **Threshold**: â‰¥ 0.75

### Task B - Medium (`bug_triage_medium`)
- **Scenario**: 15 tickets, mixed-quality reports, several duplicates, some missing repro details, limited step budget
- **Grader**: Label correctness + duplicate F1 + correct use of `request_info` + penalties for loops/destructive actions
- **Threshold**: â‰¥ 0.75

### Task C - Hard (`bug_triage_hard`)
- **Scenario**: 25 tickets, noisy/ambiguous text, conflicting signals, strict SLA pressure for enterprise + high-severity tickets, capacity trade-offs
- **Grader**: Strict weighting on sev0/sev1 correctness, SLA-risk handling, escalation accuracy, global policy quality
- **Threshold**: â‰¥ 0.75

## Installation

### Local Setup

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd openenv-bug-triage
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Validate environment**:
   ```bash
   openenv validate
   ```

### Docker Setup

1. **Build the image**:
   ```bash
   docker build -t bug-triage-openenv .
   ```

2. **Run the container**:
   ```bash
   docker run --rm -p 7860:7860 bug-triage-openenv
   ```

## Usage

### Submission Inference (Mandatory)

For submission, use the root script `inference.py` (not `scripts/baseline_inference.py`).
It uses the OpenAI client with these required environment variables:

- `API_BASE_URL` (for Groq: `https://api.groq.com/openai/v1`)
- `MODEL_NAME` (for example `llama-3.3-70b-versatile`)
- `HF_TOKEN` (set this to your Groq API key)

Example:

```bash
# Linux/macOS
export API_BASE_URL="https://api.groq.com/openai/v1"
export MODEL_NAME="llama-3.3-70b-versatile"
export HF_TOKEN="<your-groq-key>"
python inference.py
```

```powershell
# Windows PowerShell
$env:API_BASE_URL = "https://api.groq.com/openai/v1"
$env:MODEL_NAME = "llama-3.3-70b-versatile"
$env:HF_TOKEN = "<your-groq-key>"
python .\inference.py
```

`inference.py` emits structured stdout lines in the required format:

- `[START] task=<task_name> env=<benchmark> model=<model_name>`
- `[STEP] step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>`
- `[END] success=<true|false> steps=<n> rewards=<r1,r2,...,rn>`


### Dark Mode Frontend

The app now ships with a dark-mode web console for interactive triage testing.

- Local: run `uvicorn openenv_bug_triage.app:app --host 0.0.0.0 --port 7860`
- Open in browser: `http://localhost:7860/`
- Uses API endpoints: `GET/POST /reset`, `POST /step`, `GET /state`
### Running Baseline Inference

The baseline script runs all three tasks using an OpenAI-compatible API.
It supports Groq (default) and OpenAI, loading credentials from `.env`.

```bash
# 1) Create your env file (one-time)
cp .env.example .env  # PowerShell: Copy-Item .env.example .env

# 2) Edit .env and set at least:
# LLM_PROVIDER=groq
# GROQ_API_KEY=your_groq_api_key_here

# 3) Run baseline with provider/model from .env
python scripts/baseline_inference.py --seed 42

# Optional runtime override
python scripts/baseline_inference.py --provider groq --model llama-3.3-70b-versatile --seed 42
```

**Output**:
- Console table with per-task scores
- `artifacts/baseline_scores.json` with detailed results
- Aggregate mean score

### Expected Baseline Scores

With deterministic settings (`seed=42`, `temperature=0`), you should see reproducible scores:

| Task | Expected Score |
|------|----------------|
| Easy | ~0.85 |
| Medium | ~0.72 |
| Hard | ~0.68 |

### Programmatic Usage

```python
from openenv_bug_triage import BugTriageEnv
from openenv_bug_triage.models import ActionModel, ClassifyAction

# Initialize environment
env = BugTriageEnv()

# Reset to specific task
obs = env.reset(task_id="bug_triage_easy", seed=42)

# Take an action
action = ActionModel(
    action_type="classify",
    classify=ClassifyAction(
        severity="sev2",
        priority="p2",
        component="api-gateway"
    )
)

obs, reward, done, info = env.step(action)

# Check current state
state = env.state()
print(f"Steps used: {state.steps_used}/{state.steps_remaining}")
```

### Pre-Submission Validation

Run the local pre-submit checks before final submission:

```bash
# Skip HF ping if your Space is not deployed yet
python precheck.py --skip-space

# Full check (recommended before submit)
python precheck.py --space-url https://<your-space-subdomain>.hf.space
```

This validates:
- HF Space `GET /reset` returns HTTP 200
- `docker build` succeeds
- `openenv validate` succeeds
## Deployment

### Hugging Face Spaces

1. **Create a new Space** on Hugging Face
2. **Set Space type** to "Docker"
3. **Add files**:
   - Push all source code
   - Include `Dockerfile`, `requirements.txt`, `openenv.yaml`
   - Add `openenv` tag to Space metadata

4. **Configure startup**:
   The Dockerfile automatically handles startup and health checks.

5. **Verify deployment**:
   The Space should pass health checks and be ready for inference.

## Project Structure

```
openenv-bug-triage/
  openenv_bug_triage/          # Main package
    __init__.py                # Package exports
    env.py                     # Environment implementation
    models.py                  # Pydantic models
    grader.py                  # Deterministic graders
    reward.py                  # Reward calculation
    tasks.py                   # Task definitions and loaders
    data/
      tasks/
        bug_triage_easy.json   # Task A fixture
        bug_triage_medium.json # Task B fixture
        bug_triage_hard.json   # Task C fixture
  scripts/
    baseline_inference.py      # Baseline runner
  tests/
    test_env_api.py           # API contract tests
    test_graders.py           # Grader tests
    test_determinism.py       # Reproducibility tests
  openenv.yaml                # Environment metadata
  Dockerfile                  # Container definition
  requirements.txt            # Python dependencies
  README.md                   # This file
```

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Adding New Tasks

1. Create fixture in `openenv_bug_triage/data/tasks/`
2. Update `tasks.py` to load the new fixture
3. Register in `openenv.yaml`
4. Add corresponding grader logic in `grader.py`

## License

MIT

## Citation

```bibtex
@software{bug_triage_openenv,
  title={Bug Triage OpenEnv: A Real-World Simulation for Software Bug Triage},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/openenv-bug-triage}
}
```

## Acknowledgments

Built according to the OpenEnv specification for creating reproducible, real-world AI training environments.





