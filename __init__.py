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

# Blender-specific addon reloading logic
# This pattern handles reloading of the addon's modules when the addon is
# re-enabled or re-registered in Blender, which is common during development.
# "bpy" in locals() checks if Blender's Python environment (bpy) is already
# initialized in the current scope, indicating a reload rather than an initial load.

# Always import the modules first so they are in the namespace
from . import preferences
from . import core
from .core import OT_BackupManagerWindow # Import the new window operator

import bpy.app.timers # Import timers module

if "bpy" in locals():
    # If reloading, re-import the addon's core modules to pick up changes.
    importlib.reload(preferences)
    importlib.reload(core)

# Third-party imports (Blender API)
import bpy
from bpy.types import Context, Menu


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

def prefs():
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences

# Define classes to be registered
classes = (
    core.OT_BackupManager,
    core.OT_AbortOperation,
    core.OT_ShowFinalReport, # Register the new operator for popups
    core.OT_BackupManagerWindow, # Register the new window operator
    preferences.BM_Preferences,
    # BM_MT_BR, # Removed as we are placing the operator directly in the File menu
)


def menus_draw_fn(self, context: Context) -> None:
    """Callback to add main menu entry."""
    layout = self.layout    
    # layout.menu(BM_MT_BR.bl_idname, text="Backup Manager") # Old: Adds a submenu
    layout.operator(OT_BackupManagerWindow.bl_idname, text="Backup Manager", icon='WINDOW') # New: Adds operator directly
    

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
        prefs_instance = bpy.context.preferences.addons[__package__].preferences
        # Check if the initial scan has already been done for this registration cycle
        if preferences.BM_Preferences._initial_scan_done:
            if prefs_instance.debug: print("DEBUG: _initial_version_scan_timer: Initial scan already done, unregistering timer.")
            return None # Stop the timer

        if prefs_instance.debug: print("DEBUG: _initial_version_scan_timer: Performing initial version scan.")
        
        # Determine the search mode based on the currently active tab in preferences.
        search_mode = f'SEARCH_{prefs_instance.tabs}'
        bpy.ops.bm.run_backup_manager(button_input=search_mode)
        
        # Mark the initial scan as done
        preferences.BM_Preferences._initial_scan_done = True
        
        if prefs_instance.debug: print("DEBUG: _initial_version_scan_timer: Scan complete, timer finished.")
        return None # Stop the timer after running once
        
    except Exception as e:
        print(f"ERROR: Backup Manager: Error during initial version scan timer: {e}")
        return None # Stop the timer on error

def register():    
    print("DEBUG: Backup Manager register() CALLED")
    [bpy.utils.register_class(c) for c in classes]
    
    # Reset the initial scan flag on registration
    preferences.BM_Preferences._initial_scan_done = False
    
    # Register a one-shot timer to perform the initial version scan shortly after registration
    # This avoids calling the operator directly from register(), which has a restricted context.
    bpy.app.timers.register(_initial_version_scan_timer, first_interval=0.1)
    if prefs().debug: # Use the local prefs() function defined in this __init__.py file
        print("DEBUG: register(): Registered _initial_version_scan_timer with first_interval=0.1s.")

    # bpy.types.TOPBAR_MT_file_new.append(backupandrestore_menu_fn) # Example: Add to File > New
    bpy.types.TOPBAR_MT_file.append(menus_draw_fn) # Add "Backup Manager" submenu to File menu


def unregister():
    # Ensure the initial scan timer is unregistered if it's still pending
    if bpy.app.timers.is_registered(_initial_version_scan_timer):
        bpy.app.timers.unregister(_initial_version_scan_timer)
    [bpy.utils.unregister_class(c) for c in classes]
    # bpy.types.TOPBAR_MT_file_new.remove(backupandrestore_menu_fn)
    bpy.types.TOPBAR_MT_file.remove(menus_draw_fn)

if __name__ == "__main__":
    register()
