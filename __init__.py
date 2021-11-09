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
from datetime import datetime
import shutil
import socket
import numpy
from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, EnumProperty, BoolProperty

bl_info = {
    "name": "Backup Manager",
    "description": "Backup and Restore your Blender configuration files",
    "author": "Daniel Grauer",
    "version": (1, 0, 0),
    "blender": (2, 93, 0),
    "location": "Preferences",
    "category": "!System",
    "wiki_url": "https://github.com/kromar/blender_BackupManager",
    "tracker_url": "https://github.com/kromar/blender_BackupManager/issues/new",
}

def prefs():
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences


initial_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
backup_version_list = [(initial_version, initial_version, '')]
restore_version_list = [(initial_version, initial_version, '')]

class OT_BackupManager(Operator):
    ''' backup manager '''
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
            try:
                path_preferences = os.path.dirname(filepath)
                for v in os.listdir(path_preferences):
                    version_list.append((v, v, ""))
            except:
                print("filepath invalid")
        return version_list
    

    def transfer_files(self, source_path, target_path):   
        try:
            if os.path.isdir(source_path):  #input is folder path
                try:     
                    print("source: ", source_path)  
                    print("target: ", target_path)     
                    if not prefs().dry_run:
                        shutil.copytree(source_path, target_path, symlinks=True)
                except:    
                    print("target folder exists, clean first: ", target_path)       
                    if not prefs().dry_run:  
                        #shutil.copy(source_path, target_path)    
                        shutil.rmtree(os.path.join(target_path))
                        shutil.copytree(source_path, target_path, symlinks=True)   
            
            else:   #input is file path
                try:                    
                    if prefs().dry_run:
                        print("create target path: ", os.path.dirname(target_path))
                    else:
                        print("create target path: ", os.path.dirname(target_path))
                        os.makedirs(os.path.dirname(target_path))
                except:                    
                    print("target folder already exists: ", os.path.dirname(target_path))

                if prefs().dry_run:
                    print("copy file1: ", source_path)
                else:
                    try:
                        print("copy file2: ", source_path)
                        shutil.copy2(source_path, target_path)
                    except:                    
                        print("no source file to copy: ", source_path)

            print(40*"-")
        except:
            print("source_path not found")

        return{'FINISHED'}
    

    def create_path_index(self, type=''):
        path_list = []
        if type=='backup':
            if prefs().backup_cache:
                path_list.append(os.path.join('cache'))    
            if prefs().backup_bookmarks:
                path_list.append(os.path.join('config', 'bookmarks.txt'))     
            if prefs().backup_recentfiles:
                path_list.append(os.path.join('config', 'recent-files.txt'))     
            if prefs().backup_startup_blend:
                path_list.append(os.path.join('config', 'startup.blend'))       
            if prefs().backup_userpref_blend:
                path_list.append(os.path.join('config', 'userpref.blend'))       
            if prefs().backup_workspaces_blend:
                path_list.append(os.path.join('config', 'workspaces.blend'))         
            if prefs().backup_datafile:
                path_list.append(os.path.join('datafiles'))        
            if prefs().backup_addons:
                path_list.append(os.path.join('scripts', 'addons'))         
            if prefs().backup_presets:
                path_list.append(os.path.join('scripts', 'presets'))

        elif type=='restore':
            if prefs().restore_cache:
                path_list.append(os.path.join('cache'))    
            if prefs().restore_bookmarks:
                path_list.append(os.path.join('config', 'bookmarks.txt'))    
            if prefs().restore_recentfiles:
                path_list.append(os.path.join('config', 'recent-files.txt'))      
            if prefs().restore_startup_blend:
                path_list.append(os.path.join('config', 'startup.blend'))
            if prefs().restore_userpref_blend:
                path_list.append(os.path.join('config', 'userpref.blend'))       
            if prefs().restore_workspaces_blend:
                path_list.append(os.path.join('config', 'workspaces.blend'))       
            if prefs().restore_datafile:
                path_list.append(os.path.join('datafiles'))        
            if prefs().restore_addons:
                path_list.append(os.path.join('scripts', 'addons'))     
            if prefs().restore_presets:
                path_list.append(os.path.join('scripts', 'presets'))
        else:
            print("wrong input type")

        return path_list


    def generate_version(self, input):        
        if input==1: #backup
            if prefs().backup_versions:
                version = prefs().backup_versions     
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])       
            return version

        if input==2: #Restore
            if prefs().restore_versions:
                version = prefs().restore_versions 
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])   
            return version
        

    def construct_paths(self, blender_path, target):    
        if prefs().use_system_id:
            backup_path  = os.path.join(prefs().backup_path, prefs().system_id)
        else:
            backup_path = prefs().backup_path

        if not prefs().advanced_mode:
            source_path = os.path.join(blender_path, prefs().active_blender_version, target).replace("\\", "/")  
            target_path = os.path.join(backup_path, prefs().active_blender_version, target).replace("\\", "/")
        else:   
            if not prefs().custom_toggle:  
                source_path = os.path.join(blender_path, self.generate_version(input=1), target).replace("\\", "/")  
                target_path = os.path.join(backup_path, self.generate_version(input=2), target).replace("\\", "/")
            else: 
                source_path = os.path.join(blender_path, self.generate_version(input=1), target).replace("\\", "/")  
                target_path = os.path.join(backup_path, prefs().custom_version, target).replace("\\", "/") 

        return source_path, target_path


    def run_backup(self, filepath, version): 
        filepath = os.path.dirname(filepath)
        path_list = self.create_path_index(type='backup')
        if prefs().clean_backup_path:
            try:
                shutil.rmtree(prefs().backup_path + version)
                print("\nCleaned target path ", prefs().backup_path + version)
            except:                
                print("\nfailed to clean path ", prefs().backup_path + version)
        
        for i, target in enumerate(path_list):
            print("backing up: ", target.split("\\"))
            source_path, target_path = self.construct_paths(filepath, target)
            self.transfer_files(source_path, target_path)              
            if prefs().custom_version and prefs().custom_toggle:
                self.ShowReport(path_list, "Backup complete from: " + self.generate_version(input=1) + " to: " +  prefs().custom_version, 'COLORSET_07_VEC') 
            else:
                self.ShowReport(path_list, "Backup complete from: " + self.generate_version(input=1) + " to: " + self.generate_version(input=2), 'COLORSET_07_VEC')

        self.report({'INFO'}, "Backup Complete")   
        return {'FINISHED'}


    def run_restore(self, filepath, version):                   
        filepath = os.path.dirname(filepath)        
        path_list = self.create_path_index(type='restore')        
        if prefs().clean_restore_path:
            try:
                shutil.rmtree(os.path.join(filepath, version))
                print("\nCleaned target path ", os.path.join(filepath, version))
            except:
                print("\nfailed to clean path ", prefs().backup_path + version)        
       
        for i, target in enumerate(path_list):
            print("restoring: ", target.split("\\"))                  
            target_path, source_path  = self.construct_paths(filepath, target) #invert paths for restore
            self.transfer_files(source_path, target_path)
            if prefs().custom_version and prefs().custom_toggle:
                self.ShowReport(path_list, "Restore Complete from: " + prefs().custom_version + " to: " + self.generate_version(input=1), 'COLORSET_14_VEC')
            else:
                self.ShowReport(path_list, "Restore Complete from: " + self.generate_version(input=2) + " to: " + self.generate_version(input=1), 'COLORSET_14_VEC')

        self.report({'INFO'}, "Restore Complete") 
        return {'FINISHED'}


    def ShowReport(self, message = [], title = "Message Box", icon = 'INFO'):
        def draw(self, context):
            for i in message:
                self.layout.label(text=i)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


    def execute(self, context): 
        #print("self.button_input: ", self.button_input)        
        if prefs().backup_path:            
            global backup_version_list
            global restore_version_list  
            if self.button_input == 1:  # backup
                version = self.generate_version(self.button_input)
                self.run_backup(bpy.utils.resource_path(type='USER'), version)   

            elif self.button_input == 2:  # restore
                version = self.generate_version(self.button_input)
                self.run_restore(bpy.utils.resource_path(type='USER'), version) 
               
            elif self.button_input == 3:  # search for backup versions 
                backup_version_list.clear() 
                backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
                backup_version_list.sort(reverse=True)

                restore_version_list.clear()    
                restore_version_list = set(self.find_versions(prefs().backup_path) + backup_version_list)
                restore_version_list = list(dict.fromkeys(restore_version_list))
                restore_version_list.sort(reverse=True)
            
            elif self.button_input == 4:  # search for restorable versions 
                backup_version_list.clear() 
                backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
                backup_version_list.sort(reverse=True)
  
                restore_version_list.clear()        
                restore_version_list = self.find_versions(prefs().backup_path)
                restore_version_list.sort(reverse=True)           

        else:
            self.ShowReport(["Specify a Backup Path"] , "Backup Path missing", 'COLORSET_01_VEC')
        return {'FINISHED'}
    

preferences_tabs = [("BACKUP", "Backup Options", ""),
                    ("RESTORE", "Restore Options", "")]

class BackupManagerPreferences(AddonPreferences):

    bl_idname = __package__

    tabs: EnumProperty(name="Tabs", items=preferences_tabs, default="BACKUP")   
    config_path: StringProperty( name="config_path", description="config_path", subtype='DIR_PATH', default=bpy.utils.user_resource('CONFIG')) #Resource type in [‘DATAFILES’, ‘CONFIG’, ‘SCRIPTS’, ‘AUTOSAVE’].
    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])
    system_id: StringProperty(name="ID", description="Current Computer Name", subtype='NONE', default=str(socket.getfqdn()))  
    use_system_id: BoolProperty(name="use_system_id", description="use_system_id", default=False)  
    active_blender_version: StringProperty(name="Current Blender Version", description="Current Blender Version", subtype='NONE', default=str(bpy.app.version[0]) + '.' + str(bpy.app.version[1]))
    
    # when user specified a custom temp path use that one as default, otherwise use the app default
    if bpy.context.preferences.filepaths.temporary_directory == None:
        default_path = bpy.app.tempdir
    else: 
        default_path = bpy.context.preferences.filepaths.temporary_directory 
    
    dry_run: BoolProperty(name="Dry Run", description="Run code without modifying any files on the drive. NOTE: this will not create or restore any backups!", default=True)    
    
    """ if use_system_id:
        path = os.path.join(default_path , '!backupmanager', system_id)     #.replace("\\", "/")        
    else:
        path = os.path.join(default_path , '!backupmanager')    #.replace("\\", "/") """

    backup_path: StringProperty(name="Backup Path", description="Backup Location", subtype='DIR_PATH', default=os.path.join(default_path , '!backupmanager/').replace("\\", "/"))
    
    advanced_mode: BoolProperty(name="Advanced", description="Advanced custom backup and restore options", default=False, update=None)    #TODO: search for backups when enabled
    
    # BACKUP        
    clean_backup_path: BoolProperty(name="Clean Backup", description="delete before backup", default=False)
    def populate_backuplist(self, context):
        global backup_version_list  
        return backup_version_list
    backup_versions: EnumProperty( items=populate_backuplist, name="Backup", description="Choose the version to backup")
    backup_cache: BoolProperty(name="cache", description="backup_cache", default=False)        
    backup_bookmarks: BoolProperty(name="bookmarks", description="backup_bookmarks", default=False)   
    backup_recentfiles: BoolProperty(name="recentfiles", description="backup_recentfiles", default=False) 
    backup_startup_blend: BoolProperty( name="startup.blend", description="backup_startup_blend", default=True)    
    backup_userpref_blend: BoolProperty(name="userpref.blend", description="backup_userpref_blend", default=True)   
    backup_workspaces_blend: BoolProperty(name="workspaces.blend", description="backup_workspaces_blend", default=True)  
    backup_datafile: BoolProperty( name="datafile", description="backup_datafile", default=True)        
    backup_addons: BoolProperty(name="addons", description="backup_addons", default=True)     
    backup_presets: BoolProperty(name="presets", description="backup_presets", default=True)

    ## RESTORE   
    custom_toggle: BoolProperty(name="Custom", description="replace_version_with_dir", default=False)  
    custom_version: StringProperty(name="Custom Path", description="Custom version folder", subtype='NONE', default='custom')
    clean_restore_path: BoolProperty(name="Clean Backup", description="Wipe target folder before creating backup", default=False)
    def populate_restorelist(self, context):
        global restore_version_list
        return restore_version_list
    restore_versions: EnumProperty(items=populate_restorelist, name="Restore", description="Choose the version to Resotre")
    restore_cache: BoolProperty(name="cache", description="restore_cache", default=False)        
    restore_bookmarks: BoolProperty(name="bookmarks", description="restore_bookmarks", default=False)   
    restore_recentfiles: BoolProperty(name="recentfiles", description="restore_recentfiles", default=False) 
    restore_startup_blend: BoolProperty(name="startup.blend", description="restore_startup_blend",  default=True)    
    restore_userpref_blend: BoolProperty(name="userpref.blend", description="restore_userpref_blend", default=True)   
    restore_workspaces_blend: BoolProperty(name="workspaces.blend", description="restore_workspaces_blend", default=True)  
    restore_datafile: BoolProperty(name="datafile", description="restore_datafile", default=True)        
    restore_addons: BoolProperty(name="addons", description="restore_addons", default=True)     
    restore_presets: BoolProperty(name="presets", description="restore_presets", default=True)    


    # DRAW Preferences      
    def draw(self, context):
        layout = self.layout        
        box = layout.box() 
        col  = box.column(align=False)  
        
        col.use_property_split = True 
        col.enabled = False
        col.prop(self, 'system_id')
        col.prop(self, 'active_blender_version')  

        col  = box.column(align=False)  
        col.use_property_split = True 
        col.prop(self, 'backup_path') 
        col.prop(self, 'use_system_id')
        
        col  = box.column(align=False)         
        col.use_property_split = True        

        # TAB BAR
        layout.use_property_split = False
        col = layout.column(align=True) #.split(factor=0.5)  
        row = col.row()        
        row.prop(self, "tabs", expand=True)
        #row.direction = 'VERTICAL'
        box = col.box()
        if self.tabs == "BACKUP":
            self.draw_backup(box)
        elif self.tabs == "RESTORE":
            self.draw_restore(box)


    def draw_backup_age(self, col, version):              
        try:
            date_file = os.path.getmtime(os.path.join(self.backup_path, version))
            backup_date = datetime.fromtimestamp(date_file)
            current_time = datetime.now()
            backup_age = str(current_time - backup_date).split('.')[0]  
            col.label(text= " Backup Age: " + str(version) + " (" + backup_age +")")
        except:
            pass

    def draw_backup_size(self, col, version, path):
        try:
            #initialize the size
            total_size = 0
            
            #use the walk() method to navigate through directory tree
            for dirpath, dirnames, filenames in os.walk(path):
                for i in filenames:
                    
                    #use join to concatenate all the components of path
                    f = os.path.join(dirpath, i)
                    
                    #use getsize to generate size in bytes and add it to the total size
                    total_size += os.path.getsize(f)
            #print(round(total_size*0.000001, 2))
            col.label(text= " Backup Size: " + str(version) + " (" + str(round(total_size*0.000001, 2)) +"MB)")
        except:
            pass


    def draw_backup(self, box):
        row  = box.row()     
        col = row.column()

        if not self.advanced_mode:
            col.label(text=self.active_blender_version + " --> " + self.active_blender_version)            
            self.draw_backup_age(col, self.active_blender_version)
            self.draw_backup_size(col, self.active_blender_version, os.path.join(prefs().backup_path, str(self.active_blender_version)))
        else:
            if self.custom_toggle:    
                col.label(text=OT_BackupManager.generate_version(self, input=1) + " --> " + self.custom_version)           
                self.draw_backup_age(col, self.custom_version)
            else:
                col.label(text= OT_BackupManager.generate_version(self, input=1) + " --> " + OT_BackupManager.generate_version(self, input=2))           
                self.draw_backup_age(col, OT_BackupManager.generate_version(self, input=2))

        col.scale_y = 1
        col.operator("bm.check_versions", text="Backup", icon='COLORSET_07_VEC').button_input = 1   
         
        row = col.row()
        row.prop(self, 'advanced_mode')    
        row.prop(self, 'clean_backup_path')      
        row.prop(self, 'dry_run') 

        # Advanced options
        if self.advanced_mode: 
            box2 = box.box()
            row = box2.row().split(factor=0.7, align=False)
            row.prop(self, 'backup_versions', text='Backup From') 
            row.operator("bm.check_versions", text="Search").button_input = 3 

            #custom version
            row = box2.row().split(factor=0.7, align=False)           
            if self.custom_toggle:                
                row.prop(self, 'custom_version', text='Backup To')  
            else:
                row.prop(self, 'restore_versions', text='Backup To')
            row.prop(self, 'custom_toggle')                          
            self.draw_selection(box)
       
        
    def draw_restore(self, box):
        row  = box.row()  
        col = row.column()   
        if not self.advanced_mode:
            col.label(text=self.active_blender_version + " --> " + OT_BackupManager.generate_version(self, input=1))     
            self.draw_backup_age(col, self.active_blender_version)
        else:
            if self.custom_toggle:    
                col.label(text=self.custom_version + " --> " + OT_BackupManager.generate_version(self, input=1))         
                self.draw_backup_age(col, self.custom_version)
            else:
                col.label(text=OT_BackupManager.generate_version(self, input=2) + " --> " + OT_BackupManager.generate_version(self, input=1))
                self.draw_backup_age(col, OT_BackupManager.generate_version(self, input=2))

        col.scale_y = 1      
        col.operator("bm.check_versions", text="Restore", icon='COLORSET_14_VEC').button_input = 2  
        row = col.row()
        row.prop(self, 'advanced_mode')    
        row.prop(self, 'clean_backup_path')      
        row.prop(self, 'dry_run')       
                
        # Advanced options
        if self.advanced_mode: 
            box2 = box.box()
            row = box2.row().split(factor=0.7, align=False)
            row.prop(self, 'restore_versions', text='Restore From') 
            row.operator("bm.check_versions", text="Search").button_input = 4  
            
            row = box2.row().split(factor=0.691, align=False)            
            row.prop(self, 'backup_versions', text='Restore To')            
            self.draw_selection(box)

  
    def draw_selection(self, box):        
            box = box.box()
            row = box.row()            
            col = row.column() 
            col.prop(self, 'backup_addons') 
            col.prop(self, 'backup_presets')  
            col.prop(self, 'backup_datafile') 

            col = row.column()  
            col.prop(self, 'backup_startup_blend') 
            col.prop(self, 'backup_userpref_blend') 
            col.prop(self, 'backup_workspaces_blend') 
            
            col = row.column()  
            col.prop(self, 'backup_cache') 
            col.prop(self, 'backup_bookmarks') 
            col.prop(self, 'backup_recentfiles') 


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
