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
    "version": (0, 7, 0),
    "blender": (2, 83, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}

initial_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
backup_version_list = [(initial_version, initial_version, '')]
restore_version_list = [(initial_version, initial_version, '')]

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
        if filepath:
            path_preferences = f"{os.path.dirname(filepath)}"
            for v in os.listdir(path_preferences):
                version_list.append((v, v, ""))
        return version_list
    

    def transfer_files(self, source_path, target_path):       
        pref = bpy.context.preferences.addons[__package__].preferences 
        
        if source_path:
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
                    try:
                        print("copy file: ", source_path)
                        shutil.copy2(source_path, target_path)
                    except:                    
                        print("no source file to copy: ", source_path)

            print(40*"-")
        return{'FINISHED'}
    
    def create_path_index(self, type=''):
        pref = bpy.context.preferences.addons[__package__].preferences  
        path_list = []
        if type=='backup':
            if pref.backup_cache:
                path_list.append(os.path.join('cache'))    
            if pref.backup_bookmarks:
                path_list.append(os.path.join('config', 'bookmarks.txt'))     
            if pref.backup_recentfiles:
                path_list.append(os.path.join('config', 'recent-files.txt'))     
            if pref.backup_startup_blend:
                path_list.append(os.path.join('config', 'startup.blend'))       
            if pref.backup_userpref_blend:
                path_list.append(os.path.join('config', 'userpref.blend'))       
            if pref.backup_workspaces_blend:
                path_list.append(os.path.join('config', 'workspaces.blend'))         
            if pref.backup_datafile:
                path_list.append(os.path.join('datafiles'))        
            if pref.backup_addons:
                path_list.append(os.path.join('scripts', 'addons'))         
            if pref.backup_presets:
                path_list.append(os.path.join('scripts', 'presets'))

        elif type=='restore':
            if pref.restore_cache:
                path_list.append(os.path.join('cache'))    
            if pref.restore_bookmarks:
                path_list.append(os.path.join('config', 'bookmarks.txt'))    
            if pref.restore_recentfiles:
                path_list.append(os.path.join('config', 'recent-files.txt'))      
            if pref.restore_startup_blend:
                path_list.append(os.path.join('config', 'startup.blend'))
            if pref.restore_userpref_blend:
                path_list.append(os.path.join('config', 'userpref.blend'))       
            if pref.restore_workspaces_blend:
                path_list.append(os.path.join('config', 'workspaces.blend'))       
            if pref.restore_datafile:
                path_list.append(os.path.join('datafiles'))        
            if pref.restore_addons:
                path_list.append(os.path.join('scripts', 'addons'))     
            if pref.restore_presets:
                path_list.append(os.path.join('scripts', 'presets'))
        else:
            print("wrong input type")

        return path_list

    def generate_version(self, input):
        pref = bpy.context.preferences.addons[__package__].preferences  
        
        if input==1: #backup
            if pref.backup_versions:
                version = pref.backup_versions     
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])       
            return version

        if input==3: #Restore
            if pref.restore_versions:
                version = pref.restore_versions 
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])   
            return version
        """ else: 
            version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])   
            return version """
        

    def construct_paths(self, path, target):   
        pref = bpy.context.preferences.addons[__package__].preferences   
        print("\n\nbackup_path: ", pref.backup_path)
        if not pref.custom_mode:          
            print("TEST 1")
            source_path = os.path.join(path, pref.current_version, target).replace("\\", "/")  
            target_path = os.path.join(pref.backup_path, pref.current_version, target).replace("\\", "/")
        else:   
            if not pref.custom_version:   
                print("TEST 2")      
                source_path = os.path.join(path, self.generate_version(input=1), target).replace("\\", "/")  
                target_path = os.path.join(pref.backup_path, self.generate_version(input=3), target).replace("\\", "/")
            else: 
                print("TEST 3")  
                source_path = os.path.join(path, self.generate_version(input=1), target).replace("\\", "/")  
                target_path = os.path.join(pref.backup_path, pref.custom_path, target).replace("\\", "/") 

        return source_path, target_path


    def backup_version(self, filepath, version):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        backup_path = os.path.dirname(filepath)
        path_list = self.create_path_index(type='backup')


        if pref.clean_backup_path:
            try:
                shutil.rmtree(pref.backup_path + version)
                print("\nCleaned target path ", pref.backup_path + version)
            except:                
                print("\nfailed to clean path ", pref.backup_path + version)

        
        for i, target in enumerate(path_list):
            print(i, target) 

            source_path, target_path = self.construct_paths(backup_path, target)
            self.transfer_files(source_path, target_path)  
            
            if pref.custom_path and pref.custom_version:
                self.ShowReport(path_list, "Backup complete from: " + self.generate_version(input=1) + " to: " +  pref.custom_path, 'COLORSET_07_VEC') 
            else:
                self.ShowReport(path_list, "Backup completefrom: " + self.generate_version(input=1) + " to: " + self.generate_version(input=3), 'COLORSET_07_VEC')

        self.report({'INFO'}, "Backup Complete")            

        return {'FINISHED'}



    def restore_version(self, filepath, version):        
        pref = bpy.context.preferences.addons[__package__].preferences            
        restore_path = os.path.dirname(filepath)        
        path_list = self.create_path_index(type='restore')
        
        if pref.clean_restore_path:
            try:
                shutil.rmtree(os.path.join(restore_path, version))
                print("\nCleaned target path ", os.path.join(restore_path, version))
            except:
                print("\nfailed to clean path ", pref.backup_path + version)
        
       
        for i, target in enumerate(path_list):
            print(i, target)                        
            target_path, source_path  = self.construct_paths(restore_path, target) #invert paths for restore
            self.transfer_files(source_path, target_path)
                   
            if pref.custom_path and pref.custom_version:
                self.ShowReport(path_list, "Restore Complete from: " + pref.custom_path + " to: " + self.generate_version(input=1), 'COLORSET_14_VEC')
            else:
                self.ShowReport(path_list, "Restore Complete from: " + self.generate_version(input=3) + " to: " + self.generate_version(input=1), 'COLORSET_14_VEC')

        self.report({'INFO'}, "Restore Complete") 
        return {'FINISHED'}


    def ShowReport(self, message = [], title = "Message Box", icon = 'INFO'):
        def draw(self, context):
            for i in message:
                self.layout.label(text=i)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


    def execute(self, context): 
        #print("self.button_input: ", self.button_input)  
        pref = bpy.context.preferences.addons[__package__].preferences       
        if pref.backup_path:
            if self.button_input == 1:
                version = self.generate_version(self.button_input)
                self.backup_version(bpy.utils.resource_path(type='USER'), version)   
            if self.button_input == 2:
                global backup_version_list
                backup_version_list.clear() 
                backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
                #print(backup_version_list)

            if self.button_input == 3:
                version = self.generate_version(self.button_input)
                self.restore_version(bpy.utils.resource_path(type='USER'), version)   
            if self.button_input == 4: 
                global restore_version_list    
                restore_version_list.clear()        
                restore_version_list = self.find_versions(pref.backup_path)
                #print(restore_version_list)
        else:
            self.ShowReport(["specify a Backup Location"] , "Backup Path missing", 'COLORSET_01_VEC')

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
                
    backup_path: StringProperty(
        name="Backup Location", 
        description="Backup Location", 
        subtype='DIR_PATH',
        #default="C:/Temp/backupmanager/") 
        default=bpy.app.tempdir)

    custom_mode: BoolProperty(
        name="More Options",
        description="custom_mode",
        default=True, 
        update=None)    #TODO: search for backups when enabled

    test_mode: BoolProperty(
        name="Dry-Run",
        description="run code without modifying any files on the drive.NOTE: this will not create or restore any backups",
        default=True)    

    ## BACKUP        
    clean_backup_path: BoolProperty(
        name="Clean Backup",
        description="delete before backup",
        default=False)
        
    def populate_backuplist(self, context):
        global backup_version_list  
        return backup_version_list
    backup_versions: EnumProperty(
        items=populate_backuplist, 
        name="Verison", 
        description="Choose the version to backup")

    backup_cache: BoolProperty(
        name="cache",
        description="backup_cache",
        default=False)        
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
    custom_version: BoolProperty(
        name="Custom Version",
        description="replace_version_with_dir",
        default=False)  
    custom_path: StringProperty(
        name="Custom", 
        description="Custom version folder", 
        subtype='NONE',
        default='custom')
    clean_restore_path: BoolProperty(
        name="Clean Restore",
        description="delete before restore",
        default=False)

    def populate_restorelist(self, context):
        global restore_version_list
        return restore_version_list
    restore_versions: EnumProperty(
        items=populate_restorelist, 
        name="Version", 
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
        
        col  = layout.column(align=False) 
        col.prop(self, 'backup_path')  
        col.prop(self, 'custom_mode')  
        if self.custom_mode: 
            col.prop(self, 'test_mode')

        col  = layout.column(align=True) 
        row = col.row()
        box = row.box()   
        col  = box.column(align=True) 
        col.label(text="Blender Version: " + self.current_version)
        col.label(text="Computer Name: " + os.getenv('COMPUTERNAME')) 



        col  = layout.column(align=True) 
        row = col.row().split(factor=0.5, align=True)
        box = row.box()   
        col  = box.column(align=True)         
        if not self.custom_mode:
            col.label(text="Backup From: " + self.current_version)
            col.label(text="Backup To: " + self.current_version)
        else:
            if self.custom_version:    
                col.label(text="Backup From: " + OT_BackupManager.generate_version(self, input=1))
                col.label(text="Backup To: " + self.custom_path)
            else:
                col.label(text="Backup From: " + OT_BackupManager.generate_version(self, input=1))
                col.label(text="Backup To: " + OT_BackupManager.generate_version(self, input=3))


        box = row.box()   
        col  = box.column(align=True)          
        if not self.custom_mode:
            col.label(text="Backup To: " + self.current_version)
            col.label(text="Restore To: " + OT_BackupManager.generate_version(self, input=1))
        else:
            if self.custom_version:    
                col.label(text="Restore From: " + self.custom_path)
                col.label(text="Restore To: " + OT_BackupManager.generate_version(self, input=1))
            else:
                col.label(text="Restore From: " + OT_BackupManager.generate_version(self, input=3))
                col.label(text="Restore To: " + OT_BackupManager.generate_version(self, input=1))

        

        col  = layout.column(align=True) 
        row = col.row().split(factor=0.5, align=True)
        box = row.box()   
        col  = box.column(align=True)   
        col.operator("bm.check_versions", text="Backup", icon='COLORSET_07_VEC').button_input = 1          
        if self.custom_mode: 
            #col.prop(self, 'clean_backup_path')   
            col.separator_spacer()             
            row2 = col.row(align=True) 
            row2.prop(self, 'backup_versions')  
            row2.operator("bm.check_versions", text="Search").button_input = 2 
           
            col.separator_spacer()  
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
            #col.prop(self, 'clean_restore_path') 
            col.separator_spacer()     
            col.prop(self, 'custom_version')  
            if self.custom_version:                
                col.prop(self, 'custom_path')  
            else:
                row2 = col.row(align=True)   
                row2.prop(self, 'restore_versions')  
                row2.operator("bm.check_versions", text="Search").button_input = 4 

            col.separator_spacer()  
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
