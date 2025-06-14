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
from datetime import datetime # Added for debug timestamps

# --- Module Imports ---
from . import preferences
from . import core
from . import ui
from .preferences_utils import get_addon_preferences

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
    import os
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


# This function will draw the "Backup Now!" warning button in the top bar header
def topbar_warning_draw_fn(self, context: Context) -> None:
    """Draws the Backup Manager 'Backup Now!' warning button in the TOPBAR header if needed."""
    layout = self.layout
    # --- Debug flag retrieval (early, for use in this function) ---
    _local_debug_active = False
    _addon_prefs_for_debug_check = None # Renamed to avoid conflict if it remains None
    try:
        # Try to get prefs once for debug flag and potential reuse
        _addon_prefs_for_debug_check = get_prefs_for_init()
        if _addon_prefs_for_debug_check and hasattr(_addon_prefs_for_debug_check, 'debug'):
            _local_debug_active = _addon_prefs_for_debug_check.debug
    except Exception:
        # If prefs_func() fails here, _local_debug_active remains False.
        # This is acceptable as we can't log debug messages without prefs.
        pass

    if _local_debug_active:
        print(f"DEBUG __init__.topbar_warning_draw_fn: Entered. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    # Ensure the ui module and the operator class are loaded
    if not hasattr(ui, 'OT_BackupManagerWindow'):
        if _local_debug_active: print("DEBUG __init__.topbar_warning_draw_fn: ui.OT_BackupManagerWindow missing. Skipping draw.")
        return

    op_idname = ui.OT_BackupManagerWindow.bl_idname
    # Check if the operator is actually registered and available in bpy.ops.bm
    if not hasattr(bpy.ops.bm, op_idname.split('.')[-1]):
        # Silently skip drawing if operator is not found, to avoid cluttering header with errors
        if _local_debug_active: print(f"DEBUG __init__.topbar_warning_draw_fn: Operator {op_idname} missing in bpy.ops.bm. Skipping draw.")
        return

    # Try to get preferences to check operation status
    # Reuse _addon_prefs_for_debug_check if it was successfully retrieved
    addon_prefs = _addon_prefs_for_debug_check
    if addon_prefs is None: # If it failed to fetch earlier or was None from the start
        try:
            addon_prefs = get_prefs_for_init()
        except Exception as e_prefs_get:
            if _local_debug_active:
                print(f"ERROR __init__.topbar_warning_draw_fn: Exception getting addon_prefs: {e_prefs_get}. Cannot draw warning.")
            # If prefs fail, we can't determine if a warning is needed.
            if _local_debug_active: print(f"DEBUG __init__.topbar_warning_draw_fn: Exiting due to prefs error. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            return

    # --- Check if an operation is currently in progress ---
    if addon_prefs and hasattr(addon_prefs, 'show_operation_progress') and addon_prefs.show_operation_progress:
        # Operation is in progress, show a status button that opens the main window
        layout.operator(ui.OT_BackupManagerWindow.bl_idname, text="Backup in Progress", icon='COLORSET_09_VEC')
        layout.separator(factor=0.5) # Keep separator consistent
        if _local_debug_active:
            print(f"DEBUG __init__.topbar_warning_draw_fn: Drawing 'Backup Active...' button. Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        return # Do not show age warning if an operation is active

        
    # --- Backup Age Warning Button Logic ---
    show_backup_now = False
    backup_age_days = None
    backup_missing = False
    if addon_prefs and hasattr(addon_prefs, 'backup_reminder_duration') and addon_prefs.backup_reminder:
        import os
        backup_path = addon_prefs.backup_path
        system_id = addon_prefs.system_id
        version_name = str(addon_prefs.active_blender_version)

        if backup_path: # Ensure backup_path is set
            system_path = os.path.join(backup_path, system_id, version_name) if system_id else None
            shared_path = os.path.join(backup_path, 'SharedConfigs', version_name)

            system_exists = system_path and os.path.isdir(system_path)
            shared_exists = shared_path and os.path.isdir(shared_path)

            if not system_exists and not shared_exists:
                backup_missing = True
                show_backup_now = True
            else:
                latest_mtime = _get_latest_backup_mtime(addon_prefs)
                if latest_mtime is not None:
                    import time # Local import
                    age_seconds = time.time() - latest_mtime
                    backup_age_days = age_seconds / 86400.0 # Seconds in a day
                    if backup_age_days > addon_prefs.backup_reminder_duration:
                        show_backup_now = True
        elif _local_debug_active:
            print("DEBUG __init__.topbar_warning_draw_fn: backup_path is not set, skipping backup age check.")

    if show_backup_now:
        label = "Backup Now!"
        if backup_missing:
            label += f" (v{version_name} Missing)" # Shorter for header, with version
        elif backup_age_days is not None:
            label += f" (v{version_name} - {int(backup_age_days)}d old)"
        # Use the core.OT_BackupManager for the "Backup Now!" action
        layout.operator(core.OT_BackupManager.bl_idname, text=label, icon='ERROR').button_input = 'BACKUP'
        layout.separator(factor=0.5) # Smaller separator for header

    if _local_debug_active:
        print(f"DEBUG __init__.topbar_warning_draw_fn: Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")


def file_menu_draw_fn(self, context: Context) -> None:
    """Draws the main Backup Manager button in the File menu."""
    layout = self.layout
    _local_debug_active = False
    _addon_prefs_for_debug_check = None
    try:
        _addon_prefs_for_debug_check = get_prefs_for_init()
        if _addon_prefs_for_debug_check and hasattr(_addon_prefs_for_debug_check, 'debug'):
            _local_debug_active = _addon_prefs_for_debug_check.debug
    except Exception:
        pass

    if _local_debug_active:
        print(f"DEBUG __init__.file_menu_draw_fn: Entered. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    if not hasattr(ui, 'OT_BackupManagerWindow'):
        if _local_debug_active: print("DEBUG __init__.file_menu_draw_fn: ui.OT_BackupManagerWindow missing. Skipping draw.")
        return

    op_idname = ui.OT_BackupManagerWindow.bl_idname
    if not hasattr(bpy.ops.bm, op_idname.split('.')[-1]):
        if _local_debug_active: print(f"DEBUG __init__.file_menu_draw_fn: Operator {op_idname} missing in bpy.ops.bm. Skipping draw.")
        return

    addon_prefs = _addon_prefs_for_debug_check
    if addon_prefs is None:
        try:
            addon_prefs = get_prefs_for_init()
        except Exception as e_prefs_get:
            if _local_debug_active:
                print(f"ERROR __init__.file_menu_draw_fn: Exception getting addon_prefs: {e_prefs_get}")
            layout.operator(op_idname, text="Backup Manager (Prefs Error)", icon='DISK_DRIVE')
            if _local_debug_active: print(f"DEBUG __init__.file_menu_draw_fn: Drew fallback operator due to prefs error. Exiting.")
            return
        
    # --- Main Backup Manager Button ---
    button_text = "Backup Manager"
    button_icon = 'DISK_DRIVE'
    
    if addon_prefs and hasattr(addon_prefs, 'show_operation_progress') and addon_prefs.show_operation_progress:
        if _local_debug_active:
            print("DEBUG __init__.file_menu_draw_fn: Condition MET. Setting text/icon to 'Backup in Progress'.")
        button_text = "Backup in Progress"
        button_icon = 'COLORSET_09_VEC' # Icon indicating activity/warning
    elif _local_debug_active: # Only print if debug is on and condition was false
        print("DEBUG __init__.file_menu_draw_fn: Condition NOT MET for 'Backup in Progress' state.")

    try:
        layout.operator(op_idname, text=button_text, icon=button_icon)
        if _local_debug_active:
            print(f"DEBUG __init__.file_menu_draw_fn: Operator drawn with text='{button_text}', icon='{button_icon}'.")
        layout.separator()
    except Exception as e:
        print(f"ERROR: Backup Manager: topbar_header_draw_fn failed to draw operator '{op_idname}'. Exception: {type(e).__name__}: {e}")

    if _local_debug_active:
        print(f"DEBUG __init__.topbar_header_draw_fn: Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        print(f"ERROR: Backup Manager: file_menu_draw_fn failed to draw operator '{op_idname}'. Exception: {type(e).__name__}: {e}")
    
    if _local_debug_active: 
        print(f"DEBUG __init__.file_menu_draw_fn: Exiting.")

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
            print("WARNING: prefs_func() failed. Addon might be unregistered or context unavailable.")
        if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug'):
            _debug_active = addon_prefs_instance.debug
    except Exception as e_prefs:
        # This might happen if prefs are not yet available or __package__ is not set during a very early call
        print(f"WARNING: Backup Manager register(): Could not access preferences for debug flag: {e_prefs}")

    if _debug_active: print("DEBUG: Backup Manager register() CALLED")
    
    for cls_to_reg in classes_to_register_dynamically:
        try:
            bpy.utils.register_class(cls_to_reg)
            _registered_classes.append(cls_to_reg) # Add to our list *after* successful registration
            if _debug_active: print(f"DEBUG: register(): Successfully registered {cls_to_reg.__name__}")
        except ValueError as e:
            if "already registered" in str(e).lower():
                if _debug_active: print(f"INFO: Class {cls_to_reg.__name__} reported as already registered. Attempting to unregister and re-register.")
                try:
                    bpy.utils.unregister_class(cls_to_reg) # Try to unregister it first
                    bpy.utils.register_class(cls_to_reg)   # Then re-register
                    _registered_classes.append(cls_to_reg) # Assume success if no exception
                    if _debug_active: print(f"DEBUG: register(): Re-registered {cls_to_reg.__name__} after 'already registered' error.")
                except Exception as e_rereg:
                    print(f"ERROR: Backup Manager: Failed to re-register class {cls_to_reg.__name__} after 'already registered' error: {e_rereg}")
            else: # Other ValueError
                print(f"ERROR: Backup Manager: Failed to register class {cls_to_reg.__name__} (ValueError): {e}")
        except Exception as e: # Other exceptions
            print(f"ERROR: Backup Manager: Failed to register class {cls_to_reg.__name__} (General Exception): {e}")
    
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
            print(f"DEBUG: {__name__} registered. Transient preference properties explicitly reset to defaults.")
    except Exception as e:
        print(f"ERROR: {__name__}: Could not reset transient preferences during registration: {e}")

    try:
        # Append to the upper bar for header buttons
        bpy.types.TOPBAR_HT_upper_bar.append(topbar_warning_draw_fn)
        bpy.types.TOPBAR_MT_file.prepend(file_menu_draw_fn)
    except Exception as e: # Catch error if prepend fails (e.g. during headless run)
        if _debug_active: print(f"DEBUG: register(): Could not append topbar_header_draw_fn to TOPBAR_HT_upper_bar: {e}")
    if _debug_active: print("DEBUG: Backup Manager register() FINISHED.")


def unregister():
    """
    Unregisters all classes and removes menu entries added by the Backup Manager addon.
    Ensures proper cleanup when the addon is disabled or uninstalled.
    """
    global _registered_classes
    _debug_active = False # Default to False for safety
    try:
        addon_prefs_instance = get_prefs_for_init()
        if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug'):
            _debug_active = addon_prefs_instance.debug
    except Exception as e_prefs:
        # Similar to register(), prefs might be gone during shutdown
        if _debug_active: print(f"DEBUG: unregister(): Could not access preferences for debug flag: {e_prefs}")

    try:
        # Remove from the upper bar
        bpy.types.TOPBAR_HT_upper_bar.remove(topbar_warning_draw_fn)
        bpy.types.TOPBAR_MT_file.remove(file_menu_draw_fn)
    except Exception as e: 
        if _debug_active: print(f"DEBUG: unregister(): Error removing UI draw functions (may have already been removed): {e}")
 
    # Unregister classes that were successfully registered by this addon instance
    if _registered_classes:  # Check if the list is not empty
        for cls_to_unreg in reversed(_registered_classes):
            try:
                bpy.utils.unregister_class(cls_to_unreg)
                if _debug_active: print(f"DEBUG: unregister(): Successfully unregistered {cls_to_unreg.__name__}")
            except Exception as e:
                print(f"ERROR: Backup Manager: Failed to unregister class {cls_to_unreg.__name__}: {e}")
        # Clear the list after unregistering all classes
        _registered_classes.clear()
