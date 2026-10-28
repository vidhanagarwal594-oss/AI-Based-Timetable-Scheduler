import json, io, time
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from algorithms.scheduler import backtracking, min_conflicts, validate_timetable, soft_penalty, expand_sessions
from utils import load_json, dataset_summary, assignments_frame

st.set_page_config(page_title="AI Timetable Scheduler", page_icon="🗓️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: rgba(100,120,150,.08); padding: 14px; border-radius: 12px;}
h1,h2,h3 {letter-spacing:-.02em}
</style>
""", unsafe_allow_html=True)

BASE = Path(__file__).parent
if "dataset" not in st.session_state:
    st.session_state.dataset = load_json(BASE/"data"/"small.json")
if "assignments" not in st.session_state:
    st.session_state.assignments = {}
if "result" not in st.session_state:
    st.session_state.result = None

st.sidebar.title("🗓️ Timetable AI")
st.sidebar.caption("AI-Based Timetable Scheduler")
page = st.sidebar.radio("NAVIGATION", ["Dashboard","Manage Data","Generate Timetable","Timetable Viewer","Conflict Checker","Experiments & Export","About"])
st.sidebar.divider()
st.sidebar.caption("B.Tech AI Assignment • CSP + Local Search")

data = st.session_state.dataset
assignments = st.session_state.assignments

def save_upload(upload):
    try:
        parsed = json.load(upload)
        required = {"time","classes","teachers","rooms","subjects"}
        if not required.issubset(parsed):
            st.error("JSON must contain time, classes, teachers, rooms and subjects.")
            return
        st.session_state.dataset = parsed
        st.session_state.assignments = {}
        st.session_state.result = None
        st.success("Dataset loaded. Previous timetable cleared.")
        st.rerun()
    except Exception as e:
        st.error(f"Could not read dataset: {e}")

def current_frame():
    return assignments_frame(st.session_state.dataset, st.session_state.assignments)

if page == "Dashboard":
    st.title("AI Timetable Scheduler")
    st.write("Generate, validate and compare college timetables using Constraint Satisfaction and local search.")
    summary = dataset_summary(data)
    cols=st.columns(5)
    for col,(label,value) in zip(cols,summary.items()):
        col.metric(label,value)
    st.subheader("Quick start")
    st.markdown("1. Load a sample dataset or upload your own JSON.  \n2. Generate a timetable using an AI algorithm.  \n3. Inspect hard constraints and soft penalties.  \n4. View and export the schedule.")
    if st.session_state.result:
        r=st.session_state.result
        c=st.columns(4)
        c[0].metric("Status", "Valid" if r["success"] else "Not solved")
        c[1].metric("Runtime", f'{r["seconds"]:.3f}s')
        c[2].metric("Hard violations",len(r["violations"]))
        c[3].metric("Soft penalty",r["soft_penalty"] if r["soft_penalty"] is not None else "—")
        if r["success"]:
            st.success("A complete timetable with zero hard-constraint violations is available.")
        else:
            st.warning(r.get("status","No valid timetable found."))
    st.subheader("Dataset")
    st.dataframe(pd.DataFrame([{"ID":x["id"],"Name":x["name"],"Strength":x["strength"],"Subjects":", ".join(x["subjects"])} for x in data["classes"]]), use_container_width=True, hide_index=True)

elif page == "Manage Data":
    st.title("Manage Input Data")
    st.info("For a fast, reliable demo, use the supplied datasets or upload a JSON file following their schema.")
    a,b=st.columns(2)
    with a:
        if st.button("Load small dataset", use_container_width=True):
            st.session_state.dataset=load_json(BASE/"data"/"small.json")
            st.session_state.assignments={}; st.session_state.result=None; st.rerun()
    with b:
        if st.button("Load large dataset", use_container_width=True):
            st.session_state.dataset=load_json(BASE/"data"/"large.json")
            st.session_state.assignments={}; st.session_state.result=None; st.rerun()
    uploaded=st.file_uploader("Upload dataset JSON", type=["json"])
    if uploaded and st.button("Import JSON"):
        save_upload(uploaded)
    tabs=st.tabs(["Subjects","Teachers","Classes","Rooms","Time"])
    with tabs[0]: st.dataframe(pd.DataFrame(data["subjects"]), use_container_width=True, hide_index=True)
    with tabs[1]: st.dataframe(pd.DataFrame(data["teachers"]), use_container_width=True, hide_index=True)
    with tabs[2]: st.dataframe(pd.DataFrame(data["classes"]), use_container_width=True, hide_index=True)
    with tabs[3]: st.dataframe(pd.DataFrame(data["rooms"]), use_container_width=True, hide_index=True)
    with tabs[4]: st.json(data["time"])
    st.caption("Dataset editing is supported through JSON import. This avoids accidental changes to linked teacher/subject identifiers.")

elif page == "Generate Timetable":
    st.title("Generate Timetable")
    c1,c2=st.columns(2)
    with c1:
        algorithm=st.selectbox("AI algorithm",["Backtracking CSP (MRV + Degree + Forward Checking)","Plain Backtracking (baseline)","Min-Conflicts"])
        timeout=st.slider("Backtracking time limit (seconds)",1,20,8)
    with c2:
        seed=st.number_input("Random seed",min_value=0,max_value=999999,value=42)
        iterations=st.number_input("Min-Conflicts max iterations",min_value=100,max_value=20000,value=3000,step=100)
    st.caption("A valid result must be complete and have zero hard-constraint violations. Difficult instances may time out.")
    if st.button("✨ Generate timetable", type="primary", use_container_width=True):
        with st.spinner("Searching for a timetable..."):
            if algorithm.startswith("Backtracking CSP"):
                result=backtracking(data, improved=True, timeout_seconds=timeout, seed=int(seed))
            elif algorithm.startswith("Plain"):
                result=backtracking(data, improved=False, timeout_seconds=timeout, seed=int(seed))
            else:
                result=min_conflicts(data,max_iterations=int(iterations),restarts=8,seed=int(seed))
        result["algorithm"]=algorithm
        st.session_state.result=result
        st.session_state.assignments=result["assignments"]
        st.rerun()
    r=st.session_state.result
    if r:
        st.divider()
        st.subheader("Generation result")
        cols=st.columns(4)
        cols[0].metric("Status","SUCCESS" if r["success"] else "NOT SOLVED")
        cols[1].metric("Time",f'{r["seconds"]:.3f} s')
        cols[2].metric("Nodes / iterations",r.get("nodes",r.get("iterations","—")))
        cols[3].metric("Hard violations",len(r["violations"]))
        if r["success"]:
            st.success("Timetable is complete and passes the hard-constraint validator.")
            st.metric("Soft penalty (lower is better)",r["soft_penalty"])
        else:
            st.warning(r.get("status","No valid solution found."))
            st.write("The returned assignment may be partial or conflicting; do not submit it as a valid timetable.")
        if r["violations"]:
            with st.expander("Inspect validation messages"):
                for v in r["violations"][:100]: st.write("•",v)
        if r.get("history"):
            hist=pd.DataFrame(r["history"])
            st.plotly_chart(px.line(hist,x="iteration",y="cost",title="Min-Conflicts hard-conflict cost"),use_container_width=True)

elif page == "Timetable Viewer":
    st.title("Timetable Viewer")
    df=current_frame()
    if df.empty:
        st.info("Generate a timetable first.")
    else:
        view=st.radio("View by",["Class","Teacher","Room"],horizontal=True)
        field={"Class":"class","Teacher":"teacher","Room":"room"}[view]
        options=sorted(df[field].unique())
        selected=st.selectbox(f"Select {view.lower()}",options)
        sub=df[df[field]==selected].copy()
        days=data["time"]["days"]; periods=data["time"]["periods_per_day"]
        grid=pd.DataFrame("",index=[f"Period {p+1}" for p in range(periods)],columns=days)
        for _,row in sub.iterrows():
            for off in range(int(row["duration"])):
                p=int(row["period"])-1+off
                if p < periods:
                    details=f'{row["subject"]}\n{row["teacher"]}\n{row["room"]}'
                    grid.loc[f"Period {p+1}",row["day"]]=details if not grid.loc[f"Period {p+1}",row["day"]] else grid.loc[f"Period {p+1}",row["day"]]+"\n⚠ CLASH\n"+details
        st.dataframe(grid, use_container_width=True, height=450)
        st.caption("A multi-period lab appears in each occupied period. Empty cells are free periods.")
        st.subheader("Session details")
        st.dataframe(sub, use_container_width=True, hide_index=True)

elif page == "Conflict Checker":
    st.title("Hard-Constraint Conflict Checker")
    if not assignments:
        st.info("Generate or import a timetable assignment first.")
    else:
        violations=validate_timetable(data,assignments)
        if not violations:
            st.success("Zero hard-constraint violations detected.")
        else:
            st.error(f"{len(violations)} violation(s) detected.")
            st.dataframe(pd.DataFrame({"Violation":violations}),use_container_width=True,hide_index=True)
        st.write("Soft penalty:",soft_penalty(data,assignments))
        st.caption("The validator is independent of the algorithm and is reused for result verification.")

elif page == "Experiments & Export":
    st.title("Experiments & Export")
    st.write("Run the selected algorithm repeatedly to compare actual performance. Large instances can take time.")
    algo=st.selectbox("Algorithm for experiment",["Backtracking CSP (heuristics)","Min-Conflicts"])
    trials=st.slider("Trials",1,10,3)
    limit=st.slider("Time / iteration limit",1,10,5)
    seed0=st.number_input("Starting seed",value=100,min_value=0,max_value=999999)
    if st.button("Run experiment trials",type="primary"):
        rows=[]; last=None
        progress=st.progress(0)
        for i in range(trials):
            if algo.startswith("Backtracking"):
                last=backtracking(data,improved=True,timeout_seconds=limit,seed=int(seed0)+i)
                effort=last["nodes"]
            else:
                last=min_conflicts(data,max_iterations=limit*500,restarts=4,seed=int(seed0)+i)
                effort=last["iterations"]
            rows.append({"trial":i+1,"seed":int(seed0)+i,"seconds":last["seconds"],"effort":effort,
                         "success":last["success"],"hard_violations":len(last["violations"]),
                         "soft_penalty":last["soft_penalty"]})
            progress.progress((i+1)/trials)
        st.session_state.experiment_rows=rows
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        st.metric("Success rate",f'{sum(r["success"] for r in rows)}/{trials}')
        st.plotly_chart(px.bar(pd.DataFrame(rows),x="trial",y="seconds",title="Execution time by trial"),use_container_width=True)
    if "experiment_rows" in st.session_state:
        exp=pd.DataFrame(st.session_state.experiment_rows)
        st.download_button("Download experiment CSV",exp.to_csv(index=False).encode(),file_name="experiment_results.csv",mime="text/csv")
        out=io.BytesIO()
        with pd.ExcelWriter(out,engine="openpyxl") as writer: exp.to_excel(writer,index=False,sheet_name="Experiments")
        st.download_button("Download experiment Excel",out.getvalue(),file_name="experiment_results.xlsx")
    st.divider()
    df=current_frame()
    if not df.empty:
        st.subheader("Export current timetable")
        st.download_button("Download timetable CSV",df.to_csv(index=False).encode(),file_name="timetable.csv",mime="text/csv")
        out=io.BytesIO()
        with pd.ExcelWriter(out,engine="openpyxl") as writer: df.to_excel(writer,index=False,sheet_name="Timetable")
        st.download_button("Download timetable Excel",out.getvalue(),file_name="timetable.xlsx")
    st.download_button("Download current dataset JSON",json.dumps(data,indent=2).encode(),file_name="dataset.json",mime="application/json")

else:
    st.title("About this project")
    st.markdown("""
**AI-Based Timetable Scheduler** models timetable generation as a Constraint Satisfaction Problem (CSP).

**Algorithms**
- Plain Backtracking: baseline systematic search.
- Improved Backtracking: MRV, Degree heuristic, approximate Least Constraining Value ordering, and forward checking.
- Min-Conflicts: local search with random restarts and a small random-walk probability.

**Hard constraints:** teacher, class and room clashes; capacity; room type; teacher availability; exact weekly hours; teacher load; lunch breaks.

**Soft constraints:** reduce internal class gaps, spread repeated theory subjects across days, and avoid long consecutive teacher teaching runs. Lab sessions are represented as indivisible consecutive blocks.

**Important limitation:** the provided sample data is a demonstration dataset. Run the actual solvers and experiments and report the measured outcomes. Solver failure must be reported honestly.
""")
    st.subheader("Assignment deliverables")
    st.markdown("- Source code and README\n- Small and large datasets\n- Working demo\n- 6–10 page report\n- 8–10 minute presentation")
