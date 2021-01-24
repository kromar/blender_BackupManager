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
else:
    from . import preferences

import bpy


bl_info = {
    "name": "Preference Manager",
    "description": "",
    "author": "Daniel Grauer",
    "version": (0, 1, 0),
    "blender": (2, 83, 0),
    "location": "Preferences",
    "category": "System",
    "wiki_url": "https://github.com/kromar/blender_PreferenceManager",
    "tracker_url": "https://github.com/kromar/blender_PreferenceManager/issues/new",
}



classes = (
    preferences.PreferenceManagerPreferences,
    )

def register():    
    for c in classes:
        bpy.utils.register_class(c)   


def unregister():
    [bpy.utils.unregister_class(c) for c in classes]

if __name__ == "__main__":
    register()
