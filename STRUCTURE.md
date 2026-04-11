# Bug Triage OpenEnv Structure

```text
openenv_bug_triage
|-- openenv.yaml                  # OpenEnv manifest
|-- inference.py                  # Submission runner / offline baseline
|-- pyproject.toml                # Project metadata and dependencies
|-- README.md                     # Setup, API, and task overview
|-- models.py                     # Typed observation, action, reward, and state models
|-- client.py                     # Lightweight environment client
|-- server/
|   |-- app.py                    # FastAPI server
|   |-- environment.py            # Core environment logic
|   |-- heuristics.py             # Shared inference heuristics
|   |-- policy.py                 # Shared deterministic triage policy
|   |-- tasks/
|   |   |-- task_easy.py
|   |   |-- task_medium.py
|   |   `-- task_hard.py
|   `-- graders/
|       |-- grader_easy.py
|       |-- grader_medium.py
|       `-- grader_hard.py
`-- tests/
    |-- test_api_contract.py
    |-- test_environment.py
    |-- test_graders.py
    |-- test_heuristics.py
    |-- test_inference_contract.py
    `-- test_policy.py
```
