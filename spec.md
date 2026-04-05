# Bug Triage OpenEnv - Specification

## 1) Goal
Build a complete OpenEnv environment that simulates **real-world software bug triage** and supports learning through:

- `reset()`
- `step(action)`
- `state()`

The environment must include deterministic tasks, programmatic graders, reward shaping, reproducible baseline scoring, and deployment artifacts for Hugging Face Spaces.

## 2) Real-World Simulation
### Domain
A software organization receives incoming bug reports from users, QA, and automated monitoring.  
The agent acts as a triage engineer responsible for:

- assigning severity and priority
- identifying duplicates
- routing bugs to correct team/component
- requesting missing information when needed
- deciding whether to close/defer/escalate

### Why this is real-world
Bug triage is a common operational workflow in engineering teams and has concrete measurable outcomes: SLA compliance, issue resolution speed, and triage correctness.

## 3) Environment API (OpenEnv Spec)
Implement typed Pydantic models and standard methods.

### 3.1 Typed Models
Create:

- `ObservationModel`
- `ActionModel`
- `RewardModel`
- `StateModel` (for `state()`)

All models should be explicit and strictly typed (`Literal`, `Enum`, bounded numeric fields where possible).

### 3.2 Method Contracts
- `reset(task_id: str | None = None, seed: int | None = None) -> ObservationModel`
- `step(action: ActionModel) -> tuple[ObservationModel, RewardModel, bool, dict]`
- `state() -> StateModel`

### 3.3 Step Semantics
Each step processes exactly one action against the current ticket queue and returns:

- updated observation
- reward details (dense + cumulative)
- `done` when success/failure/step-budget reached
- `info` with grader signals and diagnostics

## 4) Data Model
Each ticket record should include:

- `ticket_id: str`
- `title: str`
- `description: str`
- `reporter_type: Literal["user","qa","monitoring"]`
- `service: str`
- `component_candidates: list[str]`
- `created_at: datetime`
- `customer_tier: Literal["free","pro","enterprise"]`
- `repro_steps_present: bool`
- `logs_present: bool`
- `attachments_count: int`
- `suspected_duplicate_ids: list[str]`

Hidden ground truth per ticket:

- `true_severity: Literal["sev0","sev1","sev2","sev3"]`
- `true_priority: Literal["p0","p1","p2","p3"]`
- `true_component: str`
- `true_assignee_team: str`
- `duplicate_of: str | null`
- `needs_more_info: bool`

## 5) Action Space
Use a single structured action schema with `action_type` plus typed payload:

- `classify`: set severity + priority + component
- `assign`: set owner team
- `mark_duplicate`: set canonical ticket id
- `request_info`: ask for missing repro/logs
- `defer`: move to backlog with reason
- `close`: close with reason (`invalid`, `won't_fix`, `cannot_reproduce`, `resolved`)
- `escalate_incident`: escalate urgent production impact
- `next_ticket`: move focus pointer

Validation rules:

- invalid field combos rejected with penalty
- references to unknown ticket IDs rejected with penalty
- destructive actions (`close`, `defer`) penalized if inconsistent with truth

## 6) Observation Space
Observation should include:

- focused ticket summary (`current_ticket`)
- queue stats (`remaining_count`, `urgent_count`, SLA-at-risk count)
- prior actions and outcomes (`last_action_result`)
- available teams/components
- step budget (`steps_used`, `steps_remaining`)
- partial score breakdown (optional but recommended for agent learning)

Observation must not expose hidden labels directly.

## 7) Reward Function (Meaningful + Dense)
Reward range per step: clamp to `[-1.0, 1.0]`.  
Episode final score normalized to `[0.0, 1.0]`.

### 7.1 Dense Progress Signals
Suggested additive components:

- `+0.20` correct severity
- `+0.15` correct priority
- `+0.15` correct component
- `+0.10` correct team assignment
- `+0.15` correct duplicate linking
- `+0.10` correct request for more info
- `+0.15` correct escalation for sev0/sev1 production incident

### 7.2 Negative Signals
- `-0.20` incorrect close/defer on valid bug
- `-0.15` missed critical escalation
- `-0.05` invalid action schema
- `-0.02` repeated no-op / loop behavior
- `-0.01` unnecessary ticket switches

### 7.3 Terminal Bonus/Penalty
- `+0.10` if all critical tickets triaged within budget
- `-0.10` if step budget exhausted with high-severity untriaged tickets

## 8) Tasks and Graders (Easy / Medium / Hard)
Implement 3 fixed tasks with deterministic fixtures and grader logic.

## 8.1 Task A - Easy (`bug_triage_easy`)
Scenario:

- 8 tickets
- mostly clear reports
- minimal duplicates
- obvious component mapping

Grader criteria:

- weighted accuracy on severity/priority/component/team
- no more than 1 major mistake
- deterministic score in `[0,1]`

## 8.2 Task B - Medium (`bug_triage_medium`)
Scenario:

- 15 tickets
- mixed-quality reports
- several duplicates
- some missing repro details
- limited step budget

Grader criteria:

- weighted label correctness
- duplicate resolution F1-like score
- correct use of `request_info`
- loop/destructive penalties applied

## 8.3 Task C - Hard (`bug_triage_hard`)
Scenario:

- 25 tickets
- noisy and ambiguous text
- conflicting signals
- strict SLA pressure for enterprise + high severity tickets
- trade-offs under capacity constraints

Grader criteria:

- strict weighting on sev0/sev1 correctness
- SLA-risk handling score
- escalation correctness
- global policy quality (avoid destructive shortcuts)

## 8.4 Grader Output Contract
Each grader returns:

- `score: float` in `[0.0, 1.0]`
- `subscores: dict[str, float]`
- `mistakes: list[str]`
- `passed: bool` (optional threshold, e.g., `>= 0.75`)

## 9) Determinism and Reproducibility
- Fixed dataset fixtures per task (`data/tasks/*.json`)
- Deterministic shuffling controlled by seed
- deterministic grader logic (no LLM-in-the-loop grading)
- baseline run outputs JSON artifact with exact scores

Recommended defaults:

- `DEFAULT_SEED=42`
- model temperature `0`

## 10) Baseline Inference Script
Create `scripts/baseline_inference.py`:

- Reads `OPENAI_API_KEY` from environment
- Runs all 3 tasks end-to-end
- Uses fixed prompt template and deterministic model params
- Writes:
  - console table of per-task score
  - `artifacts/baseline_scores.json`
  - aggregate mean score

CLI example:

```bash
python scripts/baseline_inference.py --model gpt-5-mini --seed 42
```

## 11) openenv.yaml (Required)
Include metadata and task registration:

```yaml
id: bug-triage-openenv
name: Bug Triage OpenEnv
version: 0.1.0
entrypoint: openenv_bug_triage.env:BugTriageEnv
tags:
  - openenv
  - bug-triage
  - real-world
tasks:
  - id: bug_triage_easy
    difficulty: easy
  - id: bug_triage_medium
    difficulty: medium
  - id: bug_triage_hard
    difficulty: hard
```

Then validate with:

```bash
openenv validate
```

## 12) Suggested Project Structure
```text
openenv-bug-triage/
  openenv_bug_triage/
    __init__.py
    env.py
    models.py
    grader.py
    reward.py
    tasks.py
    data/
      tasks/
        bug_triage_easy.json
        bug_triage_medium.json
        bug_triage_hard.json
  scripts/
    baseline_inference.py
  tests/
    test_env_api.py
    test_graders.py
    test_determinism.py
  openenv.yaml
  Dockerfile
  requirements.txt
  README.md
```

## 13) Docker + HF Space Deployment
### 13.1 Dockerfile Requirements
- Base image: `python:3.11-slim`
- install dependencies from `requirements.txt`
- copy source + data
- expose runtime command for environment app or API wrapper
- must run successfully with:

```bash
docker build -t bug-triage-openenv .
docker run --rm -p 7860:7860 bug-triage-openenv
```

### 13.2 Hugging Face Space
- Space type: Docker
- include `README.md` and `openenv` tag in metadata
- startup should pass health check and expose expected endpoint/process

## 14) README Requirements
README must include:

- environment motivation and real-world relevance
- observation and action schema definitions
- task descriptions + difficulty rationale
- reward design and scoring explanation
- local setup instructions
- validation command (`openenv validate`)
- baseline command and expected reproducible scores
- Docker and HF Space deployment steps

## 15) Acceptance Criteria Checklist
- [ ] Real-world bug triage simulation implemented
- [ ] Full OpenEnv API with typed models
- [ ] `openenv.yaml` present and valid
- [ ] 3 tasks (easy/medium/hard) with deterministic graders
- [ ] Dense reward shaping with partial progress + penalties
- [ ] Baseline inference script with reproducible results
- [ ] Working Dockerfile
- [ ] Deployable HF Space configuration
- [ ] README complete per requirements

## 16) Implementation Sequence (How to Build)
1. Define typed models in `models.py`.
2. Implement environment lifecycle in `env.py` (`reset/step/state`).
3. Add fixed task fixtures and loader in `tasks.py`.
4. Implement reward shaping logic in `reward.py`.
5. Implement deterministic grader in `grader.py`.
6. Register metadata in `openenv.yaml`; run `openenv validate`.
7. Build baseline runner and lock seed/model params.
8. Add tests for API contract, graders, determinism.
9. Add Dockerfile and verify container startup.
10. Publish to HF Space and verify runtime.

This sequence is the recommended path for turning the spec into a working submission.
1. Start Docker Desktop engine                                                                     
  2. Install validator tool: pip install openenv-core                                                
  3. Run: python precheck.py --space-url https://<your-space>.hf.space                               
   