# Utility functions for calculating path age and size
import os
from datetime import datetime
from .preferences_utils import get_addon_preferences

def _calculate_path_age_str(path_to_scan):
    """
    Calculates the age string for a path (single folder). Always returns 'Last change: ...' for UI consistency.
    """
    if not path_to_scan or not os.path.isdir(path_to_scan):
        return "Last change: N/A"
    try:
        latest_mtime = None
        for dp, _, filenames in os.walk(path_to_scan):
            for f in filenames:
                try:
                    mtime = os.path.getmtime(os.path.join(dp, f))
                    if latest_mtime is None or mtime > latest_mtime:
                        latest_mtime = mtime
                except Exception:
                    continue
        if latest_mtime is None:
            return "Last change: N/A"
        return _format_age_string(latest_mtime)
    except Exception as e:
        prefs = None
        debug = False
        try:
            prefs = get_addon_preferences()
            debug = getattr(prefs, 'debug', False)
        except Exception:
            pass
        if debug:
            print(f"[DEBUG] Exception in _calculate_path_age_str: {e}")
        return "Last change: error"


def _format_age_string(latest_mtime, prefix="Last change: "):
    """Helper to format the age string given a latest modification time."""
    if latest_mtime is None:
        return f"{prefix}N/A"
    delta = datetime.now() - datetime.fromtimestamp(latest_mtime)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if days > 0:
        backup_age = f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        backup_age = f"{hours}h {minutes}m"
    elif minutes > 0:
        backup_age = f"{minutes}m {seconds}s"
    else:
        backup_age = f"{seconds}s"
    return f"{prefix}{backup_age}"


def _calculate_path_age_str_combined(backup_path, system_id, version_name):
    """
    Calculates the most recent age string for a versioned folder, checking both system-specific and shared config folders.
    Always returns 'Last change: ...' for UI consistency.
    """
    try:
        prefs = None
        debug = False
        try:
            prefs = get_addon_preferences()
            debug = getattr(prefs, 'debug', False)
        except Exception:
            pass
        system_path = os.path.join(backup_path, system_id, version_name) if system_id else None
        shared_path = os.path.join(backup_path, 'SharedConfigs', version_name)
        latest_mtime = None
        # Check system path
        if system_path and os.path.isdir(system_path):
            for dp, _, filenames in os.walk(system_path):
                for f in filenames:
                    try:
                        mtime = os.path.getmtime(os.path.join(dp, f))
                        if latest_mtime is None or mtime > latest_mtime:
                            latest_mtime = mtime
                    except Exception:
                        continue
        # Check shared path
        if os.path.isdir(shared_path):
            for dp, _, filenames in os.walk(shared_path):
                for f in filenames:
                    try:
                        mtime = os.path.getmtime(os.path.join(dp, f))
                        if latest_mtime is None or mtime > latest_mtime:
                            latest_mtime = mtime
                    except Exception:
                        continue
        if latest_mtime is None:
            return "Last change: N/A"
        return _format_age_string(latest_mtime)
    except Exception as e:
        if debug:
            print(f"[DEBUG] Exception in _calculate_path_age_str_combined: {e}")
        return "Last change: error"


def _calculate_path_size_str(path_to_scan, backup_path=None, system_id=None, version_name=None):
    """Calculates size string for a path, summing both system-specific and shared config version folders if version_name is provided.
    Only prints summary debug output, not per-file details.
    """
    try:
        debug = False
        try:
            prefs = get_addon_preferences()
            debug = getattr(prefs, 'debug', False)
        except Exception:
            pass
        if backup_path and version_name:
            system_size = 0
            shared_size = 0
            if debug:
                print(f"[DEBUG] backup_path: {backup_path}")
                print(f"[DEBUG] system_id: {system_id}")
                print(f"[DEBUG] version_name: {version_name}")
            system_path = os.path.join(backup_path, system_id, version_name) if system_id else None
            if debug:
                print(f"[DEBUG] Checking system_path: {system_path} exists={os.path.isdir(system_path) if system_path else 'N/A'}")
            if system_path and os.path.isdir(system_path):
                for dp, _, filenames in os.walk(system_path):
                    for f in filenames:
                        try:
                            fp = os.path.join(dp, f)
                            sz = os.path.getsize(fp)
                            system_size += sz
                        except Exception as e:
                            continue
            shared_path = os.path.join(backup_path, 'SharedConfigs', version_name)
            if debug:
                print(f"[DEBUG] Checking shared_path: {shared_path} exists={os.path.isdir(shared_path)}")
            if os.path.isdir(shared_path):
                for dp, _, filenames in os.walk(shared_path):
                    for f in filenames:
                        try:
                            fp = os.path.join(dp, f)
                            sz = os.path.getsize(fp)
                            shared_size += sz
                        except Exception as e:
                            continue
            total_size = system_size + shared_size
            if debug:
                print(f"[DEBUG] Final sizes: total={total_size} system={system_size} shared={shared_size}")
            return f"Size {total_size / 1_000_000:.0f}mb (System {system_size / 1_000_000:.0f}mb + Shared {shared_size / 1_000_000:.0f}mb)"
        else:
            size = 0
            if path_to_scan and os.path.isdir(path_to_scan):
                for dp, _, filenames in os.walk(path_to_scan):
                    for f in filenames:
                        try:
                            fp = os.path.join(dp, f)
                            sz = os.path.getsize(fp)
                            size += sz
                        except Exception as e:
                            continue
            if debug:
                print(f"[DEBUG] Fallback size: {size}")
            return f"Size {size / 1_000_000:.0f}mb (System {size / 1_000_000:.0f}mb + Shared 0mb)"
    except Exception as e:
        print(f"[DEBUG] Exception in _calculate_path_size_str: {e}")
        return "Size 0mb (System 0mb + Shared 0mb)"
