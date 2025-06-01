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

# Standard library imports
import importlib

# Third-party imports (Blender API)
import bpy
from bpy.types import Context
from datetime import datetime # Added for debug timestamps

# --- Module Reloading ---
# These will be populated by reload_addon_modules or initial import
preferences = None
core = None

def _reload_addon_submodules():
    """Force reload of addon submodules for development."""
    global preferences, core
    # print("Backup Manager: Reloading submodules...") # Optional debug print

    # Import or re-import the modules using their full path from the package
    # This ensures that 'preferences' and 'core' are module objects.
    _preferences_module = importlib.import_module(".preferences", __package__)
    _core_module = importlib.import_module(".core", __package__)

    importlib.reload(_preferences_module)
    importlib.reload(_core_module)
    
    preferences = _preferences_module
    core = _core_module
    # print("Backup Manager: Submodules reloaded.") # Optional debug print

# Check if running in Blender's UI and not in background mode before reloading submodules.
if "bpy" in locals() and getattr(bpy.app, 'background_mode', False) is False:
    _reload_addon_submodules()
else:
    from . import preferences as initial_preferences
    from . import core as initial_core
    preferences = initial_preferences
    core = initial_core
# --- End Module Reloading ---


bl_info = {
    "name": "Backup Manager",
    "description": "Backup and Restore your Blender configuration files",
    "author": "Daniel Grauer",
    "version": (1, 3, 1), # Consider incrementing version after changes
    "blender": (3, 0, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}

# Module-level list to keep track of classes registered by this addon instance.
_registered_classes = []

def prefs_func(): # Renamed from prefs to avoid conflict with 'preferences' module
    """
    Directly retrieves the addon's preferences.
    Assumes bpy.context and addon preferences are always accessible.
    """
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences


def menus_draw_fn(self, context: Context) -> None:
    """Callback to add main menu entry."""
    layout = self.layout
    # --- Debug flag retrieval (early, for use in this function) ---
    _local_debug_active = False
    _addon_prefs_for_debug_check = None # Renamed to avoid conflict if it remains None
    try:
        # Try to get prefs once for debug flag and potential reuse
        _addon_prefs_for_debug_check = prefs_func()
        if _addon_prefs_for_debug_check and hasattr(_addon_prefs_for_debug_check, 'debug'):
            _local_debug_active = _addon_prefs_for_debug_check.debug
    except Exception:
        # If prefs_func() fails here, _local_debug_active remains False.
        # This is acceptable as we can't log debug messages without prefs.
        pass

    if _local_debug_active:
        print(f"DEBUG __init__.menus_draw_fn: Entered. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

    # Ensure the core module and the operator class are loaded
    if not core or not hasattr(core, 'OT_BackupManagerWindow'):
        layout.label(text="Backup Manager (Operator Error)", icon='ERROR')
        if _local_debug_active: print("DEBUG __init__.menus_draw_fn: core or OT_BackupManagerWindow missing.")
        return

    op_idname = core.OT_BackupManagerWindow.bl_idname
    # Check if the operator is actually registered and available in bpy.ops.bm
    # op_idname.split('.')[-1] would be 'open_backup_manager_window'
    if not hasattr(bpy.ops.bm, op_idname.split('.')[-1]):
        layout.label(text="Backup Manager: Operator not found in bpy.ops.bm", icon='ERROR')
        if _local_debug_active: print(f"DEBUG __init__.menus_draw_fn: Operator {op_idname} missing in bpy.ops.bm.")
        return

    # Try to get preferences to check operation status
    # Reuse _addon_prefs_for_debug_check if it was successfully retrieved
    addon_prefs = _addon_prefs_for_debug_check
    if addon_prefs is None: # If it failed to fetch earlier or was None from the start
        try:
            addon_prefs = prefs_func()
        except Exception as e_prefs_get:
            if _local_debug_active:
                print(f"ERROR __init__.menus_draw_fn: Exception getting addon_prefs: {e_prefs_get}")
            # Fallback: draw default button if prefs are inaccessible
            layout.operator(op_idname, text="Backup Manager", icon='DISK_DRIVE')
            if _local_debug_active: print(f"DEBUG __init__.menus_draw_fn: Drew default operator due to prefs error. Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            return

    button_text = "Backup Manager"
    button_icon = 'DISK_DRIVE' # Default icon

    if _local_debug_active:
        sop_value = 'N/A (prefs None or attr missing)'
        if addon_prefs and hasattr(addon_prefs, 'show_operation_progress'):
            sop_value = addon_prefs.show_operation_progress
        print(f"DEBUG __init__.menus_draw_fn: addon_prefs {'IS valid' if addon_prefs else 'IS NONE'}. show_operation_progress = {sop_value}")

    if addon_prefs and hasattr(addon_prefs, 'show_operation_progress') and addon_prefs.show_operation_progress:
        if _local_debug_active:
            print(f"DEBUG __init__.menus_draw_fn: Condition MET. Setting text/icon to 'Running...'.")
        button_text = "Backup Manager (Running...)"
        button_icon = 'COLORSET_09_VEC' # Icon indicating activity/warning
    elif _local_debug_active: # Only print if debug is on and condition was false
        print(f"DEBUG __init__.menus_draw_fn: Condition NOT MET for 'Running...' state.")

    try:
        layout.operator(op_idname, text=button_text, icon=button_icon)
        if _local_debug_active:
            print(f"DEBUG __init__.menus_draw_fn: Operator drawn with text='{button_text}', icon='{button_icon}'.")
        layout.separator() # Add this line to draw a separator after your operator
    except Exception as e:
        # Log the error if layout.operator fails, to help diagnose
        print(f"ERROR: Backup Manager: menus_draw_fn failed to draw operator '{op_idname}'. Exception: {type(e).__name__}: {e}")
        # If drawing the operator fails, we log the error but do not display a fallback UI error label in the menu.
        # The menu item for the addon will simply be absent if this occurs.
        pass
    
    if _local_debug_active:
        print(f"DEBUG __init__.menus_draw_fn: Exiting. Current time: {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")

# Register and unregister functions
def register():
    global _registered_classes
    _registered_classes.clear() # Clear from any previous registration attempt in this session

    # Ensure submodules are loaded (important if register is called standalone after an error)
    if not core or not preferences:
        _reload_addon_submodules() # Attempt to load/reload them
        if not core or not preferences:
            print("ERROR: Backup Manager: Core modules (core, preferences) could not be loaded. Registration cannot proceed.")
            return

    # Define the classes to register, AddonPreferences first
    classes_to_register_dynamically = (
        preferences.BM_Preferences,
        preferences.OT_OpenPathInExplorer,
        core.OT_BackupManager,
        core.OT_AbortOperation,
        core.OT_ShowFinalReport,
        core.OT_QuitBlenderNoSave,
        core.OT_CloseReportDialog,
        core.OT_BackupManagerWindow,
    )

    _debug_active = False # Default to False for safety
    try:
        try:
            addon_prefs_instance = prefs_func()
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
        bpy.types.TOPBAR_MT_file.prepend(menus_draw_fn)
    except Exception as e: # Catch error if prepend fails (e.g. during headless run)
        if _debug_active: print(f"DEBUG: register(): Could not prepend menu_draw_fn to TOPBAR_MT_file: {e}")
    if _debug_active: print("DEBUG: Backup Manager register() FINISHED.")


def unregister():
    """
    Unregisters all classes and removes menu entries added by the Backup Manager addon.
    Ensures proper cleanup when the addon is disabled or uninstalled.
    """
    global _registered_classes
    _debug_active = False # Default to False for safety
    try:
        addon_prefs_instance = prefs_func()
        if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug'):
            _debug_active = addon_prefs_instance.debug
    except Exception as e_prefs:
        # Similar to register(), prefs might be gone during shutdown
        if _debug_active: print(f"DEBUG: unregister(): Could not access preferences for debug flag: {e_prefs}")

    try:
        bpy.types.TOPBAR_MT_file.remove(menus_draw_fn)
    except Exception as e: # Can error if not found
        if _debug_active: print(f"DEBUG: unregister(): Error removing menu_draw_fn (may have already been removed): {e}")

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
