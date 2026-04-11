# Code Debug Environment — Full File Structure

```
openenv_bug_triage
├── openenv.yaml                  ← OpenEnv manifest (required)
├── inference.py                  ← Baseline agent script (must be in root)
├── pyproject.toml                ← Dependencies
├── README.md                     ← Docs with action/obs spaces
├── .dockerignore
├── models.py                     ← Pydantic Action/Observation/State
├── client.py                     ← EnvClient (for training code)
├── __init__.py                   ← Exports
└── server/
    ├── __init__.py
    ├── app.py                    ← FastAPI server
    ├── environment.py            ← Core logic: reset/step/state
    ├── tasks/
    │   ├── __init__.py
    │   ├── task_easy.py          ←  bug_triage_easy samples
    │   ├── task_medium.py        ←  bug_triage_medium samples
    │   └── task_hard.py          ←  bug_triage_difficult samples
    ├── graders/
    │   ├── __init__.py
    │   ├── grader_easy.py
    │   ├── grader_medium.py
    │   └── grader_hard.py
    ├── requirements.txt
    └── Dockerfile
```