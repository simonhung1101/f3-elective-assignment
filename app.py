import streamlit as st
import pandas as pd
import plotly.express as px
import os

from assignment import assign_students, get_all_unique_normal
from utils import (
    get_default_config, validate_config, save_config_json, load_config_json,
    create_template_bytes, parse_uploaded_excel, validate_imported_data,
    export_results_to_bytes, generate_summary,
)
import cloud_storage

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

st.set_page_config(page_title="F3 Elective Assignment", layout="wide")

if 'config' not in st.session_state:
    st.session_state.config = get_default_config()
if 'students_raw' not in st.session_state:
    st.session_state.students_raw = None
if 'results' not in st.session_state:
    st.session_state.results = None
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'import_errors' not in st.session_state:
    st.session_state.import_errors = []
if '_cloud_loaded' not in st.session_state:
    config, students, results, summary, msg = cloud_storage.load_session()
    if config is not None:
        st.session_state.config = config
        st.session_state.students_raw = students
        st.session_state.results = results
        st.session_state.summary = summary
        st.session_state._cloud_loaded = msg
    else:
        st.session_state._cloud_loaded = False


def _block_cap(cfg, block_num, subject):
    return cfg.get('capacities', {}).get(block_num, {}).get(subject, 25)


def render_config_page():
    st.header("Configuration")
    cfg = st.session_state.config

    cfg['academic_year'] = st.text_input("Academic Year", value=cfg['academic_year'],
                                          placeholder="e.g. 2025-2026")

    b1_names, b2_names, b3n_names, b3a_names = [], [], [], []

    cols = st.columns(2)
    with cols[0]:
        st.subheader("Block 1 (5 Normal Subjects)")
        for i in range(5):
            c1, c2 = st.columns([3, 1])
            val = cfg.get('block_1', [''] * 5)[i]
            name = c1.text_input(f"Subject {i + 1}", value=val, key=f"b1_{i}")
            cap = c2.number_input(f"Cap", min_value=1, max_value=99,
                                  value=_block_cap(cfg, 1, name) if name else 25,
                                  key=f"b1_cap_{i}")
            b1_names.append((name, cap))

    with cols[1]:
        st.subheader("Block 2 (5 Normal Subjects)")
        for i in range(5):
            c1, c2 = st.columns([3, 1])
            val = cfg.get('block_2', [''] * 5)[i]
            name = c1.text_input(f"Subject {i + 1}", value=val, key=f"b2_{i}")
            cap = c2.number_input(f"Cap", min_value=1, max_value=99,
                                  value=_block_cap(cfg, 2, name) if name else 25,
                                  key=f"b2_cap_{i}")
            b2_names.append((name, cap))

    st.subheader("Block 3")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Normal Subjects**")
        for i in range(2):
            col1, col2 = st.columns([3, 1])
            val = cfg.get('block_3_normal', [''] * 2)[i]
            name = col1.text_input(f"Subject {i + 1}", value=val, key=f"b3n_{i}")
            cap = col2.number_input(f"Cap", min_value=1, max_value=99,
                                    value=_block_cap(cfg, 3, name) if name else 25,
                                    key=f"b3n_cap_{i}")
            b3n_names.append((name, cap))

    with c2:
        st.markdown("**Applied Learning (ApL)**")
        for i in range(3):
            col1, col2 = st.columns([3, 1])
            val = cfg.get('block_3_apl', [''] * 3)[i]
            name = col1.text_input(f"Subject {i + 1}", value=val, key=f"b3a_{i}")
            cap = col2.number_input(f"Cap", min_value=1, max_value=99,
                                    value=_block_cap(cfg, 3, name) if name else 15,
                                    key=f"b3a_cap_{i}")
            b3a_names.append((name, cap))

    b1_just_names = [n for n, _ in b1_names]
    b2_just_names = [n for n, _ in b2_names]
    b3n_just_names = [n for n, _ in b3n_names]

    all_subjects_with_blocks = {}
    for bnum, subs in [(1, b1_just_names), (2, b2_just_names), (3, b3n_just_names)]:
        for s in subs:
            if s:
                all_subjects_with_blocks.setdefault(s, []).append(bnum)

    repeated_candidates = {s: bs for s, bs in all_subjects_with_blocks.items() if len(bs) >= 2}

    rep_info = cfg.get('repeated_subject', {})
    if isinstance(rep_info, dict):
        prev_rep_name = rep_info.get('name', '')
        prev_rep_blocks = rep_info.get('blocks', [])
    else:
        prev_rep_name = rep_info
        prev_rep_blocks = [1, 2]

    st.divider()
    st.subheader("Repeated Subject")
    if repeated_candidates:
        rep_names = list(repeated_candidates.keys())
        rep_name = st.selectbox(
            "Select repeated subject (appears in multiple blocks):",
            options=[""] + rep_names,
            index=(rep_names.index(prev_rep_name) + 1) if prev_rep_name in rep_names else 0,
        )
        if rep_name:
            possible_blocks = repeated_candidates[rep_name]
            st.info(f"**{rep_name}** appears in: Block {', '.join(str(b) for b in possible_blocks)}")
            rep_blocks = st.multiselect(
                "Which two blocks should the repeated subject span?",
                options=possible_blocks,
                default=[b for b in prev_rep_blocks if b in possible_blocks] or possible_blocks[:2],
                max_selections=2,
            )
            cfg['repeated_subject'] = {"name": rep_name, "blocks": sorted(rep_blocks)}
        else:
            cfg['repeated_subject'] = {"name": "", "blocks": []}
    else:
        cfg['repeated_subject'] = {"name": "", "blocks": []}
        if all(b1_just_names) and all(b2_just_names) and all(b3n_just_names):
            st.warning("No subject appears in multiple blocks. "
                       "Use the same subject name in two different blocks to set a repeated subject.")

    if st.button("Save Configuration"):
        cfg['block_1'] = [n for n, _ in b1_names]
        cfg['block_2'] = [n for n, _ in b2_names]
        cfg['block_3_normal'] = [n for n, _ in b3n_names]
        cfg['block_3_apl'] = [n for n, _ in b3a_names]

        caps = cfg.setdefault('capacities', {1: {}, 2: {}, 3: {}})
        for block_num, items in [(1, b1_names), (2, b2_names), (3, b3n_names + b3a_names)]:
            caps.setdefault(block_num, {})
            for name, cap in items:
                if name:
                    caps[block_num][name] = cap

        errors = validate_config(cfg)
        if errors:
            for e in errors:
                st.error(e)
        else:
            os.makedirs(DATA_DIR, exist_ok=True)
            fpath = os.path.join(DATA_DIR, f"config_{cfg['academic_year'].replace('/', '-')}.json")
            save_config_json(cfg, fpath)
            st.session_state.config = cfg
            st.success(f"Configuration saved to {fpath}")
            st.balloons()

    st.divider()
    st.subheader("Load Existing Configuration")
    if os.path.isdir(DATA_DIR):
        config_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
        if config_files:
            selected = st.selectbox("Select saved config:", config_files)
            if st.button("Load Config"):
                fpath = os.path.join(DATA_DIR, selected)
                loaded = load_config_json(fpath)
                st.session_state.config = loaded
                st.rerun()
        else:
            st.info("No saved configurations found.")


def render_import_page():
    st.header("Data Import")
    cfg = st.session_state.config

    errors = validate_config(cfg)
    if errors:
        st.warning("Please complete the Configuration page first.")
        for e in errors:
            st.error(e)
        return

    with st.expander("Download Template", expanded=False):
        if st.button("Generate Blank Template (.xlsx)"):
            template_bytes = create_template_bytes(cfg)
            st.download_button(
                label="Download Template",
                data=template_bytes,
                file_name=f"elective_template_{cfg['academic_year']}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        all_unique = get_all_unique_normal(cfg)
        mapping = {"Column": [], "Maps To": []}
        for i, s in enumerate(cfg['block_1']):
            mapping["Column"].append(f"B1_Pref_{i + 1}")
            mapping["Maps To"].append(s)
        for i, s in enumerate(cfg['block_2']):
            mapping["Column"].append(f"B2_Pref_{i + 1}")
            mapping["Maps To"].append(s)
        for i, s in enumerate(cfg['block_3_normal'] + cfg['block_3_apl']):
            mapping["Column"].append(f"B3_Pref_{i + 1}")
            mapping["Maps To"].append(s)
        for i, s in enumerate(all_unique):
            mapping["Column"].append(f"Overall_Pref_{i + 1}")
            mapping["Maps To"].append(s)
        st.table(pd.DataFrame(mapping))

    st.divider()
    uploaded = st.file_uploader("Upload student data (.xlsx)", type=["xlsx"])

    if uploaded:
        try:
            df = parse_uploaded_excel(uploaded, cfg)
            st.success(f"Loaded {len(df)} student records.")

            errs = validate_imported_data(df, cfg)
            if errs:
                st.session_state.import_errors = errs
                with st.expander(f"Validation Errors ({len(errs)})", expanded=True):
                    for e in errs:
                        st.error(e)
            else:
                st.session_state.import_errors = []

            st.subheader("Preview")
            display_cols = ["Student Name", "Class", "Class_No", "Marks"]
            st.dataframe(df[display_cols].head(20), use_container_width=True,
                         hide_index=True)
            st.caption(f"Showing first {min(20, len(df))} of {len(df)} rows")

            st.subheader("Edit Student Data")
            edited = st.data_editor(
                df,
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key="data_editor",
            )
            if st.button("Apply Changes"):
                st.session_state.students_raw = edited
                st.success(f"Saved {len(edited)} student records to session.")
                st.rerun()

        except Exception as ex:
            st.error(f"Error reading file: {ex}")

    if st.session_state.students_raw is not None and uploaded is None:
        st.info(f"Currently loaded: {len(st.session_state.students_raw)} students from previous import.")
        if st.button("Clear Imported Data"):
            st.session_state.students_raw = None
            st.rerun()


def render_run_page():
    st.header("Run Assignment")
    cfg = st.session_state.config

    if st.session_state.students_raw is None:
        st.warning("No student data loaded. Go to Data Import page first.")
        return

    errors = validate_config(cfg)
    if errors:
        for e in errors:
            st.error(e)
        return

    st.info(f"Ready to assign **{len(st.session_state.students_raw)}** students.")

    run_cols = st.columns([1, 1, 1])
    all_unique = get_all_unique_normal(cfg)
    total_cap = sum(cfg['capacities'].get(s, 25) for s in cfg['block_1'])
    run_cols[0].metric("Block 1 Total Capacity", total_cap)
    total_cap2 = sum(cfg['capacities'].get(s, 25) for s in cfg['block_2'])
    run_cols[1].metric("Block 2 Total Capacity", total_cap2)
    total_cap3 = sum(cfg['capacities'].get(s, 25) for s in (cfg['block_3_normal'] + cfg['block_3_apl']))
    run_cols[2].metric("Block 3 Total Capacity", total_cap3)

    n_students = len(st.session_state.students_raw)
    if total_cap < n_students:
        st.warning(f"⚠️ Block 1 capacity ({total_cap}) < students ({n_students})!")
    if total_cap2 < n_students:
        st.warning(f"⚠️ Block 2 capacity ({total_cap2}) < students ({n_students})!")
    if total_cap3 < n_students:
        st.warning(f"⚠️ Block 3 capacity ({total_cap3}) < students ({n_students})!")

    if st.button("▶ Run Assignment", type="primary", use_container_width=True):
        with st.spinner("Running assignment algorithm..."):
            df = st.session_state.students_raw.copy()
            results, logs = assign_students(cfg, df)
            st.session_state.results = results
            st.session_state.logs = logs
            st.session_state.summary = generate_summary(results, cfg)

        st.success("Assignment completed!")
        st.balloons()

    if st.session_state.results is not None:
        st.divider()
        st.subheader("Assignment Summary")
        s = st.session_state.summary
        if s:
            mcols = st.columns(5)
            mcols[0].metric("Total Students", s['total_students'])
            mcols[1].metric("3X (Normal all blocks)", s['type_3x'])
            mcols[2].metric("2X+A (ApL in Block 3)", s['type_2x_a'])
            mcols[3].metric("Partial", s['type_partial'])
            assigned = s['type_3x'] + s['type_2x_a']
            mcols[4].metric("Successfully Assigned", assigned)

            st.subheader("Choice Satisfaction by Block")
            for label in ['Block 1', 'Block 2', 'Block 3']:
                stats = s.get(label, {})
                cols = st.columns(6)
                cols[0].markdown(f"**{label}**")
                for i in range(1, 6):
                    d = stats.get(f'choice_{i}', {})
                    suffix = "st" if i == 1 else "nd" if i == 2 else "rd" if i == 3 else "th"
                    cols[i].metric(f"{i}{suffix}",
                                   d.get('count', 0))
                un = stats.get('unassigned', {})
                cols_c = st.columns([1] + [1] * 5)
                cols_c[0].markdown("")
                for i in range(1, 6):
                    d = stats.get(f'choice_{i}', {})
                    cols_c[i].caption(f"{d.get('pct', 0)}%")
                cols_c2 = st.columns([1] + [5])
                cols_c2[1].metric("Unassigned", un.get('count', 0))

    with st.expander("View Assignment Log", expanded=False):
        if st.session_state.logs:
            st.code("\n".join(st.session_state.logs[-200:]), language="text")
        else:
            st.info("No log entries yet.")


def render_results_page():
    st.header("Results")
    if st.session_state.results is None:
        st.warning("No results yet. Run the assignment first.")
        return

    cfg = st.session_state.config
    results = st.session_state.results
    s = st.session_state.summary

    st.subheader("Dashboard")
    mcols = st.columns(5)
    mcols[0].metric("Total Students", s['total_students'])
    mcols[1].metric("3X Students", s['type_3x'])
    mcols[2].metric("2X+A Students", s['type_2x_a'])
    assigned = s['type_3x'] + s['type_2x_a']
    mcols[3].metric("Assigned", assigned)
    pct_assigned = round(assigned / s['total_students'] * 100, 1) if s['total_students'] > 0 else 0
    mcols[4].metric("Assignment Rate", f"{pct_assigned}%")

    se_data = []
    for key, val in s['subject_enrollment'].items():
        se_data.append(val)
    if se_data:
        se_df = pd.DataFrame(se_data)
        se_df['pct'] = (se_df['enrolled'] / se_df['capacity'] * 100).round(1)

        fig = px.bar(
            se_df, x='subject', y=['enrolled', 'capacity'],
            barmode='group', facet_col='block', facet_col_wrap=1,
            title='Enrollment vs Capacity by Subject',
            labels={'value': 'Students', 'subject': 'Subject', 'variable': 'Metric'},
            color_discrete_map={'enrolled': '#1f77b4', 'capacity': '#ff7f0e'},
        )
        fig.update_layout(height=500)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Choice Satisfaction")
    sat_cols = st.columns(3)
    for i, label in enumerate(['Block 1', 'Block 2', 'Block 3']):
        stats = s.get(label, {})
        def _sfx(j): return "st" if j == 1 else "nd" if j == 2 else "rd" if j == 3 else "th"
        data = {
            'Choice': [f"{j}{_sfx(j)}" for j in range(1, 6)]
                      + ['Unassigned'],
            'Students': [stats.get(f'choice_{j}', {}).get('count', 0) for j in range(1, 6)]
                        + [stats.get('unassigned', {}).get('count', 0)],
        }
        dff = pd.DataFrame(data)
        fig = px.pie(dff, values='Students', names='Choice',
                     title=f'{label} Satisfaction',
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        sat_cols[i].plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Detailed Results")
    display_cols = [
        'Student Name', 'Class', 'Class_No', 'Marks',
        'Block1_Assigned', 'Block2_Assigned', 'Block3_Assigned',
        'Student_Type', 'B1_Choice_Level', 'B2_Choice_Level', 'B3_Choice_Level',
    ]
    display = results[display_cols].copy()
    for col in ['B1_Choice_Level', 'B2_Choice_Level', 'B3_Choice_Level']:
        display[col] = display[col].map(
            lambda x: f"{x}st" if x == 1 else f"{x}nd" if x == 2 else f"{x}rd" if x == 3 else f"{x}th" if x >= 4 else "Unassigned"
        )

    st.dataframe(display, use_container_width=True, hide_index=True)

    csv = display.to_csv(index=False).encode('utf-8-sig')
    col1, col2 = st.columns(2)
    col1.download_button("📥 Download as CSV", data=csv,
                          file_name=f"elective_results_{cfg['academic_year']}.csv",
                          mime="text/csv")
    excel_bytes = export_results_to_bytes(results, cfg)
    col2.download_button("📥 Download as Excel (.xlsx)", data=excel_bytes,
                          file_name=f"elective_results_{cfg['academic_year']}.xlsx",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def main():
    st.sidebar.title("🎓 F3 Elective Assignment")
    st.sidebar.markdown("---")

    cfg = st.session_state.config
    if cfg.get('academic_year'):
        st.sidebar.markdown(f"**Year:** {cfg['academic_year']}")
    n_students = len(st.session_state.students_raw) if st.session_state.students_raw is not None else 0
    st.sidebar.markdown(f"**Students loaded:** {n_students}")
    has_results = st.session_state.results is not None
    st.sidebar.markdown(f"**Results:** {'✅ Ready' if has_results else '❌ Not run'}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Cloud Storage")
    if cloud_storage.is_configured():
        st.sidebar.success("🔗 GitHub connected")
        if st.session_state._cloud_loaded:
            st.sidebar.caption("Session auto-loaded from cloud")
        col1, col2 = st.sidebar.columns(2)
        if col1.button("💾 Save"):
            c, s, r, sm = (st.session_state.config,
                           st.session_state.students_raw,
                           st.session_state.results,
                           st.session_state.summary)
            ok, msg = cloud_storage.save_session(c, s, r, sm)
            if ok:
                st.sidebar.success(msg)
            else:
                st.sidebar.error(msg)
            st.rerun()
        if col2.button("📂 Load"):
            config, students, results, summary, msg = cloud_storage.load_session()
            if config is not None:
                st.session_state.config = config
                st.session_state.students_raw = students
                st.session_state.results = results
                st.session_state.summary = summary
                st.sidebar.success(msg)
            else:
                st.sidebar.warning(msg)
            st.rerun()
    else:
        st.sidebar.warning("☁️ Cloud not connected")
        st.sidebar.caption("Set GITHUB_TOKEN in Streamlit secrets to enable")

    st.sidebar.markdown("---")
    page = st.sidebar.radio(
        "Navigate",
        ["Configuration", "Data Import", "Run Assignment", "Results"],
        index=["Configuration", "Data Import", "Run Assignment", "Results"].index(
            st.session_state.get('page', 'Configuration')
        ),
    )
    st.session_state.page = page

    if page == "Configuration":
        render_config_page()
    elif page == "Data Import":
        render_import_page()
    elif page == "Run Assignment":
        render_run_page()
    elif page == "Results":
        render_results_page()


if __name__ == "__main__":
    main()
