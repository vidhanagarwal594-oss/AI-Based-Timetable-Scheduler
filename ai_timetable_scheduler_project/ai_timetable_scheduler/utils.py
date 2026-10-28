import json
import pandas as pd

def load_json(upload):
    if hasattr(upload, "read"):
        return json.load(upload)
    with open(upload, encoding="utf-8") as f:
        return json.load(f)

def dataset_summary(data):
    return {
        "Classes": len(data.get("classes", [])),
        "Teachers": len(data.get("teachers", [])),
        "Rooms": len(data.get("rooms", [])),
        "Subjects": len(data.get("subjects", [])),
        "Available room-periods": len(data.get("rooms", [])) * len(data["time"]["days"]) * data["time"]["periods_per_day"],
    }

def assignments_frame(data, assignments):
    classes = {x["id"]:x for x in data["classes"]}
    teachers = {x["id"]:x for x in data["teachers"]}
    rooms = {x["id"]:x for x in data["rooms"]}
    subjects = {x["code"]:x for x in data["subjects"]}
    rows=[]
    for s in __import__("algorithms.scheduler", fromlist=["expand_sessions"]).expand_sessions(data):
        v=assignments.get(s["id"])
        if not v: continue
        rows.append({"session_id":s["id"],"class":classes[s["class_id"]]["name"],"class_id":s["class_id"],
          "subject":subjects[s["subject_code"]]["name"],"subject_code":s["subject_code"],
          "teacher":teachers[s["teacher_id"]]["name"],"teacher_id":s["teacher_id"],
          "room":rooms[v["room_id"]]["name"],"room_id":v["room_id"],"day":v["day"],
          "period":v["period"]+1,"duration":s["duration"],"type":s["type"]})
    return pd.DataFrame(rows)
