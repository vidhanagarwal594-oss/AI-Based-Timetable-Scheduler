import json
from pathlib import Path
from algorithms.scheduler import expand_sessions, candidate_domain, validate_timetable, soft_penalty

ROOT=Path(__file__).resolve().parents[1]

def load_small():
    return json.loads((ROOT/"data"/"small.json").read_text(encoding="utf-8"))

def test_sessions_are_created():
    data=load_small()
    sessions=expand_sessions(data)
    assert sessions
    assert any(s["duration"]==2 for s in sessions)

def test_candidate_domains_nonempty_for_small_dataset():
    data=load_small()
    for session in expand_sessions(data):
        assert candidate_domain(session,data)

def test_validator_flags_incomplete_schedule():
    data=load_small()
    violations=validate_timetable(data,{})
    assert any("H7" in v for v in violations)

def test_soft_penalty_nonnegative():
    data=load_small()
    assert soft_penalty(data,{}) >= 0
