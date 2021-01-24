# ##### BEGIN GPL LICENSE BLOCK #####
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
    
    
import bpy
from bpy.types import AddonPreferences
from bpy.props import ( StringProperty, 
                        BoolProperty, 
                        FloatProperty,
                        EnumProperty)

# https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html
print(bpy.utils.user_resource('CONFIG'))
print(bpy.utils.resource_path(type='USER', major=bpy.app.version[0], minor=bpy.app.version[1]))



class PreferenceManagerPreferences(AddonPreferences):
    bl_idname = __package__
    
    config_path: StringProperty(
        name="config_path", 
        description="config_path", 
        subtype='DIR_PATH',
        default=bpy.utils.user_resource('CONFIG') )
   

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, 'config_path') 
