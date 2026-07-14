import json
import io
import pandas as pd
from datetime import datetime

from assignment import get_all_unique_normal


def get_default_config():
    return {
        "academic_year": datetime.now().strftime("%Y-%m"),
        "block_1": ["", "", "", "", ""],
        "block_2": ["", "", "", "", ""],
        "block_3_normal": ["", ""],
        "block_3_apl": ["", "", ""],
        "repeated_subject": "",
        "capacities": {},
    }


def validate_config(config):
    errors = []
    if not config.get("academic_year"):
        errors.append("Academic year is required.")
    for b in ["block_1", "block_2"]:
        for i, s in enumerate(config.get(b, [])):
            if not s:
                errors.append(f"{b.title()} has empty subject at position {i + 1}.")
    for i, s in enumerate(config.get("block_3_normal", [])):
        if not s:
            errors.append(f"Block 3 normal subject at position {i + 1} is empty.")
    for i, s in enumerate(config.get("block_3_apl", [])):
        if not s:
            errors.append(f"Block 3 ApL subject at position {i + 1} is empty.")

    repeated = config.get("repeated_subject", "")
    if repeated and repeated not in config.get("block_1", []) + config.get("block_2", []):
        errors.append(f"Repeated subject '{repeated}' not found in Block 1 or Block 2.")
    return errors


def save_config_json(config, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_config_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_template_bytes(config):
    all_unique = get_all_unique_normal(config)
    b1 = config['block_1']
    b2 = config['block_2']
    b3_all = config['block_3_normal'] + config['block_3_apl']

    cols = ["Student Name", "Class", "Class_No", "Marks"]
    b1_pref_cols = [f"B1_Pref_{i + 1}" for i in range(5)]
    b2_pref_cols = [f"B2_Pref_{i + 1}" for i in range(5)]
    b3_pref_cols = [f"B3_Pref_{i + 1}" for i in range(5)]
    overall_cols = [f"Overall_Pref_{i + 1}" for i in range(len(all_unique))]
    extra_cols = ["ApL_Preference_Score", "Interview_Score"]

    all_cols = cols + b1_pref_cols + b2_pref_cols + b3_pref_cols + overall_cols + extra_cols
    df = pd.DataFrame(columns=all_cols)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)

        mapping_data = []
        mapping_data.append(["Subject Mapping Reference"])
        mapping_data.append([])
        mapping_data.append(["Block 1:"])
        for i, s in enumerate(b1):
            mapping_data.append([f"  B1_Pref_{i + 1}", s])
        mapping_data.append([])
        mapping_data.append(["Block 2:"])
        for i, s in enumerate(b2):
            mapping_data.append([f"  B2_Pref_{i + 1}", s])
        mapping_data.append([])
        mapping_data.append(["Block 3:"])
        for i, s in enumerate(b3_all):
            mapping_data.append([f"  B3_Pref_{i + 1}", s])
        mapping_data.append([])
        mapping_data.append(["Overall Preferences (11 unique normal subjects):"])
        for i, s in enumerate(all_unique):
            mapping_data.append([f"  Overall_Pref_{i + 1}", s])
        mapping_data.append([])
        mapping_data.append(["Notes:"])
        mapping_data.append(["- Preference columns expect a rank (1 = most preferred, 5 = least preferred)"])
        mapping_data.append(["- Each rank value can only be used once within a block"])
        mapping_data.append(["- Overall_Pref columns expect ranks 1-11 across all 11 normal subjects"])
        mapping_data.append(["- ApL_Preference_Score and Interview_Score should be 0-100"])

        pd.DataFrame(mapping_data).to_excel(writer, sheet_name='Instructions', index=False, header=False)

    output.seek(0)
    return output


def parse_uploaded_excel(file_bytes, config):
    df = pd.read_excel(file_bytes, sheet_name='Data')
    if 'Class No.' in df.columns and 'Class_No' not in df.columns:
        df.rename(columns={'Class No.': 'Class_No'}, inplace=True)
    return df


def validate_imported_data(df, config):
    errors = []
    required = ["Student Name", "Class", "Class_No", "Marks"]
    for col in required:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    b1_pref_cols = [f"B1_Pref_{i + 1}" for i in range(5)]
    b2_pref_cols = [f"B2_Pref_{i + 1}" for i in range(5)]
    b3_pref_cols = [f"B3_Pref_{i + 1}" for i in range(5)]
    all_unique = get_all_unique_normal(config)
    overall_cols = [f"Overall_Pref_{i + 1}" for i in range(len(all_unique))]

    for cols, label in [(b1_pref_cols, "Block 1"), (b2_pref_cols, "Block 2"),
                         (b3_pref_cols, "Block 3"), (overall_cols, "Overall")]:
        for c in cols:
            if c not in df.columns:
                errors.append(f"Missing column: {c} ({label})")

    if "ApL_Preference_Score" not in df.columns:
        errors.append("Missing column: ApL_Preference_Score")
    if "Interview_Score" not in df.columns:
        errors.append("Missing column: Interview_Score")

    if errors:
        return errors

    for idx, row in df.iterrows():
        name = row.get("Student Name", f"Row {idx + 1}")
        if pd.isna(row.get("Student Name")) or str(row["Student Name"]).strip() == "":
            errors.append(f"Row {idx + 1}: Student Name is missing.")
            continue
        if pd.isna(row.get("Class")) or str(row["Class"]).strip() == "":
            errors.append(f"Row {idx + 1} ({name}): Class is missing.")
        if pd.isna(row.get("Class_No")):
            errors.append(f"Row {idx + 1} ({name}): Class_No is missing.")
        if pd.isna(row.get("Marks")):
            errors.append(f"Row {idx + 1} ({name}): Marks is missing.")

        all_pref_cols = b1_pref_cols + b2_pref_cols + b3_pref_cols
        for col in all_pref_cols:
            val = row.get(col)
            if pd.isna(val):
                errors.append(f"Row {idx + 1} ({name}): {col} is missing.")
            elif int(val) < 1 or int(val) > 5:
                errors.append(f"Row {idx + 1} ({name}): {col} must be 1-5.")

        for col in overall_cols:
            val = row.get(col)
            if pd.isna(val):
                errors.append(f"Row {idx + 1} ({name}): {col} is missing.")
            elif int(val) < 1 or int(val) > len(all_unique):
                errors.append(f"Row {idx + 1} ({name}): {col} must be 1-{len(all_unique)}.")

    return errors


def export_results_to_bytes(results_df, config):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        results_df.to_excel(writer, sheet_name='Results', index=False)
    output.seek(0)
    return output


def generate_summary(results_df, config):
    summary = {}
    total = len(results_df)
    summary['total_students'] = total

    types = results_df['Student_Type'].value_counts().to_dict()
    summary['type_3x'] = types.get('3X', 0)
    summary['type_2x_a'] = types.get('2X+A', 0)
    summary['type_partial'] = types.get('Partial', 0)

    for block, col, label in [
        (1, 'B1_Choice_Level', 'Block 1'),
        (2, 'B2_Choice_Level', 'Block 2'),
        (3, 'B3_Choice_Level', 'Block 3'),
    ]:
        stats = {}
        for level in range(1, 6):
            count = int((results_df[col] == level).sum())
            pct = round(count / total * 100, 1) if total > 0 else 0
            stats[f"choice_{level}"] = {"count": count, "pct": pct}
        unassigned = int((results_df[col] == 0).sum())
        stats["unassigned"] = {"count": unassigned, "pct": round(unassigned / total * 100, 1) if total > 0 else 0}
        summary[label] = stats

    b1_subjects = config['block_1']
    b2_subjects = config['block_2']
    b3_all = config['block_3_normal'] + config['block_3_apl']
    caps = config['capacities']

    subject_enrollment = {}
    for block_label, subjects, assign_col in [
        ("Block 1", b1_subjects, 'Block1_Assigned'),
        ("Block 2", b2_subjects, 'Block2_Assigned'),
        ("Block 3", b3_all, 'Block3_Assigned'),
    ]:
        counts = results_df[assign_col].value_counts().to_dict()
        for s in subjects:
            subject_enrollment[f"{block_label}_{s}"] = {
                "subject": s,
                "block": block_label,
                "enrolled": counts.get(s, 0),
                "capacity": caps.get(s, 25)
            }
    summary['subject_enrollment'] = subject_enrollment

    return summary
