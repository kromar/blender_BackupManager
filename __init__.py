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
from bpy.types import Context
import os
import time
from datetime import datetime # Added for debug timestamps

# --- Module Imports ---
from . import preferences
from . import core
from . import ui
from .preferences_utils import get_addon_preferences
from .debug_utils import get_prefs_and_debug
from .logger import debug

bl_info = {
    "name": "Backup Manager",
    "description": "Backup and Restore your Blender configuration files",
    "author": "Daniel Grauer",
    "version": (1, 4, 0),
    "blender": (3, 0, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}

# Module-level list to keep track of classes registered by this addon instance.
_registered_classes = []

# --- Backup warning cache and next-check timestamp ---
_backup_warning_cache = {
    "show_backup_now": False,
    "backup_missing": False,
    "backup_age_days": None,
    "version_name": "",
}
_next_backup_check_time = 0  # Timestamp for next allowed check

def get_prefs_for_init():
    """
    Directly retrieves the addon's preferences.
    Uses the centralized utility function.
    """
    return get_addon_preferences()


def _get_latest_backup_mtime(prefs):
    """
    Returns the latest backup modification time (as a timestamp) for the current system/version, or None if not found.
    """
    backup_path = prefs.backup_path
    system_id = prefs.system_id
    version_name = str(prefs.active_blender_version)
    system_path = os.path.join(backup_path, system_id, version_name) if system_id else None
    shared_path = os.path.join(backup_path, 'SharedConfigs', version_name)
    latest_mtime = None
    for path in [system_path, shared_path]:
        if path and os.path.isdir(path):
            for dp, _, filenames in os.walk(path):
                for f in filenames:
                    try:
                        mtime = os.path.getmtime(os.path.join(dp, f))
                        if latest_mtime is None or mtime > latest_mtime:
                            latest_mtime = mtime
                    except Exception:
                        continue
    return latest_mtime

def update_backup_warning_cache(force=False):
    """
    Updates the backup warning cache if the reminder duration has expired or if forced.
    """
    global _backup_warning_cache, _next_backup_check_time
    now = time.time()
    if not force and now < _next_backup_check_time:
        return  # Not time to check yet

    show_backup_now = False
    backup_missing = False
    backup_age_days = None
    version_name = ""
    next_check_in = 86400  # Default: check again in 1 day if something goes wrong

    try:
        prefs_instance = get_prefs_for_init()
        if prefs_instance and hasattr(prefs_instance, 'backup_reminder_duration') and prefs_instance.backup_reminder:
            backup_path = prefs_instance.backup_path
            system_id = prefs_instance.system_id
            version_name = str(prefs_instance.active_blender_version)
            if backup_path:
                system_path = os.path.join(backup_path, system_id, version_name) if system_id else None
                system_exists = system_path and os.path.isdir(system_path)
                if not system_exists:
                    backup_missing = True
                    show_backup_now = True
                    next_check_in = 3600  # Check again in 1 hour if missing
                else:
                    latest_mtime = _get_latest_backup_mtime(prefs_instance)
                    if latest_mtime is not None:
                        age_seconds = now - latest_mtime
                        backup_age_days = age_seconds / 86400.0
                        if backup_age_days > prefs_instance.backup_reminder_duration:
                            show_backup_now = True
                            next_check_in = 3600  # Check again in 1 hour if overdue
                        else:
                            # Next check: when the duration will be exceeded
                            seconds_until_due = (prefs_instance.backup_reminder_duration * 86400) - age_seconds
                            next_check_in = max(60, seconds_until_due)  # At least 1 minute
    except Exception as e:
        debug(f"ERROR: Could not update backup warning cache: {e}")

    _backup_warning_cache = {
        "show_backup_now": show_backup_now,
        "backup_missing": backup_missing,
        "backup_age_days": backup_age_days,
        "version_name": version_name,
    }
    _next_backup_check_time = now + next_check_in

def topbar_warning_draw_fn(self, context: Context) -> None:
    """Draws the Backup Manager button in the TOPBAR header if needed."""
    layout = self.layout
    addon_prefs, _local_debug_active = get_prefs_and_debug()

    if addon_prefs is None:
        debug("ERROR: Backup Manager: topbar_warning_draw_fn: Addon preferences object is None. Cannot proceed.")
        return

    debug(f"DEBUG __init__.topbar_warning_draw_fn: Entered. Prefs {'obtained' if addon_prefs else 'NOT obtained'}. Debug: {_local_debug_active}. Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    # Ensure the ui module and the operator class are loaded
    if not hasattr(ui, 'OT_BackupManagerWindow'):
        debug("DEBUG __init__.topbar_warning_draw_fn: ui.OT_BackupManagerWindow missing. Skipping draw.")
        return
    op_idname = ui.OT_BackupManagerWindow.bl_idname
    # Check if the operator is actually registered and available in bpy.ops.bm
    if not hasattr(bpy.ops.bm, op_idname.split('.')[-1]):
        debug(f"DEBUG __init__.topbar_warning_draw_fn: Operator {op_idname} missing in bpy.ops.bm. Skipping draw.")
        return

    # --- Operation in Progress Indicator (PRIORITY) ---
    if addon_prefs and hasattr(addon_prefs, 'show_operation_progress') and addon_prefs.show_operation_progress:
        layout.operator(op_idname, text="Backup in Progress...", icon='COLORSET_09_VEC')
        layout.separator(factor=0.5)
        debug(f"DEBUG __init__.topbar_warning_draw_fn: Drawing 'Backup in Progress...' indicator.")
        return # If an operation is in progress, don't show other warnings from this function.
    else:
        debug(f"DEBUG __init__.topbar_warning_draw_fn: Condition for 'Backup in Progress...' NOT met. Proceeding to age warning.")

    # --- Backup Age Warning Button Logic (use cache, update only if needed) ---
    update_backup_warning_cache()  # Will only update if time has come

    global _backup_warning_cache
    show_backup_now = _backup_warning_cache["show_backup_now"]
    backup_missing = _backup_warning_cache["backup_missing"]
    backup_age_days = _backup_warning_cache["backup_age_days"]
    version_name = _backup_warning_cache["version_name"]

    if show_backup_now:
        label = "Backup Now!"
        if backup_missing:
            label += f" (v{version_name} Missing)"
        elif backup_age_days is not None:
            label += f" (v{version_name} - {int(backup_age_days)}d old)"
        # Use the core.OT_BackupManager for the "Backup Now!" action
        layout.operator(core.OT_BackupManager.bl_idname, text=label, icon='ERROR').button_input = core.OPERATION_BACKUP
        layout.separator(factor=0.5) # Smaller separator for header

    debug(f"DEBUG __init__.topbar_warning_draw_fn: Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")


def file_menu_draw_fn(self, context: Context) -> None:
    """Draws the main Backup Manager button in the File menu."""
    layout = self.layout
    addon_prefs, _local_debug_active = get_prefs_and_debug()

    if addon_prefs is None:
        debug("ERROR: Backup Manager: file_menu_draw_fn: Addon preferences object is None. Cannot proceed.")
        layout.operator(ui.OT_BackupManagerWindow.bl_idname if hasattr(ui, 'OT_BackupManagerWindow') else "bm.backup_manager_window", text="Backup Manager (Prefs Error)", icon='DISK_DRIVE')
        return

    debug(f"DEBUG __init__.file_menu_draw_fn: Entered. Prefs {'obtained' if addon_prefs else 'NOT obtained'}. Debug: {_local_debug_active}. Time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    if not hasattr(ui, 'OT_BackupManagerWindow'):
        debug("DEBUG __init__.file_menu_draw_fn: ui.OT_BackupManagerWindow missing. Skipping draw.")
        return
    op_idname = ui.OT_BackupManagerWindow.bl_idname
    if not hasattr(bpy.ops.bm, op_idname.split('.')[-1]):
        debug(f"DEBUG __init__.file_menu_draw_fn: Operator {op_idname} missing in bpy.ops.bm. Skipping draw.")
        return
        
    # --- Main Backup Manager Button ---
    button_text = "Backup Manager" # Default text
    button_icon = 'DISK_DRIVE'   # Default icon

    if addon_prefs and hasattr(addon_prefs, 'show_operation_progress') and addon_prefs.show_operation_progress:
        debug("DEBUG __init__.file_menu_draw_fn: Operation in progress. Changing text/icon for File Menu operator.")
        button_text = "Backup in Progress..."
        button_icon = 'COLORSET_09_VEC' 
    else:
        debug("DEBUG __init__.file_menu_draw_fn: No operation in progress. Standard File Menu operator.")

    try:
        layout.operator(op_idname, text=button_text, icon=button_icon)
    except Exception as e:
        debug(f"ERROR: Backup Manager: file_menu_draw_fn failed to draw operator '{op_idname}'. Exception: {type(e).__name__}: {e}")
    layout.separator() # Common separator after the label or operator

    debug(f"DEBUG __init__.file_menu_draw_fn: Exiting.")

# Register and unregister functions
def register():
    global _registered_classes
    _registered_classes.clear() # Clear from any previous registration attempt in this session

    # Define the classes to register, AddonPreferences first
    classes_to_register_dynamically = (
        # PropertyGroups first, as they might be used by AddonPreferences or Operators
        preferences.BM_BackupItem,
        
        # AddonPreferences class, which might define CollectionProperties of the above
        preferences.BM_Preferences,
        
        # UIList classes
        ui.BM_UL_BackupItemsList, 

        # Operator classes
        ui.OT_OpenPathInExplorer, 
        ui.OT_AbortOperation,     
        ui.OT_ShowFinalReport,   
        ui.OT_QuitBlenderNoSave,  
        ui.OT_CloseReportDialog,  
        ui.OT_BackupManagerWindow,
        core.OT_BackupManager,
    )
    _debug_active = False # Default to False for safety
    try:
        try:
            addon_prefs_instance = get_prefs_for_init()
        except KeyError:
            addon_prefs_instance = None
            debug("WARNING: prefs_func() failed. Addon might be unregistered or context unavailable.")
        if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug'):
            _debug_active = addon_prefs_instance.debug
        from .logger import set_debug
        set_debug(_debug_active)
    except Exception as e_prefs:
        debug(f"WARNING: Backup Manager register(): Could not access preferences for debug flag: {e_prefs}")

    for cls_to_reg in classes_to_register_dynamically:
        try:
            bpy.utils.register_class(cls_to_reg)
            _registered_classes.append(cls_to_reg) # Add to our list *after* successful registration
            debug(f"DEBUG: register(): Successfully registered {cls_to_reg.__name__}")
        except ValueError as e:
            if "already registered" in str(e).lower():
                debug(f"INFO: Class {cls_to_reg.__name__} reported as already registered. Attempting to unregister and re-register.")
                try:
                    bpy.utils.unregister_class(cls_to_reg) # Try to unregister it first
                    bpy.utils.register_class(cls_to_reg)   # Then re-register
                    _registered_classes.append(cls_to_reg) # Assume success if no exception
                    debug(f"DEBUG: register(): Re-registered {cls_to_reg.__name__} after 'already registered' error.")
                except Exception as e_rereg:
                    debug(f"ERROR: Backup Manager: Failed to re-register class {cls_to_reg.__name__} after 'already registered' error: {e_rereg}")
            else: # Other ValueError
                debug(f"ERROR: Backup Manager: Failed to register class {cls_to_reg.__name__} (ValueError): {e}")
        except Exception as e: # Other exceptions
            debug(f"ERROR: Backup Manager: Failed to register class {cls_to_reg.__name__} (General Exception): {e}")
    
    # Reset the initial scan flag on registration
    if hasattr(preferences, 'BM_Preferences'):
        preferences.BM_Preferences._initial_scan_done = False # Ensure this refers to the actual flag in BM_Preferences
         
    # Explicitly reset transient preference properties to their defaults.
    # This ensures that even if old values were somehow loaded from userpref.blend
    # (e.g., from before SKIP_SAVE was added or due to property definition changes),
    # they are reset to a clean state for the new session.
    try:
        prefs_instance = bpy.context.preferences.addons[__name__].preferences
        prefs_instance.show_operation_progress = False  # Default
        prefs_instance.operation_progress_value = 0.0   # Default (property is 0-100 factor)
        prefs_instance.operation_progress_message = "Waiting..."  # Default
        prefs_instance.abort_operation_requested = False  # Default

        if prefs_instance.debug:
            debug(f"DEBUG: {__name__} registered. Transient preference properties explicitly reset to defaults.")
    except Exception as e:
        debug(f"ERROR: {__name__}: Could not reset transient preferences during registration: {e}")

    try:
        # Append to the upper bar for header buttons
        bpy.types.TOPBAR_HT_upper_bar.append(topbar_warning_draw_fn)
        bpy.types.TOPBAR_MT_file.prepend(file_menu_draw_fn)
    except Exception as e: # Catch error if prepend fails (e.g. during headless run)
        debug(f"DEBUG: register(): Could not append topbar_header_draw_fn to TOPBAR_HT_upper_bar: {e}")
    debug("DEBUG: Backup Manager register() FINISHED.")


def unregister():
    """
    Unregisters all classes and removes menu entries added by the Backup Manager addon.
    Ensures proper cleanup when the addon is disabled or uninstalled.
    """
    global _registered_classes
    from .debug_utils import get_prefs_and_debug
    from .logger import set_debug
    _debug_active = False
    try:
        addon_prefs_instance, _debug_active = get_prefs_and_debug()
        set_debug(_debug_active)
    except Exception as e_prefs:
        debug(f"DEBUG: unregister(): Could not access preferences for debug flag: {e_prefs}")

    try:
        # Remove from the upper bar
        bpy.types.TOPBAR_HT_upper_bar.remove(topbar_warning_draw_fn)
        bpy.types.TOPBAR_MT_file.remove(file_menu_draw_fn)
    except Exception as e: 
        debug(f"DEBUG: unregister(): Error removing UI draw functions (may have already been removed): {e}")
 
    # Unregister classes that were successfully registered by this addon instance
    if _registered_classes:  # Check if the list is not empty
        for cls_to_unreg in reversed(_registered_classes):
            try:
                bpy.utils.unregister_class(cls_to_unreg)
                debug(f"DEBUG: unregister(): Successfully unregistered {cls_to_unreg.__name__}")
            except Exception as e:
                debug(f"ERROR: Backup Manager: Failed to unregister class {cls_to_unreg.__name__}: {e}")
        # Clear the list after unregistering all classes
        _registered_classes.clear()
