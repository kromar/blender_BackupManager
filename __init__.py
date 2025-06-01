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
    "version": (1, 2, 2), # Consider incrementing version after changes
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
    if core and hasattr(core, 'OT_BackupManagerWindow'):
        # Diagnostic: Check if Blender's operator system recognizes the bl_idname
        op_idname = core.OT_BackupManagerWindow.bl_idname
        if hasattr(bpy.ops.bm, op_idname.split('.')[-1]): # Check if 'bm.open_backup_manager_window' is known as 'bpy.ops.bm.open_backup_manager_window'
            layout.operator(op_idname, text="Backup Manager", icon='WINDOW')
        else:
            _debug_menu_draw = False
            try:
                _debug_menu_draw = prefs_func().debug
            except Exception: # Catch errors if prefs_func() fails (e.g. during very early UI draw)
                pass # Keep _debug_menu_draw as False
            layout.label(text=f"Backup Manager (Op '{op_idname.split('.')[-1]}' unavailable)") # Shorter error for menu
            if _debug_menu_draw:
                print(f"DEBUG: menus_draw_fn: bpy.ops.bm does not have {op_idname.split('.')[-1]}. Available: {dir(bpy.ops.bm)}")
    else:
        layout.label(text="Backup Manager Window (Error: Operator not loaded)")
    

# The BM_MT_BR menu is empty. If this menu is intended to be used, its draw() method needs content.
# The backupandrestore_menu_fn seems intended for a different menu type or location.
# Keeping them commented out as they don't seem actively used in the preferences panel context.
# def backupandrestore_menu_fn(self, context: Context) -> None:
#     """Menu Callback for the export operator."""
#     layout = self.layout
#     layout.operator("bm.run_backup_manager", text="Run Backup", icon='COLORSET_03_VEC').button_input = 'BACKUP'     
#     layout.operator("bm.run_backup_manager", text="Run Restore", icon='COLORSET_04_VEC').button_input = 'RESTORE' 

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
        core.OT_BackupManager,
        core.OT_AbortOperation,
        core.OT_ShowFinalReport,
        core.OT_QuitBlenderNoSave, # Add the new operator
        core.OT_BackupManagerWindow,
    )

    _debug_active = False # Default to False for safety
    try:
        addon_prefs_instance = prefs_func()
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
        bpy.types.TOPBAR_MT_file.append(menus_draw_fn)
    except Exception as e: # Catch error if append fails (e.g. during headless run)
        if _debug_active: print(f"DEBUG: register(): Could not append menu_draw_fn to TOPBAR_MT_file: {e}")
    if _debug_active: print("DEBUG: Backup Manager register() FINISHED.")


def unregister():
    global _registered_classes
    _debug_active = False # Default to False for safety
    try:
        addon_prefs_instance = prefs_func()
        if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug'):
            _debug_active = addon_prefs_instance.debug
    except Exception as e_prefs:
        # Similar to register(), prefs might be gone during shutdown
        print(f"WARNING: Backup Manager unregister(): Could not access preferences for debug flag: {e_prefs}")

    if _debug_active: print("DEBUG: Backup Manager unregister() CALLED")

    try:
        bpy.types.TOPBAR_MT_file.remove(menus_draw_fn)
    except Exception as e: # Can error if not found
        if _debug_active: print(f"DEBUG: unregister(): Error removing menu_draw_fn (may have already been removed): {e}")

    # Unregister classes that were successfully registered by this addon instance
    for cls_to_unreg in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls_to_unreg)
            if _debug_active: print(f"DEBUG: unregister(): Successfully unregistered {cls_to_unreg.__name__}")
        except Exception as e:
            print(f"ERROR: Backup Manager: Failed to unregister class {cls_to_unreg.__name__}: {e}")
    _registered_classes.clear()

if __name__ == "__main__":
    register()
