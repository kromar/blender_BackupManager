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


if "bpy" in locals():
    import importlib
    importlib.reload(preferences)
    importlib.reload(core)
else:
    from . import preferences
    from . import core

import bpy
from bpy.types import Context, Menu


bl_info = {
    "name": "Backup Manager",
    "description": "Backup and Restore your Blender configuration files",
    "author": "Daniel Grauer",
    "version": (1, 2, 0),
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
    bl_idname = 'BM_MT_BR'

    def draw(self, context):
        pass

classes = (
    core.OT_BackupManager,
    preferences.BM_Preferences,
    BM_MT_BR,
    )


def menus_draw_fn(self, context: Context) -> None:
    """Callback to add menus for exporters."""
    layout = self.layout    
    layout.menu(BM_MT_BR.bl_idname)   
    

def backupandrestore_menu_fn(self, context: Context) -> None:
    """Menu Callback for the export operator."""
    layout = self.layout
    layout.operator("bm.run_backup_manager", text="Run Backup", icon='COLORSET_03_VEC').button_input = 'BACKUP'     
    layout.operator("bm.run_backup_manager", text="Run Restore", icon='COLORSET_04_VEC').button_input = 'RESTORE' 


def register():    
    [bpy.utils.register_class(c) for c in classes]
    bpy.types.TOPBAR_MT_file_defaults.append(menus_draw_fn)
    bpy.types.TOPBAR_MT_file.append(backupandrestore_menu_fn)


def unregister():
    [bpy.utils.unregister_class(c) for c in classes]
    bpy.types.TOPBAR_MT_file_defaults.remove(menus_draw_fn)
    bpy.types.TOPBAR_MT_file.remove(backupandrestore_menu_fn)

if __name__ == "__main__":
    register()
