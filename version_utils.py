# Utility functions for version discovery
import os
from datetime import datetime
from .preferences_utils import get_addon_preferences

def find_versions(filepath):
    """
    Returns a list of (name, name, '') tuples for each subdirectory in filepath.
    """
    prefs = get_addon_preferences()
    debug = getattr(prefs, "debug", False)
    version_list = []

    if debug:
        start_time = datetime.now()
        print(f"DEBUG: find_versions START for path: {filepath}")

    if not filepath or not os.path.isdir(filepath):
        if debug:
            print(f"DEBUG: find_versions: filepath invalid or not a directory: {filepath}")
        return version_list

    try:
        entries = os.listdir(filepath)
        for entry in entries:
            path = os.path.join(filepath, entry)
            if os.path.isdir(path):
                version_list.append((entry, entry, ''))
        if debug:
            print(f"DEBUG: find_versions found {len(version_list)} versions in '{filepath}'. List: {version_list}")
    except OSError as e:
        if debug:
            print(f"DEBUG: find_versions: Error accessing filepath {filepath}: {e}")

    if debug:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"DEBUG: (took: {elapsed:.6f}s) find_versions END for path: '{filepath}'")

    return version_list
