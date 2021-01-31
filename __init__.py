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
import numpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, EnumProperty, BoolProperty

bl_info = {
    "name": "Backup Manager",
    "description": "Backup and Restore your Blender configuration files",
    "author": "Daniel Grauer",
    "version": (0, 5, 0),
    "blender": (2, 83, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}


backup_version_list = []
restore_version_list = []

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
        version_list = []
        path_preferences = f"{os.path.dirname(filepath)}"
        for v in os.listdir(path_preferences):
            version_list.append((v, v, ""))
        return version_list
    

    def transfer_files(self, source_path, target_path):       
        pref = bpy.context.preferences.addons[__package__].preferences 
        
        if os.path.isdir(source_path):  #input is folder path
            try:     
                print("target folder: ", target_path)  
                print("copy folder: ", source_path)     
                if not pref.test_mode:
                    shutil.copytree(source_path, target_path, symlinks=True)
            except:    
                print("target folder exists, clean first: ", target_path)       
                if not pref.test_mode:  
                    #shutil.copy(source_path, target_path)    
                    shutil.rmtree(os.path.join(target_path))
                    shutil.copytree(source_path, target_path, symlinks=True)   
        
        else:   #input is file path
            try:                    
                if pref.test_mode:
                    print("create target path: ", os.path.dirname(target_path))
                else:
                    print("create target path: ", os.path.dirname(target_path))
                    os.makedirs(os.path.dirname(target_path))
            except:                    
                print("target folder already exists: ", os.path.dirname(target_path))

            if pref.test_mode:
                print("copy file: ", source_path)
            else:
                print("copy file: ", source_path)
                shutil.copy2(source_path, target_path)
        print(40*"-")
        return{'FINISHED'}


    def backup_version(self, filepath):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        backup_path = os.path.dirname(filepath)

        if pref.backup_versions:
            version = pref.backup_versions
            print("\nBacking up selected version ", version, "\n", 80*"=")
        else:
            version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
            print("\nBacking up current version ", version, "\n", 80*"=")

        path_list = []
        if pref.backup_cache:
            path_list.append(os.path.join(version, 'cache'))    
        if pref.backup_bookmarks:
            path_list.append(os.path.join(version, 'config', 'bookmarks.txt'))     
        if pref.backup_recentfiles:
            path_list.append(os.path.join(version, 'config', 'recent-files.txt'))     
        if pref.backup_startup_blend:
            path_list.append(os.path.join(version, 'config', 'startup.blend'))       
        if pref.backup_userpref_blend:
            path_list.append(os.path.join(version, 'config', 'userpref.blend'))       
        if pref.backup_workspaces_blend:
            path_list.append(os.path.join(version, 'config', 'workspaces.blend'))         
        if pref.backup_datafile:
            path_list.append(os.path.join(version, 'datafiles'))        
        if pref.backup_addons:
            path_list.append(os.path.join(version, 'scripts', 'addons'))         
        if pref.backup_presets:
            path_list.append(os.path.join(version, 'scripts', 'presets'))

        if pref.clean_backup_path:
            try:
                shutil.rmtree(pref.backup_path + version)
                print("\nCleaned target path ", pref.backup_path + version)
            except:                
                print("\nfailed to clean path ", pref.backup_path + version)

        for i, target in enumerate(path_list):
            print(i, target)
            source_path = os.path.join(backup_path, target).replace("\\", "/")
            target_path =  os.path.join(pref.backup_path + target).replace("\\", "/")                        
            self.transfer_files(source_path, target_path)  
            self.ShowReport(path_list, "Backup complete", 'COLORSET_07_VEC') 
            
        self.report({'INFO'}, "Backup Complete")            

        return {'FINISHED'}



    def restore_version(self, filepath):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        restore_path = os.path.dirname(filepath)

        if pref.backup_versions:
            version = pref.backup_versions
            print("\nRestoring up selected version ", version)
        else:
            version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
            print("\nRestoring up current version ", version)

        path_list = []
        if pref.restore_cache:
            path_list.append(os.path.join(version, 'cache'))    
        if pref.restore_bookmarks:
            path_list.append(os.path.join(version, 'config', 'bookmarks.txt'))    
        if pref.restore_recentfiles:
            path_list.append(os.path.join(version, 'config', 'recent-files.txt'))      
        if pref.restore_startup_blend:
            path_list.append(os.path.join(version, 'config', 'startup.blend'))
        if pref.restore_userpref_blend:
            path_list.append(os.path.join(version, 'config', 'userpref.blend'))       
        if pref.restore_workspaces_blend:
            path_list.append(os.path.join(version, 'config', 'workspaces.blend'))       
        if pref.restore_datafile:
            path_list.append(os.path.join(version, 'datafiles'))        
        if pref.restore_addons:
            path_list.append(os.path.join(version, 'scripts', 'addons'))     
        if pref.restore_presets:
            path_list.append(os.path.join(version, 'scripts', 'presets'))
        
        if pref.clean_restore_path:
            try:
                shutil.rmtree(os.path.join(restore_path, version))
                print("\nCleaned target path ", os.path.join(restore_path, version))
            except:
                print("\nfailed to clean path ", pref.backup_path + version)
        
       
        for i, target in enumerate(path_list):
            print(i, target)
            target_path = os.path.join(restore_path, target).replace("\\", "/")
            source_path =  os.path.join(pref.backup_path + target).replace("\\", "/") 
            self.transfer_files(source_path, target_path)
            self.ShowReport(path_list, "Restore Complete", 'COLORSET_14_VEC')

        self.report({'INFO'}, "Restore Complete") 
        return {'FINISHED'}


    def ShowReport(self, message = [], title = "Message Box", icon = 'INFO'):
        def draw(self, context):
            for i in message:
                self.layout.label(text=i)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


    def execute(self, context): 
        #print("self.button_input: ", self.button_input)        
        if self.button_input == 1:
            self.backup_version(bpy.utils.resource_path(type='USER'))   
        if self.button_input == 2:
            global backup_version_list
            backup_version_list.clear() 
            backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
            #print(backup_version_list)

        if self.button_input == 3:
            self.restore_version(bpy.utils.resource_path(type='USER'))   
        if self.button_input == 4: 
            global restore_version_list    
            restore_version_list.clear()       
            pref = bpy.context.preferences.addons[__package__].preferences  
            restore_version_list = self.find_versions(pref.backup_path)
            #print(restore_version_list)

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
    
    test_mode: BoolProperty(
        name="dry run",
        description="run code without modifying any files on the drive.NOTE: this will not create or restore any backups",
        default=True)    

    current_version: StringProperty(
        name="Current Version", 
        description="Current Blender Version", 
        subtype='NONE',
        default=str(bpy.app.version[0]) + '.' + str(bpy.app.version[1]))

    custom_backup_version: StringProperty(
        name="Custom Version", 
        description="Custom backup path", 
        subtype='NONE',
        default='')
        
    custom_restore_version: StringProperty(
        name="Custom Version", 
        description="Custom restore path", 
        subtype='NONE',
        default='')
        
    backup_path: StringProperty(
        name="Backup Location", 
        description="Backup Location", 
        subtype='DIR_PATH',
        default="C:/Temp/backupmanager/") #bpy.app.tempdir)

    clean_backup_path: BoolProperty(
        name="Clean Backup",
        description="delete before backup",
        default=False)
        
    clean_restore_path: BoolProperty(
        name="Clean Restore",
        description="delete before restore",
        default=False)

    custom_mode: BoolProperty(
        name="More Options",
        description="custom_mode",
        default=True, 
        update=None)    #TODO: search for backups when enabled


    ## BACKUP
        
    def populate_backuplist(self, context):
        global backup_version_list   
        return backup_version_list

    backup_versions: EnumProperty(
        items=populate_backuplist, 
        name="Backup Verison", 
        description="Choose the version to backup")

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
    

    def populate_restorelist(self, context):
        global restore_version_list
        return restore_version_list
    restore_versions: EnumProperty(
        items=populate_restorelist, 
        name="Resotre Verison", 
        description="Choose the version to Resotre")

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

        col.label(text="Current Blender Version: " + self.current_version)  
        col.prop(self, 'custom_mode')  
        col.prop(self, 'backup_path')  
        col.prop(self, 'test_mode')  

        col  = layout.column(align=False) 
        row = col.row()
        box = row.box()   
        col  = box.column(align=True)   
        col.operator("bm.check_versions", text="Backup", icon='COLORSET_07_VEC').button_input = 1          
        if self.custom_mode: 
            col.prop(self, 'clean_backup_path')   
            col.separator_spacer()              
            row2 = col.row() 
            row2.prop(self, 'backup_versions')  
            row2.operator("bm.check_versions", text="Search").button_input = 2  
            col.prop(self, 'custom_backup_version')   
           
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
        col  = box.column(align=True)           
        col.operator("bm.check_versions", text="Restore", icon='COLORSET_14_VEC').button_input = 3             
        if self.custom_mode:  
            col.prop(self, 'clean_restore_path') 
            col.separator_spacer()                    
            row2 = col.row()   
            row2.prop(self, 'restore_versions')  
            row2.operator("bm.check_versions", text="Search").button_input = 4 
            col.prop(self, 'custom_restore_version')  

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
