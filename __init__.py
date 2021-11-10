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
    
    button_input: bpy.props.StringProperty()
    

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
    
    
    def create_path_index(self):
        path_index = []        
        if prefs().backup_cache or prefs().restore_cache:
            path_index.append(os.path.join('cache'))    
        if prefs().backup_bookmarks or prefs().restore_bookmarks:
            path_index.append(os.path.join('config', 'bookmarks.txt'))     
        if prefs().backup_recentfiles or prefs().restore_recentfiles:
            path_index.append(os.path.join('config', 'recent-files.txt'))     
        if prefs().backup_startup_blend or prefs().restore_startup_blend:
            path_index.append(os.path.join('config', 'startup.blend'))       
        if prefs().backup_userpref_blend or prefs().restore_userpref_blend:
            path_index.append(os.path.join('config', 'userpref.blend'))       
        if prefs().backup_workspaces_blend or prefs().restore_workspaces_blend:
            path_index.append(os.path.join('config', 'workspaces.blend'))         
        if prefs().backup_datafile or prefs().restore_datafile:
            path_index.append(os.path.join('datafiles'))        
        if prefs().backup_addons or prefs().restore_addons:
            path_index.append(os.path.join('scripts', 'addons'))         
        if prefs().backup_presets or prefs().restore_presets:
            path_index.append(os.path.join('scripts', 'presets'))
        return path_index


    def generate_version(self, input): 
        if input=='BACKUP':
            if prefs().backup_versions:
                version = prefs().backup_versions     
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])       
            return version

        if input=='RESTORE':
            if prefs().restore_versions:
                version = prefs().restore_versions 
            else:
                version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])   
            return version


    def generate_paths(self, roaming_path, path_index): 
        if prefs().use_system_id:
            backup_path  = os.path.join(prefs().backup_path, prefs().system_id)
        else:
            backup_path = prefs().backup_path

        if not prefs().advanced_mode:
            source_path = os.path.join(roaming_path, prefs().active_blender_version, path_index).replace("\\", "/")  
            target_path = os.path.join(backup_path, prefs().active_blender_version, path_index).replace("\\", "/")
        else:   
            if not prefs().custom_toggle:  
                source_path = os.path.join(roaming_path, self.generate_version(input='BACKUP'), path_index).replace("\\", "/")  
                target_path = os.path.join(backup_path, self.generate_version(input='RESTORE'), path_index).replace("\\", "/")
            else: 
                source_path = os.path.join(roaming_path, self.generate_version(input='BACKUP'), path_index).replace("\\", "/")  
                target_path = os.path.join(backup_path, prefs().custom_version, path_index).replace("\\", "/") 

        return source_path, target_path
            

    def transfer_files(self, source_path, target_path):   
        """ transfer the files from the source to the target directory  """
        try:
            if os.path.isdir(target_path):  #input is folder path
                print("isdir: ", os.path.isdir(source_path))
                try:     
                    print("source: ", source_path)  
                    print("target: ", target_path) 
                    if not prefs().dry_run:
                        print("target path: ", os.path.dirname(target_path)) 
                        #shutil.copy(source_path, target_path)    
                        shutil.rmtree(target_path)                       
                        #os.makedirs(target_path)
                        shutil.copytree(source_path, target_path)
                    else:
                        print("dry")
                except:  
                    print("failed file transfer")
            
            else:   #input is file path
                print("isdir: ", os.path.isdir(source_path))
                try:      
                    print("create target path: ", os.path.dirname(target_path))              
                    if not prefs().dry_run:
                        os.makedirs(os.path.dirname(target_path))
                        print("created target path: ", os.path.dirname(target_path))
                except:                    
                    print("target folder already exists: ", os.path.dirname(target_path))

                try:          
                    print("copy source files: ", source_path)          
                    if not prefs().dry_run:
                        shutil.copy2(source_path, target_path)
                except:                    
                    print("no source files to copy: ", source_path)

            print(40*"-")
        except:
            print("source_path not found")

        return{'FINISHED'}
    

    def run_backup(self, filepath, version): 
        filepath = os.path.dirname(filepath)
        
        # clean
        if prefs().clean_backup_path:
            try:
                shutil.rmtree(os.path.join(prefs().backup_path, version))
                print("\nCleaned target path ", os.path.join(prefs().backup_path, version))
            except:                
                print("\nfailed to clean path ", os.path.join(prefs().backup_path, version))
        
        # backup
        path_index = self.create_path_index()
        for i, target in enumerate(path_index):
            print("backing up: ", target.split("\\"))
            
            source_path, target_path = self.generate_paths(filepath, target)
            self.transfer_files(source_path, target_path)        

            if prefs().custom_version and prefs().custom_toggle:
                self.ShowReport(path_index, "Backup complete from: " + self.generate_version(input='BACKUP') + " to: " +  prefs().custom_version, 'COLORSET_07_VEC') 
            else:
                self.ShowReport(path_index, "Backup complete from: " + self.generate_version(input='BACKUP') + " to: " + self.generate_version(input='RESTORE'), 'COLORSET_07_VEC')

        self.report({'INFO'}, "Backup Complete")   
        return {'FINISHED'}


    def run_restore(self, filepath, version):                   
        filepath = os.path.dirname(filepath)
        
        if prefs().clean_restore_path:
            try:
                shutil.rmtree(os.path.join(filepath, version))
                print("\nCleaned target path ", os.path.join(filepath, version))
            except:
                print("\nfailed to clean path ", os.path.join(filepath, version))     
       
        path_index = self.create_path_index()  
        for i, target in enumerate(path_index):
            print("restoring: ", target.split("\\"))                  
            target_path, source_path  = self.generate_paths(filepath, target) #invert paths for restore
            self.transfer_files(source_path, target_path)

            if prefs().custom_version and prefs().custom_toggle:
                self.ShowReport(path_index, "Restore Complete from: " + prefs().custom_version + " to: " + self.generate_version(input='BACKUP'), 'COLORSET_14_VEC')
            else:
                self.ShowReport(path_index, "Restore Complete from: " + self.generate_version(input='RESTORE') + " to: " + self.generate_version(input='BACKUP'), 'COLORSET_14_VEC')

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
            if self.button_input == 'BACKUP':  # backup
                version = self.generate_version(self.button_input)
                self.run_backup(bpy.utils.resource_path(type='USER'), version)   

            elif self.button_input == 'RESTORE':  # restore
                version = self.generate_version(self.button_input)
                self.run_restore(bpy.utils.resource_path(type='USER'), version) 
               
            elif self.button_input == 'SEARCH_BACKUP':  # search for backup versions 
                backup_version_list.clear() 
                backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER'))
                backup_version_list.sort(reverse=True)

                restore_version_list.clear()    
                restore_version_list = set(self.find_versions(prefs().backup_path) + backup_version_list)
                restore_version_list = list(dict.fromkeys(restore_version_list))
                restore_version_list.sort(reverse=True)
            
            elif self.button_input == 'SEARCH_RESTORE':  # search for restorable versions 
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
            col.label(text= "Backup Age: " + backup_age)
        except:
            col.label(text= "New Backup")
            pass

    def draw_backup_size(self, col, path):
        try:
            #initialize the size
            size = 0            
            #use the walk() method to navigate through directory tree
            for dirpath, dirnames, filenames in os.walk(path):
                for i in filenames:
                    
                    #use join to concatenate all the components of path
                    f = os.path.join(dirpath, i)
                    
                    #use getsize to generate size in bytes and add it to the total size
                    size += os.path.getsize(f)
            #print(round(total_size*0.000001, 2))
            col.label(text= "Backup Size: " + str(round(size * 0.000001, 2)) +" MB")
        except:
            pass


    def draw_backup(self, box):
        row  = box.row()            
        
        col = row.column()  
        col.prop(self, 'dry_run')  
        col.prop(self, 'clean_backup_path')  
        col.prop(self, 'advanced_mode')   

        col = row.column()
        col.scale_y = 3
        col.operator("bm.check_versions", text="Backup", icon='COLORSET_07_VEC').button_input = 'BACKUP'   

        box1 = row.box()
        col = box1.column()
        if not self.advanced_mode:
            col.label(text = "From: " + self.active_blender_version)            
            #self.draw_backup_age(col, self.active_blender_version) 
            col.separator(factor=3.7)    
            self.draw_backup_size(col, os.path.join(prefs().backup_path, str(self.active_blender_version)))
                   
            box = row.box() 
            col = box.column()  
            col.label(text = "To: " + self.active_blender_version)            
            self.draw_backup_age(col, self.active_blender_version)    
            self.draw_backup_size(col, os.path.join(prefs().backup_path, str(self.active_blender_version)))
        else:
             
            if self.custom_toggle:    
                col.label(text=OT_BackupManager.generate_version(self, input='BACKUP') + " --> " + self.custom_version)           
                self.draw_backup_age(col, self.custom_version)
                self.draw_backup_size(col, os.path.join(prefs().backup_path, self.custom_version))
            else:
                col.label(text= OT_BackupManager.generate_version(self, input='BACKUP') + " --> " + OT_BackupManager.generate_version(self, input='RESTORE'))           
                self.draw_backup_age(col, OT_BackupManager.generate_version(self, input='RESTORE'))
                self.draw_backup_size(col, os.path.join(prefs().backup_path, str(OT_BackupManager.generate_version(self, input='RESTORE'))))
                
 
        # Advanced options
        if self.advanced_mode: 
            box2 = box.box()
            row = box2.row().split(factor=0.7, align=False)
            row.prop(self, 'backup_versions', text='Backup From') 
            row.operator("bm.check_versions", text="Search").button_input = 'SEARCH_BACKUP' 

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
        col.prop(self, 'dry_run')      
        col.prop(self, 'clean_backup_path')   
        col.prop(self, 'advanced_mode')  
        
        col = row.column()
        col.scale_y = 3   
        col.operator("bm.check_versions", text="Restore", icon='COLORSET_14_VEC').button_input = 'RESTORE'

        col = row.column()
        if not self.advanced_mode:
            col.label(text=self.active_blender_version + " --> " + OT_BackupManager.generate_version(self, input='BACKUP'))     
            self.draw_backup_age(col, self.active_blender_version)
            self.draw_backup_size(col, os.path.join(prefs().backup_path, str(self.active_blender_version)))
        else:
            if self.custom_toggle:    
                col.label(text=self.custom_version + " --> " + OT_BackupManager.generate_version(self, input='BACKUP'))         
                self.draw_backup_age(col, self.custom_version)
                self.draw_backup_size(col, os.path.join(prefs().backup_path, self.custom_version))
            else:
                col.label(text=OT_BackupManager.generate_version(self, input='RESTORE') + " --> " + OT_BackupManager.generate_version(self, input='BACKUP'))
                self.draw_backup_age(col, OT_BackupManager.generate_version(self, input='RESTORE'))
                self.draw_backup_size(col, os.path.join(prefs().backup_path, str(OT_BackupManager.generate_version(self, input='RESTORE'))))
  
                
        # Advanced options
        if self.advanced_mode: 
            box2 = box.box()
            row = box2.row().split(factor=0.7, align=False)
            row.prop(self, 'restore_versions', text='Restore From') 
            row.operator("bm.check_versions", text="Search").button_input = 'SEARCH_RESTORE'  
            
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
    [bpy.utils.register_class(c) for c in classes]

def unregister():
    [bpy.utils.unregister_class(c) for c in classes]

if __name__ == "__main__":
    register()
