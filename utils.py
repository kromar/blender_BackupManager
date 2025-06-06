# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
import os
from datetime import datetime

# For profiling purposes, if needed
import subprocess
import sys

def ensure_pyinstrument_installed():
    try:
        import pyinstrument
        return True
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "pyinstrument"])
            import pyinstrument
            return True
        except Exception as e:
            print(f"Failed to install pyinstrument: {e}")
            return False

if ensure_pyinstrument_installed():
    from pyinstrument import Profiler
else:
    Profiler = None



def get_addon_preferences():
    """
    Directly retrieves the addon's preferences.
    Assumes bpy.context and addon preferences are always accessible.
    """
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences

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


def get_paths_for_details(prefs_instance):
    """
    Collects all unique directory paths that might need age/size details displayed,
    based on the current addon preference settings.
    """
    paths = set()
    p = prefs_instance

    if not p.backup_path:
        return []

    # Non-advanced mode
    if not p.advanced_mode:
        if p.blender_user_path:
            paths.add(p.blender_user_path)
        if p.active_blender_version:
            paths.add(os.path.join(p.backup_path, p.system_id, str(p.active_blender_version)))
    else:
        # Advanced mode
        base_user_path_dir = os.path.dirname(p.blender_user_path) if p.blender_user_path else None
        if base_user_path_dir and p.backup_versions:
            paths.add(os.path.join(base_user_path_dir, p.backup_versions))
        if p.custom_version_toggle and p.custom_version:
            paths.add(os.path.join(p.backup_path, p.system_id, str(p.custom_version)))
        if p.restore_versions:
            paths.add(os.path.join(p.backup_path, p.system_id, p.restore_versions))

    final_paths = [path for path in paths if path]
    if p.debug:
        print(f"DEBUG (utils): get_paths_for_details collected {len(final_paths)} relevant paths: {final_paths}")
    return final_paths


def get_default_base_temp_dir():
    """Safely determines a base temporary directory for addon defaults, 
        using Blender user preferences if available. 
        Falls back to a user home directory if not set.
    """
    try:
        temp_path = bpy.context.preferences.filepaths.temporary_directory
        if temp_path:
            return temp_path
        return bpy.app.tempdir or os.path.join(os.path.expanduser("~"), "blender_temp_fallback")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "blender_temp_fallback")
        

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
    Adds debug output for troubleshooting scenarios where size is unexpectedly zero.
    """
    try:
        debug = False
        try:
            prefs = get_addon_preferences()
            debug = getattr(prefs, 'debug', False)
        except Exception:
            pass
        # --- Fix: Print the actual paths and check for typos or path issues ---
        if backup_path and version_name:
            system_size = 0
            shared_size = 0
            # Print the actual values for troubleshooting
            if debug:
                print(f"[DEBUG] backup_path: {backup_path}")
                print(f"[DEBUG] system_id: {system_id}")
                print(f"[DEBUG] version_name: {version_name}")
            # System path
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
                            if debug:
                                print(f"[DEBUG] System file: {fp} size={sz}")
                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Error reading system file: {fp} err={e}")
                            continue
            # Shared path
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
                            if debug:
                                print(f"[DEBUG] Shared file: {fp} size={sz}")
                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Error reading shared file: {fp} err={e}")
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
                            if debug:
                                print(f"[DEBUG] Fallback file: {fp} size={sz}")
                        except Exception as e:
                            if debug:
                                print(f"[DEBUG] Error reading fallback file: {fp} err={e}")
                            continue
            if debug:
                print(f"[DEBUG] Fallback size: {size}")
            return f"Size {size / 1_000_000:.0f}mb (System {size / 1_000_000:.0f}mb + Shared 0mb)"
    except Exception as e:
        print(f"[DEBUG] Exception in _calculate_path_size_str: {e}")
        return "Size 0mb (System 0mb + Shared 0mb)"


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
