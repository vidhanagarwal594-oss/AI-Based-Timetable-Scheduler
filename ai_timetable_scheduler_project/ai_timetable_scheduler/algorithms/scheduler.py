"""Scheduling engine for the AI Timetable Scheduler assignment.

Sessions are variables. A theory session occupies one period; a lab session
occupies `duration` consecutive periods. Teacher assignments are fixed in the
dataset to keep the CSP domain manageable.
"""
from __future__ import annotations
import random
import time
from collections import defaultdict

def slot_label(day, period):
    return f"{day} P{period + 1}"

def expand_sessions(data):
    """Convert weekly subject requirements into indivisible sessions."""
    sessions = []
    for cls in data["classes"]:
        for code in cls["subjects"]:
            sub = next(s for s in data["subjects"] if s["code"] == code)
            duration = int(sub.get("session_length", 2 if sub["type"] == "lab" else 1))
            hours = int(sub["weekly_hours"])
            if duration < 1 or hours % duration:
                raise ValueError(f"{code}: weekly_hours must be divisible by session_length ({duration}).")
            for idx in range(hours // duration):
                sessions.append({
                    "id": f'{cls["id"]}-{code}-{idx+1}',
                    "class_id": cls["id"], "subject_code": code,
                    "subject_name": sub["name"], "teacher_id": sub["teacher_id"],
                    "type": sub["type"], "duration": duration,
                })
    return sessions

def _lookup(data):
    return ({x["id"]: x for x in data["classes"]},
            {x["id"]: x for x in data["teachers"]},
            {x["id"]: x for x in data["rooms"]},
            {x["code"]: x for x in data["subjects"]})

def _occupied_periods(value, duration):
    return [(value["day"], value["period"] + i) for i in range(duration)]

def candidate_domain(session, data):
    classes, teachers, rooms, subjects = _lookup(data)
    cls, teacher = classes[session["class_id"]], teachers[session["teacher_id"]]
    domains = []
    days, periods = data["time"]["days"], int(data["time"]["periods_per_day"])
    unavailable = {tuple(x) for x in teacher.get("unavailable_slots", [])}
    lunch = cls.get("lunch_period")
    for day in days:
        for start in range(periods - session["duration"] + 1):
            occ = _occupied_periods({"day": day, "period": start}, session["duration"])
            if any((d, p) in unavailable for d, p in occ):
                continue
            if any(p == lunch for d, p in occ):
                continue
            for room in data["rooms"]:
                if room["capacity"] < cls["strength"]:
                    continue
                if room["type"] != session["type"]:
                    continue
                domains.append({"day": day, "period": start, "room_id": room["id"]})
    return domains

def validate_timetable(data, assignments):
    """Return a list of readable hard-constraint violations."""
    classes, teachers, rooms, subjects = _lookup(data)
    sessions = {s["id"]: s for s in expand_sessions(data)}
    violations = []
    occupancy = defaultdict(list)
    hours_by_subject = defaultdict(int)
    teacher_load = defaultdict(int)
    assigned_ids = set(assignments)

    if assigned_ids != set(sessions):
        missing = sorted(set(sessions) - assigned_ids)
        extra = sorted(assigned_ids - set(sessions))
        if missing:
            violations.append(f"H7: Missing required sessions: {', '.join(missing[:8])}")
        if extra:
            violations.append(f"Unknown session IDs: {', '.join(extra[:8])}")

    for sid, val in assignments.items():
        if sid not in sessions:
            continue
        s = sessions[sid]
        cls, teacher = classes[s["class_id"]], teachers[s["teacher_id"]]
        room = rooms.get(val.get("room_id"))
        if room is None:
            violations.append(f"{sid}: unknown room {val.get('room_id')}")
            continue
        periods = _occupied_periods(val, s["duration"])
        if any(p < 0 or p >= data["time"]["periods_per_day"] for _, p in periods):
            violations.append(f"{sid}: session extends outside the day")
            continue
        if room["capacity"] < cls["strength"]:
            violations.append(f"H4: {sid} class strength exceeds room capacity")
        if room["type"] != s["type"]:
            violations.append(f"H5: {sid} requires {s['type']} room")
        if any((d, p) in {tuple(x) for x in teacher.get("unavailable_slots", [])} for d,p in periods):
            violations.append(f"H6: {sid} uses an unavailable teacher slot")
        if any(p == cls.get("lunch_period") for d,p in periods):
            violations.append(f"H9: {sid} overlaps {cls['id']}'s lunch break")
        teacher_load[teacher["id"]] += s["duration"]
        hours_by_subject[(cls["id"], s["subject_code"])] += s["duration"]
        for d,p in periods:
            occupancy[("teacher", teacher["id"], d, p)].append(sid)
            occupancy[("class", cls["id"], d, p)].append(sid)
            occupancy[("room", room["id"], d, p)].append(sid)

    for (kind, entity, day, period), ids in occupancy.items():
        if len(ids) > 1:
            code = {"teacher":"H1", "class":"H2", "room":"H3"}[kind]
            violations.append(f"{code}: {entity} has a clash on {day} period {period+1}: {', '.join(ids)}")

    for cls in data["classes"]:
        for code in cls["subjects"]:
            sub = subjects[code]
            actual = hours_by_subject[(cls["id"], code)]
            if actual != sub["weekly_hours"]:
                violations.append(f"H7: {cls['id']} {code} has {actual}/{sub['weekly_hours']} hours")
    for tid, load in teacher_load.items():
        if load > teachers[tid]["max_weekly_load"]:
            violations.append(f"H8: {tid} load {load} exceeds maximum {teachers[tid]['max_weekly_load']}")
    return violations

def soft_penalty(data, assignments):
    """Lower is better. Implements gaps, subject spreading, lab continuity via blocks,
    and >2 consecutive teacher periods. Lab blocks are indivisible by construction.
    """
    sessions = {s["id"]: s for s in expand_sessions(data)}
    classes, teachers, rooms, subjects = _lookup(data)
    class_periods = defaultdict(set)
    subject_days = defaultdict(set)
    teacher_periods = defaultdict(set)
    for sid, val in assignments.items():
        if sid not in sessions:
            continue
        s = sessions[sid]
        for offset in range(s["duration"]):
            p = val["period"] + offset
            class_periods[(s["class_id"], val["day"])].add(p)
            teacher_periods[(s["teacher_id"], val["day"])].add(p)
        subject_days[(s["class_id"], s["subject_code"], val["day"])].add(sid)
    penalty = 0
    # S1: internal gaps between the first and last occupied period
    for key, periods in class_periods.items():
        if periods:
            penalty += max(periods) - min(periods) + 1 - len(periods)
    # S2: repeat same non-lab subject on a day (weekly spread is encouraged)
    for (cid, code, day), ids in subject_days.items():
        if subjects[code]["type"] != "lab" and len(ids) > 1:
            penalty += 3 * (len(ids) - 1)
    # S5: teacher has more than two consecutive occupied periods
    for key, periods in teacher_periods.items():
        run = 0
        for p in range(data["time"]["periods_per_day"]):
            if p in periods:
                run += 1
                if run > 2:
                    penalty += 2
            else:
                run = 0
    return int(penalty)

def _compatible(session, value, assigned, sessions_by_id):
    """Fast hard clash check against already assigned sessions."""
    s_periods = set(_occupied_periods(value, session["duration"]))
    for sid, other_val in assigned.items():
        other = sessions_by_id[sid]
        if not (s_periods & set(_occupied_periods(other_val, other["duration"]))):
            continue
        if session["class_id"] == other["class_id"]:
            return False
        if session["teacher_id"] == other["teacher_id"]:
            return False
        if value["room_id"] == other_val["room_id"]:
            return False
    return True

def backtracking(data, improved=True, timeout_seconds=8, seed=42):
    start_time = time.perf_counter()
    sessions = expand_sessions(data)
    by_id = {s["id"]: s for s in sessions}
    domains = {s["id"]: candidate_domain(s, data) for s in sessions}
    if any(not domains[s["id"]] for s in sessions):
        return {"success": False, "assignments": {}, "nodes": 0, "seconds": time.perf_counter()-start_time,
                "violations": ["At least one session has an empty domain."], "soft_penalty": None, "status":"infeasible domain"}
    # Seeded order provides reproducibility without changing correctness.
    rng = random.Random(seed)
    for d in domains.values():
        rng.shuffle(d)
    assigned, nodes = {}, 0
    deadline = start_time + timeout_seconds

    def search():
        nonlocal nodes
        if len(assigned) == len(sessions):
            return True
        if time.perf_counter() >= deadline:
            return False
        unassigned = [s for s in sessions if s["id"] not in assigned]
        if improved:
            # MRV, then degree heuristic: more shared class/teacher constraints first.
            def rank(s):
                valid = sum(_compatible(s, v, assigned, by_id) for v in domains[s["id"]])
                degree = sum(1 for o in unassigned if o["id"] != s["id"] and
                             (o["class_id"] == s["class_id"] or o["teacher_id"] == s["teacher_id"]))
                return (valid, -degree)
            session = min(unassigned, key=rank)
        else:
            session = unassigned[0]
        sid = session["id"]
        options = [v for v in domains[sid] if _compatible(session, v, assigned, by_id)]
        if improved:
            # Least-constraining-value approximation: prefer values leaving more choices.
            def lcv(value):
                conflicts = 0
                for other in unassigned:
                    if other["id"] == sid:
                        continue
                    for ov in domains[other["id"]]:
                        if not _compatible(other, ov, {**assigned, sid:value}, by_id):
                            conflicts += 1
                return conflicts
            options.sort(key=lcv)
        for value in options:
            nodes += 1
            assigned[sid] = value
            # Forward checking: every remaining variable must retain at least one legal value.
            if not improved or all(any(_compatible(o, ov, assigned, by_id)
                    for ov in domains[o["id"]]) for o in unassigned if o["id"] != sid):
                if search():
                    return True
            assigned.pop(sid, None)
        return False

    success = search()
    elapsed = time.perf_counter() - start_time
    result = dict(assigned) if success else dict(assigned)
    violations = validate_timetable(data, result)
    valid = success and not violations and len(result) == len(sessions)
    return {"success": valid, "assignments": result, "nodes": nodes, "seconds": elapsed,
            "violations": violations, "soft_penalty": soft_penalty(data, result) if valid else None,
            "status": "success" if valid else ("timeout or search exhausted" if elapsed >= timeout_seconds else "no complete valid assignment")}

def min_conflicts(data, max_iterations=5000, restarts=8, seed=42):
    """Min-Conflicts local search over complete assignments using unary-valid domains.
    If it cannot solve the instance, it reports failure rather than claiming success.
    """
    start = time.perf_counter()
    rng = random.Random(seed)
    sessions = expand_sessions(data)
    by_id = {s["id"]: s for s in sessions}
    domains = {s["id"]: candidate_domain(s, data) for s in sessions}
    if any(not d for d in domains.values()):
        return {"success":False,"assignments":{},"iterations":0,"seconds":time.perf_counter()-start,
                "violations":["At least one session has an empty domain."],"soft_penalty":None,
                "history":[],"status":"infeasible domain"}
    def conflicts(sid, value, assign):
        s = by_id[sid]
        count = 0
        for oid, ov in assign.items():
            if oid == sid: continue
            other = by_id[oid]
            overlap = set(_occupied_periods(value,s["duration"])) & set(_occupied_periods(ov,other["duration"]))
            if overlap and (s["class_id"] == other["class_id"] or s["teacher_id"] == other["teacher_id"] or value["room_id"] == ov["room_id"]):
                count += len(overlap)
        return count
    history, total_iter, best = [], 0, None
    for restart in range(restarts):
        assignment = {s["id"]: rng.choice(domains[s["id"]]) for s in sessions}
        for _ in range(max_iterations):
            total_iter += 1
            conflicted = [sid for sid,v in assignment.items() if conflicts(sid,v,assignment)>0]
            hard = sum(conflicts(sid,v,assignment) for sid,v in assignment.items()) // 2
            history.append({"iteration":total_iter,"cost":hard})
            if best is None or hard < best[0]:
                best = (hard, dict(assignment))
            if hard == 0:
                violations = validate_timetable(data, assignment)
                if not violations:
                    return {"success":True,"assignments":assignment,"iterations":total_iter,
                            "seconds":time.perf_counter()-start,"violations":[],"soft_penalty":soft_penalty(data,assignment),
                            "history":history,"status":"success"}
            if not conflicted:
                break
            sid = rng.choice(conflicted)
            scores = [(conflicts(sid,v,assignment),v) for v in domains[sid]]
            min_score = min(x[0] for x in scores)
            choices = [v for score,v in scores if score == min_score]
            if rng.random() < 0.03:
                assignment[sid] = rng.choice(domains[sid])
            else:
                assignment[sid] = rng.choice(choices)
    result = best[1] if best else {}
    violations = validate_timetable(data, result)
    return {"success":False,"assignments":result,"iterations":total_iter,"seconds":time.perf_counter()-start,
            "violations":violations,"soft_penalty":None,"history":history,"status":"no valid timetable found within limits"}
