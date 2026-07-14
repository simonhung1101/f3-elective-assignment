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


def _cap(config, block_num, subject):
    return config.get('capacities', {}).get(block_num, {}).get(subject, 25)


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


def _resolve_pair(students, a_subjs, b_subjs, a_pref_cols, b_pref_cols,
                  a_col, b_col, a_label, b_label,
                  repeated, all_unique, logs):
    mask = (students[a_col] == repeated) & (students[b_col] == repeated)
    for idx in students[mask].index:
        row = students.loc[idx]
        ap = row[a_pref_cols].values
        bp = row[b_pref_cols].values

        a_fb = None
        b_fb = None
        for rank in range(1, 6):
            if a_fb is None:
                c = [a_subjs[i] for i, p in enumerate(ap) if p == rank and a_subjs[i] != repeated]
                if c:
                    a_fb = c[0]
            if b_fb is None:
                c = [b_subjs[i] for i, p in enumerate(bp) if p == rank and b_subjs[i] != repeated]
                if c:
                    b_fb = c[0]

        if a_fb and b_fb:
            r1 = _get_overall_rank(row, a_fb, all_unique)
            r2 = _get_overall_rank(row, b_fb, all_unique)
            if r1 <= r2:
                students.loc[idx, a_col] = a_fb
                students.loc[idx, b_col] = repeated
                logs.append(f"CONFLICT: {row['Student Name']}: {repeated} resolved, {a_label}->{a_fb}, {b_label}->{repeated}")
            else:
                students.loc[idx, a_col] = repeated
                students.loc[idx, b_col] = b_fb
                logs.append(f"CONFLICT: {row['Student Name']}: {repeated} resolved, {a_label}->{repeated}, {b_label}->{b_fb}")
        elif a_fb:
            students.loc[idx, a_col] = a_fb
            students.loc[idx, b_col] = repeated
            logs.append(f"CONFLICT: {row['Student Name']}: {repeated} partially resolved, {a_label}->{a_fb}, {b_label}->{repeated}")
        elif b_fb:
            students.loc[idx, a_col] = repeated
            students.loc[idx, b_col] = b_fb
            logs.append(f"CONFLICT: {row['Student Name']}: {repeated} partially resolved, {a_label}->{repeated}, {b_label}->{b_fb}")
        else:
            logs.append(f"CONFLICT: {row['Student Name']}: {repeated} cannot be resolved!")


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

    b1_subs = config['block_1']
    b2_subs = config['block_2']
    b3n = config['block_3_normal']
    b3a = config['block_3_apl']
    b3_all = b3n + b3a

    b1_pc = ['B1_Pref_1', 'B1_Pref_2', 'B1_Pref_3', 'B1_Pref_4', 'B1_Pref_5']
    b2_pc = ['B2_Pref_1', 'B2_Pref_2', 'B2_Pref_3', 'B2_Pref_4', 'B2_Pref_5']
    b3_pc = ['B3_Pref_1', 'B3_Pref_2', 'B3_Pref_3', 'B3_Pref_4', 'B3_Pref_5']

    all_unique = get_all_unique_normal(config)
    logs = []

    ri = config.get('repeated_subject', {})
    if isinstance(ri, dict):
        rep_name = ri.get('name', '')
        rep_blocks = ri.get('blocks', [])
    else:
        rep_name = ri
        rep_blocks = [1, 2]

    remaining_b1 = {s: _cap(config, 1, s) for s in b1_subs}
    students, l1 = _assign_block(students, b1_subs, b1_pc, remaining_b1, all_unique,
                                  'Block1_Assigned', 'B1_Choice_Level', 'B1')
    logs.extend(l1)

    remaining_b2 = {s: _cap(config, 2, s) for s in b2_subs}
    students, l2 = _assign_block(students, b2_subs, b2_pc, remaining_b2, all_unique,
                                  'Block2_Assigned', 'B2_Choice_Level', 'B2')
    logs.extend(l2)

    remaining_b3 = {s: _cap(config, 3, s) for s in b3_all}
    students, l3 = _assign_block(students, b3_all, b3_pc, remaining_b3, all_unique,
                                  'Block3_Assigned', 'B3_Choice_Level', 'B3A')
    logs.extend(l3)

    if b3a:
        apl_mask = students['Block3_Assigned'].isin(b3a)
        if apl_mask.any():
            apl_idx = students[apl_mask].index.tolist()
            max_m = max(students['Marks'].max(), 1)
            for idx in apl_idx:
                row = students.loc[idx]
                composite = (
                    (row['Marks'] / max_m * 100) * 0.6 +
                    (row.get('ApL_Preference_Score', 0) or 0) +
                    (row.get('Interview_Score', 0) or 0)
                )
                students.loc[idx, '_apl_composite'] = composite

            students['_apl_composite'] = students.get('_apl_composite', 0.0)
            apl_sorted = students.loc[apl_idx].sort_values('_apl_composite', ascending=False)

            rem_apl = {s: _cap(config, 3, s) for s in b3a}
            for idx in apl_sorted.index:
                row = students.loc[idx]
                prefs = row[b3_pc].values
                assigned = ''
                level = 0
                for rank in range(1, 6):
                    candidates = [b3_all[i] for i, p in enumerate(prefs) if p == rank]
                    if not candidates:
                        continue
                    for subj in candidates:
                        if subj in b3a and rem_apl.get(subj, 0) > 0:
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
        elif b3 in b3a:
            students.loc[idx, 'Student_Type'] = '2X+A'
        else:
            students.loc[idx, 'Student_Type'] = '3X'

    if rep_name:
        pair_map = {
            (1, 2): (b1_subs, b2_subs, b1_pc, b2_pc, 'Block1_Assigned', 'Block2_Assigned', 'B1', 'B2'),
            (1, 3): (b1_subs, b3_all, b1_pc, b3_pc, 'Block1_Assigned', 'Block3_Assigned', 'B1', 'B3'),
            (2, 3): (b2_subs, b3_all, b2_pc, b3_pc, 'Block2_Assigned', 'Block3_Assigned', 'B2', 'B3'),
        }
        if len(rep_blocks) == 2:
            key = tuple(sorted(rep_blocks))
            if key in pair_map:
                args = pair_map[key]
                _resolve_pair(students, *args, rep_name, all_unique, logs)

    return students, logs
