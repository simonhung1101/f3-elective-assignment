import json
import pandas as pd
from github import Github, GithubException

import streamlit as st


def _get_repo():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets.get("GITHUB_REPO")
        if not repo_name:
            return None
        g = Github(token)
        return g.get_repo(repo_name)
    except Exception:
        return None


def is_configured():
    try:
        return bool(st.secrets.get("GITHUB_TOKEN")) and bool(st.secrets.get("GITHUB_REPO"))
    except Exception:
        return False


def _save_json_file(repo, path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2)
    try:
        contents = repo.get_contents(path)
        repo.update_file(path, f"Update {path}", content, contents.sha)
    except GithubException:
        repo.create_file(path, f"Create {path}", content)


def save_session(config, students_df, results_df, summary):
    repo = _get_repo()
    if repo is None:
        return False, "Cloud storage not configured (missing GitHub token)"

    try:
        _save_json_file(repo, "sessions/config.json", config)

        if students_df is not None:
            students_data = json.loads(
                students_df.to_json(orient="records", force_ascii=False)
            )
            _save_json_file(repo, "sessions/students.json", students_data)

        if results_df is not None:
            results_data = json.loads(
                results_df.to_json(orient="records", force_ascii=False)
            )
            _save_json_file(repo, "sessions/results.json", results_data)

        if summary is not None:
            _save_json_file(repo, "sessions/summary.json", summary)

        return True, "Session saved to cloud successfully"
    except Exception as e:
        return False, f"Save failed: {str(e)}"


def load_session():
    repo = _get_repo()
    if repo is None:
        return None, None, None, None, "Cloud storage not configured"

    config = None
    students = None
    results = None
    summary = None

    paths = {
        "sessions/config.json": "config",
        "sessions/students.json": "students",
        "sessions/results.json": "results",
        "sessions/summary.json": "summary",
    }

    for path, key in paths.items():
        try:
            contents = repo.get_contents(path)
            data = json.loads(contents.decoded_content)
            if key == "config":
                config = data
            elif key == "students":
                students = pd.DataFrame(data)
            elif key == "results":
                results = pd.DataFrame(data)
            elif key == "summary":
                summary = data
        except GithubException:
            pass

    if config is None:
        return None, None, None, None, "No saved session found in cloud"

    return config, students, results, summary, "Session loaded from cloud"
