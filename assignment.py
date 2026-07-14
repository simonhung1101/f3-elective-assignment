import pandas as pd


def get_all_unique_normal(config):
    b1 = config['block_1']
    b2 = config['block_2']
    b3n = config['block_3_normal']
    all_n = list(b1)
    for s in b2:
        if s not in all_n:
            all_n.append(s)
    for s in b3n:
        if s not in all_n:
            all_n.append(s)
    return all_n


def _get_overall_rank(row, subject_name, all_normal):
    if subject_name in all_normal:
        pos = all_normal.index(subject_name)
        col = f'Overall_Pref_{pos + 1}'
        val = row.get(col)
        if pd.notna(val):
            return int(val)
    return 99


def _assign_block(students, subjects, pref_cols, remaining, all_unique,
                  assign_col, choice_col, log_prefix):
    logs = []
    for idx in students.index:
        row = students.loc[idx]
        prefs = row[pref_cols].values
        assigned = ''
        level = 0

        for rank in range(1, 6):
            candidates = [subjects[i] for i, p in enumerate(prefs) if p == rank]
            if not candidates:
                continue
            candidates.sort(key=lambda s: _get_overall_rank(row, s, all_unique))
            for subj in candidates:
                if remaining.get(subj, 0) > 0:
                    assigned = subj
                    remaining[subj] -= 1
                    level = rank
                    logs.append(f"{log_prefix}: {row['Student Name']} -> {subj} (choice #{rank})")
                    break
            if assigned:
                break

        if not assigned:
            logs.append(f"{log_prefix}: {row['Student Name']} -> UNASSIGNED")

        students.loc[idx, assign_col] = assigned
        students.loc[idx, choice_col] = level

    return students, logs


def assign_students(config, students_df):
    students = students_df.copy()

    sort_cols = ['Marks', 'Class', 'Class_No']
    students = students.sort_values(
        by=sort_cols,
        ascending=[False] + [True] * (len(sort_cols) - 1)
    ).reset_index(drop=True)

    students['Block1_Assigned'] = ''
    students['Block2_Assigned'] = ''
    students['Block3_Assigned'] = ''
    students['B1_Choice_Level'] = 0
    students['B2_Choice_Level'] = 0
    students['B3_Choice_Level'] = 0
    students['Student_Type'] = ''

    b1_subjects = config['block_1']
    b2_subjects = config['block_2']
    b3_normal = config['block_3_normal']
    b3_apl = config['block_3_apl']
    b3_all = b3_normal + b3_apl
    repeated = config.get('repeated_subject', '')

    b1_pref_cols = ['B1_Pref_1', 'B1_Pref_2', 'B1_Pref_3', 'B1_Pref_4', 'B1_Pref_5']
    b2_pref_cols = ['B2_Pref_1', 'B2_Pref_2', 'B2_Pref_3', 'B2_Pref_4', 'B2_Pref_5']
    b3_pref_cols = ['B3_Pref_1', 'B3_Pref_2', 'B3_Pref_3', 'B3_Pref_4', 'B3_Pref_5']

    all_unique = get_all_unique_normal(config)
    logs = []

    caps = config['capacities']

    remaining_b1 = {s: caps.get(s, 25) for s in b1_subjects}
    students, l1 = _assign_block(students, b1_subjects, b1_pref_cols,
                                  remaining_b1, all_unique,
                                  'Block1_Assigned', 'B1_Choice_Level', 'B1')
    logs.extend(l1)

    remaining_b2 = {s: caps.get(s, 25) for s in b2_subjects}
    students, l2 = _assign_block(students, b2_subjects, b2_pref_cols,
                                  remaining_b2, all_unique,
                                  'Block2_Assigned', 'B2_Choice_Level', 'B2')
    logs.extend(l2)

    remaining_b3 = {s: caps.get(s, 25) for s in b3_all}
    students, l3 = _assign_block(students, b3_all, b3_pref_cols,
                                  remaining_b3, all_unique,
                                  'Block3_Assigned', 'B3_Choice_Level', 'B3A')
    logs.extend(l3)

    if b3_apl:
        apl_mask = students['Block3_Assigned'].isin(b3_apl)
        if apl_mask.any():
            apl_idx = students[apl_mask].index.tolist()

            max_m = max(students['Marks'].max(), 1)
            for idx in apl_idx:
                row = students.loc[idx]
                composite = (
                    (row['Marks'] / max_m * 100) * 0.6 +
                    (row.get('ApL_Preference_Score', 0) or 0) * 0.1 +
                    (row.get('Interview_Score', 0) or 0) * 0.3
                )
                students.loc[idx, '_apl_composite'] = composite

            students['_apl_composite'] = students.get('_apl_composite', 0.0)
            apl_sorted = students.loc[apl_idx].sort_values('_apl_composite', ascending=False)

            rem_apl = {s: caps.get(s, 25) for s in b3_apl}
            for idx in apl_sorted.index:
                row = students.loc[idx]
                prefs = row[b3_pref_cols].values
                assigned = ''
                level = 0

                for rank in range(1, 6):
                    candidates = [b3_all[i] for i, p in enumerate(prefs) if p == rank]
                    if not candidates:
                        continue
                    for subj in candidates:
                        if subj in b3_apl and rem_apl.get(subj, 0) > 0:
                            assigned = subj
                            rem_apl[subj] -= 1
                            level = rank
                            logs.append(
                                f"B3B: {row['Student Name']} -> {subj} (choice #{rank}, "
                                f"composite: {students.loc[idx, '_apl_composite']:.1f})"
                            )
                            break
                    if assigned:
                        break

                students.loc[idx, 'Block3_Assigned'] = assigned
                students.loc[idx, 'B3_Choice_Level'] = level

            students.drop(columns=['_apl_composite'], inplace=True, errors='ignore')

    for idx in students.index:
        b3 = students.loc[idx, 'Block3_Assigned']
        b1 = students.loc[idx, 'Block1_Assigned']
        b2 = students.loc[idx, 'Block2_Assigned']
        if not b1 or not b2 or not b3:
            students.loc[idx, 'Student_Type'] = 'Partial'
        elif b3 in b3_apl:
            students.loc[idx, 'Student_Type'] = '2X+A'
        else:
            students.loc[idx, 'Student_Type'] = '3X'

    if repeated and repeated in b1_subjects and repeated in b2_subjects:
        conflict_mask = (
            (students['Block1_Assigned'] == repeated) &
            (students['Block2_Assigned'] == repeated)
        )
        for idx in students[conflict_mask].index:
            row = students.loc[idx]
            b1p = row[b1_pref_cols].values
            b2p = row[b2_pref_cols].values

            b1_fb = None
            b2_fb = None
            for rank in range(1, 6):
                if b1_fb is None:
                    c = [b1_subjects[i] for i, p in enumerate(b1p)
                         if p == rank and b1_subjects[i] != repeated]
                    if c:
                        b1_fb = c[0]
                if b2_fb is None:
                    c = [b2_subjects[i] for i, p in enumerate(b2p)
                         if p == rank and b2_subjects[i] != repeated]
                    if c:
                        b2_fb = c[0]

            if b1_fb and b2_fb:
                r1 = _get_overall_rank(row, b1_fb, all_unique)
                r2 = _get_overall_rank(row, b2_fb, all_unique)
                if r1 <= r2:
                    students.loc[idx, 'Block1_Assigned'] = b1_fb
                    students.loc[idx, 'Block2_Assigned'] = repeated
                    logs.append(
                        f"CONFLICT: {row['Student Name']}: {repeated} conflict resolved, "
                        f"B1->{b1_fb}, B2->{repeated}"
                    )
                else:
                    students.loc[idx, 'Block1_Assigned'] = repeated
                    students.loc[idx, 'Block2_Assigned'] = b2_fb
                    logs.append(
                        f"CONFLICT: {row['Student Name']}: {repeated} conflict resolved, "
                        f"B1->{repeated}, B2->{b2_fb}"
                    )
            elif b1_fb:
                students.loc[idx, 'Block1_Assigned'] = b1_fb
                students.loc[idx, 'Block2_Assigned'] = repeated
                logs.append(
                    f"CONFLICT: {row['Student Name']}: {repeated} partially resolved, "
                    f"B1->{b1_fb}, B2->{repeated}"
                )
            elif b2_fb:
                students.loc[idx, 'Block1_Assigned'] = repeated
                students.loc[idx, 'Block2_Assigned'] = b2_fb
                logs.append(
                    f"CONFLICT: {row['Student Name']}: {repeated} partially resolved, "
                    f"B1->{repeated}, B2->{b2_fb}"
                )
            else:
                logs.append(
                    f"CONFLICT: {row['Student Name']}: {repeated} cannot be resolved!"
                )

    return students, logs
