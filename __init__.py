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
import os
import numpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, EnumProperty, BoolProperty

bl_info = {
    "name": "Preference Manager",
    "description": "",
    "author": "Daniel Grauer",
    "version": (0, 1, 0),
    "blender": (2, 83, 0),
    "location": "Preferences",
    "category": "!kromar",
    "wiki_url": "https://github.com/kromar/blender_PreferenceManager",
    "tracker_url": "https://github.com/kromar/blender_PreferenceManager/issues/new",
}

version_list =[]
class PM_OT_ConfigManager(Operator):
    ''' Look for a new Addon version on Github '''
    bl_idname = "pm.check_versions"
    bl_label = "Blender Versions" 
    
    button_input: bpy.props.IntProperty()

    def max_list_value(self, list):
        i = numpy.argmax(list)
        v = list[i]
        return (i, v)

    def find_versions(self, filepath):
        global version_list
        version_list.clear()  
        path_preferences = f"{os.path.dirname(filepath)+'/'}".replace("/", "\\")  
        for v in os.listdir(path_preferences):
            version_list.append((v, v, ""))
        return version_list
    
    def backup_version(self, filepath):
        
        pref = bpy.context.preferences.addons[__package__].preferences
        backup = None
            
        backup_path = os.path.dirname(filepath)
        
        if pref.bl_versions:
            backup = f"{backup_path + '/' +  pref.bl_versions}".replace("/", "\\")
        else:
            #backup current version
            backup = f"{backup_path + '/' + bpy.app.version[0] + '.' + bpy.app.version[1]}".replace("/", "\\") 
            print("backup current version")  


        print("lets backup: ", backup)

        return {'FINISHED'}

    def execute(self, context):     
        pref = bpy.context.preferences.addons[__package__].preferences
        global version_list

        #print("self.button_input: ", self.button_input)        
        if self.button_input == 1:
            version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
        if self.button_input == 2:
            self.backup_version(bpy.utils.resource_path(type='USER'))   

        return {'FINISHED'}
    
    

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

    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
    custom_version: StringProperty(
        name="Current Version", 
        description="Current Blender Version", 
        subtype='NONE',
        default=str(bpy.app.version[0]) + '.' + str(bpy.app.version[1]))
        
    backup_path: StringProperty(
        name="Backup Location", 
        description="Backup Location", 
        subtype='DIR_PATH',
        default=bpy.app.tempdir)
                  
    def list_populate(self, context):
        global version_list
        return version_list

    bl_versions: EnumProperty(
        items=list_populate, 
        name="Backup Verison", 
        description="Choose the version to backup")

    use_custom_version: BoolProperty(
        name="Custom Version",
        description="use_custom_version",
        default=False)

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
        col  = box.column(align=False)   

        #if self.use_custom_version:
            
        col.prop(self, 'use_custom_version')  

        col.prop(self, 'custom_version')   
        #col.prop(self, 'custom_version')     
        col.operator("pm.check_versions", text="Search Backups", icon='COLORSET_03_VEC').button_input = 1


        col  = layout.column(align=False) 
        row = col.row()
        box = row.box()   
        col  = box.column(align=False) 
        #col.label(text="Current Blender Version: " + bpy.app.version_string)           
        col.operator("pm.check_versions", text="Backup", icon='COLORSET_04_VEC').button_input = 2  
        col.prop(self, 'bl_versions')    

        box = row.box()   
        col  = box.column(align=False) 
        #col.label(text="Current Blender Version: " + bpy.app.version_string)     
        col.operator("pm.check_versions", text="Restore", icon='COLORSET_01_VEC').button_input = 4  
        col.prop(self, 'bl_versions')    
        col.prop(self, 'backup_path')   

       
         
classes = (
    PM_OT_ConfigManager,
    ConfigManagerPreferences,
    )

def register():    
    for c in classes:
        try:
            bpy.utils.register_class(c)   
        except:
            print(c, " already loaded")

def unregister():
    [bpy.utils.unregister_class(c) for c in classes]

if __name__ == "__main__":
    register()
