# AI-Based Timetable Scheduler

A Streamlit application for the B.Tech AI assignment. It models teaching sessions as a Constraint Satisfaction Problem and includes plain/improved backtracking, Min-Conflicts, validation, timetable views, experiments and exports.

## Requirements
- Python 3.11 or 3.12 recommended
- pip

## Run locally (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## Project structure
- `app.py`: Streamlit user interface
- `algorithms/scheduler.py`: session expansion, domains, validation, scoring and solvers
- `data/small.json`: small sample dataset
- `data/large.json`: large sample dataset
- `tests/`: starter automated tests
- `reports/`: report outline

## Dataset format
JSON contains `time`, `classes`, `teachers`, `rooms`, and `subjects`. Teacher assignments are fixed per subject to reduce CSP domain size. A lab's `session_length` should be 2 and its weekly hours should be divisible by 2.

## Tests
```powershell
pip install pytest
python -m pytest -q
```

## Algorithms
- Plain backtracking baseline
- Improved backtracking with MRV, degree heuristic, LCV ordering and forward checking
- Min-Conflicts with randomized initialization, random walk and restarts

## Important
Always report actual measured experiment results. A solver failure or timeout must not be described as a successful timetable. Run the small dataset first and verify the final result with the independent hard-constraint checker.
