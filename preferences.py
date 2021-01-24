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

    
import os
import bpy
from bpy.types import AddonPreferences
from bpy.props import ( StringProperty, 
                        BoolProperty,
                        EnumProperty)

class ConfigManagerPreferences(AddonPreferences):
    bl_idname = __package__

    ############################################
    #      Manager
    ############################################
    config_path: StringProperty(
        name="config_path", 
        description="config_path", 
        subtype='DIR_PATH',
        default=bpy.utils.user_resource('CONFIG')) #Resource type in [‘DATAFILES’, ‘CONFIG’, ‘SCRIPTS’, ‘AUTOSAVE’].

    user_resource_path: StringProperty(
        name="user_resource_path", 
        description="user_resource_path", 
        subtype='DIR_PATH',
        default=bpy.utils.resource_path(type='USER', major=bpy.app.version[0], minor=bpy.app.version[1]))
    

    version_paths: EnumProperty(
            name="version_paths",
            description="version_paths",
            items='',
            default='')  
            
    ############################################
    #       UI
    ############################################

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        
        ############################################
        #      Manager UI
        ############################################
        box = layout.box() 
        box.label(text='Path Manager', icon='PREFERENCES')  
        col  = box.column(align=False) 

        #col.prop(self, 'config_path')         
        col.prop(self, 'user_resource_path') 

        col.operator("pm.check_versions", text="Download: ", icon='COLORSET_03_VEC').button_input = 1
        
        #col.prop(self, 'version_paths')

       
         
        

        
        
