import json
from pathlib import Path

# Progress tracking
PROGRESS_FILE = "../data/processed/progress.json"


def load_progress():
    """Load processed post IDs from progress file"""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE) as f:
            return set(json.load(f))
    return set()


def save_progress(processed_ids: set):
    """Save processed post IDs to progress file"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(list(processed_ids), f)
