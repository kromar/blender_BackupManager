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
if "bpy" in locals():
    # If reloading, re-import the addon's core modules to pick up changes.
    # 'preferences' and 'core' module objects are expected to be in the global
    # scope from the initial load (the 'else' block below).
    importlib.reload(preferences)
    importlib.reload(core)
else:
    # Initial load of the addon.
    from . import preferences
    from . import core

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

class BM_MT_BR(Menu):
    bl_label = 'Backup and Restore'
    # bl_idname should be unique, typically ADDONNAME_MT_menuname
    bl_idname = 'BM_MT_BR'

    def draw(self, context):
        pass


classes = (
    core.OT_BackupManager,
    preferences.BM_Preferences,
    BM_MT_BR,
    )


def menus_draw_fn(self, context: Context) -> None:
    """Callback to add main menu entry."""
    layout = self.layout    
    layout.menu(BM_MT_BR.bl_idname)   
    

# The BM_MT_BR menu is empty. If this menu is intended to be used,
# its draw() method needs content, or this function could directly add operators.
def backupandrestore_menu_fn(self, context: Context) -> None:
    """Menu Callback for the export operator."""
    layout = self.layout
    layout.operator("bm.run_backup_manager", text="Run Backup", icon='COLORSET_03_VEC').button_input = 'BACKUP'     
    layout.operator("bm.run_backup_manager", text="Run Restore", icon='COLORSET_04_VEC').button_input = 'RESTORE' 


def register():    
    [bpy.utils.register_class(c) for c in classes]
    # bpy.types.TOPBAR_MT_file_new.append(backupandrestore_menu_fn) # Example: Add to File > New
    # bpy.types.TOPBAR_MT_file.append(menus_draw_fn) # If BM_MT_BR is populated


def unregister():
    # No timer to unregister in this approach
    [bpy.utils.unregister_class(c) for c in classes]
    # bpy.types.TOPBAR_MT_file_new.remove(backupandrestore_menu_fn)
    # bpy.types.TOPBAR_MT_file.remove(menus_draw_fn)

if __name__ == "__main__":
    register()
