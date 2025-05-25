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
    "blender": (2, 93, 0),
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
    # Ensure 'core' and 'OT_BackupManagerWindow' are available
    if core and hasattr(core, 'OT_BackupManagerWindow'):
        layout.operator(core.OT_BackupManagerWindow.bl_idname, text="Backup Manager", icon='WINDOW')
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

def _initial_version_scan_timer():
    """Timer to perform the initial version scan shortly after registration."""
    try:
        prefs_instance = prefs_func() # Use renamed function
        
        # Determine debug state safely
        _debug_active_timer = prefs_instance.debug if prefs_instance and hasattr(prefs_instance, 'debug') else False

        if not prefs_instance:
            print("ERROR: Backup Manager: _initial_version_scan_timer: Addon preferences not available. Timer cannot proceed.")
            return None # Stop the timer

        # Check if the initial scan has already been done for this registration cycle
        if preferences.BM_Preferences._initial_scan_done:
            if _debug_active_timer: print("DEBUG: _initial_version_scan_timer: Initial scan already done, unregistering timer.")
            return None # Stop the timer

        if _debug_active_timer: print(f"DEBUG: _initial_version_scan_timer: Performing initial version scan for tabs: {prefs_instance.tabs}.")
        
        # Determine the search mode based on the currently active tab in preferences.
        if hasattr(prefs_instance, 'tabs'):
            search_mode = f'SEARCH_{prefs_instance.tabs}'
            if hasattr(bpy.ops.bm, 'run_backup_manager'):
                bpy.ops.bm.run_backup_manager(button_input=search_mode)
                if hasattr(preferences, 'BM_Preferences'): # Ensure module and class are available
                    preferences.BM_Preferences._initial_scan_done = True
                if _debug_active_timer: print("DEBUG: _initial_version_scan_timer: Scan complete, timer finished.")
            else:
                if _debug_active_timer: print("ERROR: _initial_version_scan_timer: bpy.ops.bm.run_backup_manager not found.")
        else:
            if _debug_active_timer: print("ERROR: _initial_version_scan_timer: prefs_instance.tabs not available.")
        
        return None # Stop the timer after running once
        
    except Exception as e:
        # Attempt to get debug state again for error logging, carefully
        _debug_err_check = False
        try: 
            _prefs_for_err = prefs_func()
            if _prefs_for_err and hasattr(_prefs_for_err, 'debug'):
                _debug_err_check = _prefs_for_err.debug
        except: pass # Ignore errors getting debug state here
        if _debug_err_check: print(f"ERROR: Backup Manager: Error in _initial_version_scan_timer: {e}")
        else: print(f"ERROR: Backup Manager: Error in _initial_version_scan_timer (debug state unknown): {e}")
        return None # Stop the timer on error

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
        core.OT_BackupManagerWindow,
    )

    addon_prefs_instance = prefs_func()
    _debug_active = addon_prefs_instance.debug if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug') else False

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
        preferences.BM_Preferences._initial_scan_done = False
    
    if bpy.app.timers.is_registered(_initial_version_scan_timer):
        if _debug_active: print("DEBUG: register(): _initial_version_scan_timer was already registered. Removing before re-registering.")
        bpy.app.timers.unregister(_initial_version_scan_timer)
    bpy.app.timers.register(_initial_version_scan_timer, first_interval=0.1) # Register the function defined in this file
    if _debug_active: print("DEBUG: register(): Scheduled _initial_version_scan_timer.")

    try:
        bpy.types.TOPBAR_MT_file.append(menus_draw_fn)
    except Exception as e: # Catch error if append fails (e.g. during headless run)
        if _debug_active: print(f"DEBUG: register(): Could not append menu_draw_fn to TOPBAR_MT_file: {e}")
    if _debug_active: print("DEBUG: Backup Manager register() FINISHED.")

def unregister():
    global _registered_classes
    addon_prefs_instance = prefs_func()
    _debug_active = addon_prefs_instance.debug if addon_prefs_instance and hasattr(addon_prefs_instance, 'debug') else False

    if _debug_active: print("DEBUG: Backup Manager unregister() CALLED")

    # Ensure the initial scan timer is unregistered if it's still pending
    if bpy.app.timers.is_registered(_initial_version_scan_timer):
        bpy.app.timers.unregister(_initial_version_scan_timer)
        if _debug_active: print("DEBUG: unregister(): Unregistered _initial_version_scan_timer.")
    
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
