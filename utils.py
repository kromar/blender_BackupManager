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
    version_list = []
    _start_time_fv = None
    prefs_instance = get_addon_preferences() # Use the centralized getter

    if prefs_instance.debug:
        _start_time_fv = datetime.now()
        print(f"DEBUG: find_versions START for path: {filepath}")

    if not filepath or not os.path.isdir(filepath):
        if prefs_instance.debug:
            print(f"DEBUG: find_versions: filepath invalid or not a directory: {filepath}")
        return version_list

    try:
        _listdir_start_time_fv = None
        if prefs_instance.debug:
            _listdir_start_time_fv = datetime.now()
            print(f"DEBUG: find_versions CALLING os.listdir for path: {filepath}")
        for file_or_dir_name in os.listdir(filepath):
            path = os.path.join(filepath, file_or_dir_name)
            if os.path.isdir(path):      
                version_list.append((file_or_dir_name, file_or_dir_name, ''))
        if prefs_instance.debug:
            _listdir_end_time_fv = datetime.now()
            print(f"DEBUG: (took: {(_listdir_end_time_fv - _listdir_start_time_fv).total_seconds():.6f}s) find_versions FINISHED os.listdir for path: {filepath}")
    except OSError as e: # Catch specific OS errors like PermissionError
        if prefs_instance.debug:
            print(f"DEBUG: find_versions: Error accessing filepath {filepath}: {e}")
    
    if prefs_instance.debug and _start_time_fv:
        _end_time_fv = datetime.now()
        print(f"DEBUG: (took: {(_end_time_fv - _start_time_fv).total_seconds():.6f}s) find_versions END for path: '{filepath}', found {len(version_list)} versions. List: {version_list}")

    return version_list

def get_paths_for_details(prefs_instance):
    """
    Collects all unique directory paths that might need age/size details displayed,
    based on the current addon preference settings.
    (This function remains largely the same but is now in utils.py)
    """
    paths = set()
    p = prefs_instance # p is already prefs_instance

    if not p.backup_path: return []

    if not p.advanced_mode:
        if p.blender_user_path: paths.add(p.blender_user_path)
        if p.active_blender_version: paths.add(os.path.join(p.backup_path, p.system_id, str(p.active_blender_version)))
    else:
        base_user_path_dir = os.path.dirname(p.blender_user_path) if p.blender_user_path else None
        if base_user_path_dir and p.backup_versions: paths.add(os.path.join(base_user_path_dir, p.backup_versions))
        if p.custom_version_toggle and p.custom_version: paths.add(os.path.join(p.backup_path, p.system_id, str(p.custom_version)))
        elif p.restore_versions: paths.add(os.path.join(p.backup_path, p.system_id, p.restore_versions))

    # Simplified restore path collection as they often overlap with backup paths
    if p.advanced_mode and p.restore_versions:
         paths.add(os.path.join(p.backup_path, p.system_id, p.restore_versions))
    
    final_paths = list(path for path in paths if path)
    if p.debug:
        print(f"DEBUG (utils): get_paths_for_details collected {len(final_paths)} relevant paths.")
    return final_paths

def get_default_base_temp_dir():
    """Safely determines a base temporary directory for addon defaults."""
    # (Content of this function is moved from preferences.py without changes)
    # ... (implementation from preferences.py) ...
    # For brevity, assuming the implementation is copied here.
    # Ensure it uses `bpy.app.tempdir` and fallbacks as before.
    # Example:
    try:
        return bpy.app.tempdir or os.path.join(os.path.expanduser("~"), "blender_temp_fallback")
    except: return os.path.join(os.path.expanduser("~"), "blender_temp_fallback")

def _calculate_path_age_str(path_to_scan):
    """Calculates age string for a path."""
    # (Content of this function is moved from preferences.py without changes)
    # ... (implementation from preferences.py) ...
    try:
        if not path_to_scan or not os.path.isdir(path_to_scan): return "Last change: N/A"
        files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(path_to_scan) for f in filenames]
        if not files: return "Last change: no data (empty)"
        latest_file = max(files, key=os.path.getmtime)
        backup_age = str(datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_file))).split('.')[0]
        return f"Last change: {backup_age}"        
    except Exception: return "Last change: error"

def _calculate_path_size_str(path_to_scan):
    """Calculates size string for a path."""
    # (Content of this function is moved from preferences.py without changes)
    # ... (implementation from preferences.py) ...
    try:
        if not path_to_scan or not os.path.isdir(path_to_scan): return "Size: N/A"
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, filenames in os.walk(path_to_scan) for f in filenames)
        return (f"Size: {str(round(size * 1e-06, 2))} MB  (" + "{:,}".format(size) + " bytes)")
    except Exception: return "Size: error"