# Utility functions for preferences and paths
import bpy
import os
from .logger import debug
from .constants import SHARED_FOLDER_NAME

def get_addon_preferences():
    """
    Directly retrieves the addon's preferences.
    Assumes bpy.context and addon preferences are always accessible.
    """
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences


def get_paths_for_details(prefs_instance):
    """
    Collects all unique directory paths that might need age/size details displayed,
    based on the current addon preference settings.
    """
    paths = set()
    p = prefs_instance

    if not p.backup_path:
        return []

    if not p.advanced_mode:
        if p.blender_user_path:
            paths.add(p.blender_user_path)
        if p.active_blender_version:
            paths.add(os.path.join(p.backup_path, p.system_id, str(p.active_blender_version)))
    else:
        base_user_path_dir = os.path.dirname(p.blender_user_path) if p.blender_user_path else None
        if base_user_path_dir and p.backup_versions:
            paths.add(os.path.join(base_user_path_dir, p.backup_versions))
        if p.custom_version_toggle and p.custom_version:
            paths.add(os.path.join(p.backup_path, p.system_id, str(p.custom_version)))
        if p.restore_versions:
            paths.add(os.path.join(p.backup_path, p.system_id, p.restore_versions))

    final_paths = [path for path in paths if path]
    debug(f"get_paths_for_details collected {len(final_paths)} relevant paths: {final_paths}")
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


def build_ignore_patterns(prefs):
    """
    Centralized function to build ignore patterns for backup/restore based on preferences.
    Returns (ignore_backup, ignore_restore) lists.
    """
    import re
    ignore_backup = []
    ignore_restore = []
    pattern_list = [x for x in re.split(',|\s+', getattr(prefs, 'ignore_files', '')) if x]
    for item in pattern_list:
        ignore_backup.append(item)
        ignore_restore.append(item)
    # Add conditional ignores
    if not getattr(prefs, 'backup_bookmarks', True):
        ignore_backup.append('bookmarks.txt')
    if not getattr(prefs, 'restore_bookmarks', True):
        ignore_restore.append('bookmarks.txt')
    if not getattr(prefs, 'backup_recentfiles', True):
        ignore_backup.append('recent-files.txt')
    if not getattr(prefs, 'restore_recentfiles', True):
        ignore_restore.append('recent-files.txt')
    if not getattr(prefs, 'backup_startup_blend', True):
        ignore_backup.append('startup.blend')
    if not getattr(prefs, 'restore_startup_blend', True):
        ignore_restore.append('startup.blend')
    if not getattr(prefs, 'backup_userpref_blend', True):
        ignore_backup.append('userpref.blend')
    if not getattr(prefs, 'restore_userpref_blend', True):
        ignore_restore.append('userpref.blend')
    if not getattr(prefs, 'backup_workspaces_blend', True):
        ignore_backup.append('workspaces.blend')
    if not getattr(prefs, 'restore_workspaces_blend', True):
        ignore_restore.append('workspaces.blend')
    if not getattr(prefs, 'backup_cache', True):
        ignore_backup.append('cache')
    if not getattr(prefs, 'restore_cache', True):
        ignore_restore.append('cache')
    if not getattr(prefs, 'backup_datafile', True):
        ignore_backup.append('datafiles')
    if not getattr(prefs, 'restore_datafile', True):
        ignore_restore.append('datafiles')
    if not getattr(prefs, 'backup_addons', True):
        ignore_backup.append('addons')
    if not getattr(prefs, 'restore_addons', True):
        ignore_restore.append('addons')
    if not getattr(prefs, 'backup_extensions', True):
        ignore_backup.append('extensions')
    if not getattr(prefs, 'restore_extensions', True):
        ignore_restore.append('extensions')
    if not getattr(prefs, 'backup_presets', True):
        ignore_backup.append('presets')
    if not getattr(prefs, 'restore_presets', True):
        ignore_restore.append('presets')
    return ignore_backup, ignore_restore
