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
import shutil
import distutils.dir_util
import numpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, EnumProperty, BoolProperty

bl_info = {
    "name": "Backup Manager",
    "description": "",
    "author": "Daniel Grauer",
    "version": (0, 3, 0),
    "blender": (2, 83, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}

version_list =[]
class OT_BackupManager(Operator):
    ''' Look for a new Addon version on Github '''
    bl_idname = "bm.check_versions"
    bl_label = "Blender Versions" 
    
    button_input: bpy.props.IntProperty()

    def max_list_value(self, list):
        i = numpy.argmax(list)
        v = list[i]
        return (i, v)

    def find_versions(self, filepath):
        global version_list
        version_list.clear()  
        path_preferences = f"{os.path.dirname(filepath)}"
        for v in os.listdir(path_preferences):
            version_list.append((v, v, ""))
        return version_list
    

    def backup_version(self, filepath):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        backup_path = os.path.dirname(filepath)

        if pref.bl_versions:
            version = pref.bl_versions
            print("\nBacking up selected version ", version)
        else:
            version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
            print("\nBacking up current version ", version)

        backup_list = []
        if pref.backup_cache:
            backup_list.append(os.path.join(version, 'cache'))    
        if pref.backup_bookmarks:
            backup_list.append(os.path.join(version, 'config', 'bookmarks.txt'))     
        if pref.backup_recentfiles:
            backup_list.append(version +'/config/recent-files.txt')        
        if pref.backup_startup_blend:
            backup_list.append(version +'/config/startup.blend')        
        if pref.backup_userpref_blend:
            backup_list.append(version +'/config/userpref.blend')       
        if pref.backup_workspaces_blend:
            backup_list.append(version +'/config/workspaces.blend')        
        if pref.backup_datafile:
            backup_list.append(version +'/datafiles/')        
        if pref.backup_addons:
            backup_list.append(version +'/scripts/addons/')        
        if pref.backup_presets:
            backup_list.append(version +'/scripts/presets/')

        if pref.clean_target_path:
            try:
                shutil.rmtree(pref.backup_path + version)
                print("\nCleaned target path ", pref.backup_path + version)
            except:
                pass


        for i, target in enumerate(backup_list):
            print(i,target )
            source_path = os.path.join(backup_path, target).replace("\\", "/")
            target_path =  os.path.join(pref.backup_path + target).replace("\\", "/")
            print("Source: ", source_path, "\nTarget: ", target_path) 
            
            print("\nBackup to target path ", target_path)
            if os.path.isdir(source_path):
                print("Backup folder: \n", source_path, target_path)
                shutil.copytree(source_path, target_path, symlinks=True)
            else:
                print("Backup copyfile: \n", source_path, target_path)
                try:
                    os.makedirs(os.path.dirname(target_path))
                except: 
                    pass
                shutil.copy2(source_path, target_path)
                
            print("\nBackup complete")

        return {'FINISHED'}



    def restore_version(self, filepath):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        backup_path = os.path.dirname(filepath)
        if pref.custom_version:            
            print("\nRestoring custom version ", pref.custom_version)
        else:
            if pref.bl_versions:
                #Restore selected version
                print("\nRestoring selected version ", pref.bl_versions)
                target_path = f"{backup_path + '/' +  pref.bl_versions + '/'}".replace("/", "\\")
                source_path =  f"{pref.backup_path + pref.bl_versions + '/'}".replace("/", "\\")
            else:
                #Restore current version
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
                print("\nRestoring current version ", version)
                target_path = f"{backup_path + '/' + version + '/'}".replace("/", "\\") 
                source_path =  f"{pref.backup_path + version + '/'}".replace("/", "\\")

            print("Source: ", source_path, "\nTarget: ", target_path)
            if pref.clean_target_path and target_path:
                try:
                    shutil.rmtree(target_path)
                    print("\nCleaned target path ", target_path)
                except:
                    pass
            try: 
                print("\nRestore1 to target path ", target_path)
                shutil.copytree(source_path, target_path) #python 3.8 will support dirs_exist_ok=True
            except FileExistsError:
                print("\nRestore2 to target path ", target_path)
                shutil.copytree(source_path, target_path) #dirs_exist_ok=True)

        return {'FINISHED'}





    def execute(self, context):     
        global version_list

        #print("self.button_input: ", self.button_input)        
        if self.button_input == 1:
            version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
        if self.button_input == 2:
            self.backup_version(bpy.utils.resource_path(type='USER'))   
        if self.button_input == 3:
            self.restore_version(bpy.utils.resource_path(type='USER'))   

        return {'FINISHED'}
    
    

class BackupManagerPreferences(AddonPreferences):
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
    
    current_version: StringProperty(
        name="Current Version", 
        description="Current Blender Version", 
        subtype='NONE',
        default=str(bpy.app.version[0]) + '.' + str(bpy.app.version[1]))

    custom_version: StringProperty(
        name="Custom Version", 
        description="Custom backup path", 
        subtype='NONE',
        default='')
        
    backup_path: StringProperty(
        name="Backup Location", 
        description="Backup Location", 
        subtype='DIR_PATH',
        default=bpy.app.tempdir)

    clean_target_path: BoolProperty(
        name="Clean Backup",
        description="delete old backup before backup",
        default=True)

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
        default=True)


    ## BACKUP
        
    backup_cache: BoolProperty(
        name="cache",
        description="backup_cache",
        default=True)
        
    backup_bookmarks: BoolProperty(
        name="bookmarks",
        description="backup_bookmarks",
        default=False)   
    backup_recentfiles: BoolProperty(
        name="recentfiles",
        description="backup_recentfiles",
        default=False) 
    backup_startup_blend: BoolProperty(
        name="startup.blend",
        description="backup_startup_blend",
        default=True)    
    backup_userpref_blend: BoolProperty(
        name="userpref.blend",
        description="backup_userpref_blend",
        default=True)   
    backup_workspaces_blend: BoolProperty(
        name="workspaces.blend",
        description="backup_workspaces_blend",
        default=True)  

    backup_datafile: BoolProperty(
        name="datafile",
        description="backup_datafile",
        default=True)        
    backup_addons: BoolProperty(
        name="addons",
        description="backup_addons",
        default=True)     
    backup_presets: BoolProperty(
        name="presets",
        description="backup_presets",
        default=True)


    ## RESTORE
    restore_cache: BoolProperty(
        name="cache",
        description="restore_cache",
        default=False)
        
    restore_bookmarks: BoolProperty(
        name="bookmarks",
        description="restore_bookmarks",
        default=False)   
    restore_recentfiles: BoolProperty(
        name="recentfiles",
        description="restore_recentfiles",
        default=False) 
    restore_startup_blend: BoolProperty(
        name="startup.blend",
        description="restore_startup_blend",
        default=True)    
    restore_userpref_blend: BoolProperty(
        name="userpref.blend",
        description="restore_userpref_blend",
        default=True)   
    restore_workspaces_blend: BoolProperty(
        name="workspaces.blend",
        description="restore_workspaces_blend",
        default=True)  

    restore_datafile: BoolProperty(
        name="datafile",
        description="restore_datafile",
        default=True)        
    restore_addons: BoolProperty(
        name="addons",
        description="restore_addons",
        default=True)     
    restore_presets: BoolProperty(
        name="presets",
        description="restore_presets",
        default=True)    

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
            

        col.label(text="Current Blender Version: " + self.current_version)   
        col.prop(self, 'use_custom_version')  
        col.prop(self, 'clean_target_path')   
        col.prop(self, 'backup_path')  


        col  = layout.column(align=False) 
        row = col.row()
        box = row.box()   
        col  = box.column(align=False) 
        #col.label(text="Current Blender Version: " + bpy.app.version_string)           
        col.operator("bm.check_versions", text="Backup", icon='COLORSET_04_VEC').button_input = 2          
        if self.use_custom_version:   
            col.operator("bm.check_versions", text="Search Backups", icon='COLORSET_03_VEC').button_input = 1  
            col.prop(self, 'bl_versions')   
            col.prop(self, 'custom_version')   
           
        col.prop(self, 'backup_cache') 
        col.prop(self, 'backup_bookmarks') 
        col.prop(self, 'backup_recentfiles') 
        col.prop(self, 'backup_startup_blend') 
        col.prop(self, 'backup_userpref_blend') 
        col.prop(self, 'backup_workspaces_blend') 
        col.prop(self, 'backup_datafile') 
        col.prop(self, 'backup_addons') 
        col.prop(self, 'backup_presets')  

        box = row.box()   
        col  = box.column(align=False) 
        #col.label(text="Current Blender Version: " + bpy.app.version_string)     
        col.operator("bm.check_versions", text="Restore", icon='COLORSET_01_VEC').button_input = 3 
        if self.use_custom_version:  
            col.operator("bm.check_versions", text="Search Backups", icon='COLORSET_03_VEC').button_input = 1   
            col.prop(self, 'bl_versions')  
            col.prop(self, 'custom_version')  
            
        col.prop(self, 'restore_cache') 
        col.prop(self, 'restore_bookmarks') 
        col.prop(self, 'restore_recentfiles') 
        col.prop(self, 'restore_startup_blend') 
        col.prop(self, 'restore_userpref_blend') 
        col.prop(self, 'restore_workspaces_blend') 
        col.prop(self, 'restore_datafile') 
        col.prop(self, 'restore_addons') 
        col.prop(self, 'restore_presets')  
       
         
classes = (
    OT_BackupManager,
    BackupManagerPreferences,
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
