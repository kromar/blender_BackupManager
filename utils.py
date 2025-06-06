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
    """Calculates age string for a path."""
    if not path_to_scan or not os.path.isdir(path_to_scan):
        return "Age: N/A"
    try:
        latest_mtime = None
        # Use a generator expression for efficiency
        for dp, _, filenames in os.walk(path_to_scan):
            for f in filenames:
                try:
                    mtime = os.path.getmtime(os.path.join(dp, f))
                    if latest_mtime is None or mtime > latest_mtime:
                        latest_mtime = mtime
                except Exception:
                    continue
        if latest_mtime is None:
            return "Age: no data (empty)"
        delta = datetime.now() - datetime.fromtimestamp(latest_mtime)
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        # Use concise formatting
        if days > 0:
            backup_age = f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            backup_age = f"{hours}h {minutes}m"
        elif minutes > 0:
            backup_age = f"{minutes}m {seconds}s"
        else:
            backup_age = f"{seconds}s"
        return f"Age: {backup_age}"
    except Exception:
        return "Age: error"


def _calculate_path_size_str(path_to_scan):
    """Calculates size string for a path."""
    try:
        if not path_to_scan or not os.path.isdir(path_to_scan):
            return "Size: N/A"
        size = 0
        for dp, _, filenames in os.walk(path_to_scan):
            for f in filenames:
                try:
                    size += os.path.getsize(os.path.join(dp, f))
                except Exception:
                    continue
        return f"Size: {size / 1_000_000:.2f} MB" #  ({size:,} bytes)"
    except Exception:
        return "Size: error"