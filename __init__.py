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
    "version": (1, 1, 0),
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
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    button_input: bpy.props.StringProperty()
    ignore_backup = []
    ignore_restore = []

    def max_list_value(self, list):
        i = numpy.argmax(list)
        v = list[i]
        return (i, v)


    def find_versions(self, filepath):
        version_list = []
        try:
            for folder in os.listdir(os.path.dirname(filepath)):
                #[(identifier, name, description, icon, number), ...]
                #print("filepath: ", folder)
                version_list.append((folder, folder, ''))
        except:
            print("filepath invalid: ", filepath)
        return version_list
    
    
    def create_ignore_pattern(self):
        self.ignore_backup.clear()
        self.ignore_restore.clear()

        if not prefs().backup_bookmarks:
            self.ignore_backup.append('bookmarks.txt')
        if not prefs().restore_bookmarks:
            self.ignore_restore.append('bookmarks.txt')
        if not prefs().backup_recentfiles:
            self.ignore_backup.append('recent-files.txt')
        if not prefs().restore_recentfiles:
            self.ignore_restore.append('recent-files.txt')   

        if not prefs().backup_startup_blend:
            self.ignore_backup.append('startup.blend')
        if not prefs().restore_startup_blend:
            self.ignore_restore.append('startup.blend')            
        if not prefs().backup_userpref_blend:
            self.ignore_backup.append('userpref.blend')
        if not prefs().restore_userpref_blend:
            self.ignore_restore.append('userpref.blend')            
        if not prefs().backup_workspaces_blend:
            self.ignore_backup.append('workspaces.blend')
        if not prefs().restore_workspaces_blend:
            self.ignore_restore.append('workspaces.blend')  

        if not prefs().backup_cache:
            self.ignore_backup.append('cache')
        if not prefs().restore_cache:
            self.ignore_restore.append('cache')
        if not prefs().backup_datafile:
            self.ignore_backup.append('datafiles')
        if not prefs().restore_datafile:
            self.ignore_restore.append('datafiles')
        if not prefs().backup_addons:
            self.ignore_backup.append('addons')
        if not prefs().restore_addons:
            self.ignore_restore.append('addons')
        if not prefs().backup_presets:
            self.ignore_backup.append('presets')
        if not prefs().restore_presets:
            self.ignore_restore.append('presets')
    

    def recursive_overwrite(self, src, dest, ignore=None):
        if os.path.isdir(src):
            if not os.path.isdir(dest):
                os.makedirs(dest)
            files = os.listdir(src)
            if ignore is not None:
                ignored = ignore(src, files)
            else:
                ignored = set()
            for f in files:
                if f not in ignored:
                    self.recursive_overwrite(os.path.join(src, f), 
                                        os.path.join(dest, f), 
                                        ignore)
        else:
            shutil.copyfile(src, dest)


    def run_backup(self, source_path, target_path):         
        if prefs().clean_path:
            if os.path.exists(target_path):
                os.system('rmdir /S /Q "{}"'.format(target_path))
                #shutil.rmtree(target_path, onerror = self.handler)
                print("\nCleaned path: ", target_path)
            else:                
                print("\nFailed to clean path: ", target_path)

        # backup
        self.create_ignore_pattern()
        #self.transfer_files(source_path, target_path)   
        print("source: ",  source_path)
        print("target: ", target_path)
    
        if os.path.isdir(source_path): 
            if not prefs().dry_run:
                self.recursive_overwrite(source_path, target_path,  ignore = shutil.ignore_patterns(*self.ignore_backup))                
            else:
                print("dry run, no files modified")
        """ 
        if prefs().custom_version and prefs().custom_version_toggle:
            self.ShowReport(path_index, "Backup complete from: " + self.generate_version(input='BACKUP') + " to: " +  prefs().custom_version, 'COLORSET_07_VEC') 
        else:
            self.ShowReport(path_index, "Backup complete from: " + self.generate_version(input='BACKUP') + " to: " + self.generate_version(input='RESTORE'), 'COLORSET_07_VEC')
        #"""
        print(40*"-")
        self.report({'INFO'}, "Backup Complete")   
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
            if self.button_input == 'BACKUP':         
                if not prefs().advanced_mode:            
                    source_path = os.path.join(prefs().blender_user_path).replace("\\", "/")
                    target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")                    
                else:                                                 
                    if prefs().custom_version_toggle:
                        source_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  prefs().backup_versions).replace("\\", "/")
                        target_path = os.path.join(prefs().backup_path, str(prefs().custom_version)).replace("\\", "/")
                    else:                
                        source_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  prefs().backup_versions).replace("\\", "/")
                        target_path = os.path.join(prefs().backup_path, prefs().restore_versions).replace("\\", "/")
                self.run_backup(source_path, target_path)  
            
            elif self.button_input == 'BATCH_BACKUP':
                for version in backup_version_list:
                    print(version[0])
                    source_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  version[0]).replace("\\", "/")
                    target_path = os.path.join(prefs().backup_path, version[0]).replace("\\", "/")
                    self.run_backup(source_path, target_path)   

            elif self.button_input == 'RESTORE':
                if not prefs().advanced_mode:            
                    source_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")
                    target_path = os.path.join(prefs().blender_user_path).replace("\\", "/")
                else:             
                    source_path = os.path.join(prefs().backup_path, prefs().restore_versions).replace("\\", "/")
                    target_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  prefs().backup_versions).replace("\\", "/")
                self.run_backup(source_path, target_path) 
               
            elif self.button_input == 'SEARCH_BACKUP':
                backup_version_list.clear() 
                backup_version_list = self.find_versions(bpy.utils.resource_path(type='USER').strip(prefs().active_blender_version))
                backup_version_list.sort(reverse=True)

                restore_version_list.clear()    
                restore_version_list = set(self.find_versions(prefs().backup_path) + backup_version_list)
                restore_version_list = list(dict.fromkeys(restore_version_list))
                restore_version_list.sort(reverse=True)
            
            elif self.button_input == 'SEARCH_RESTORE': 
                restore_version_list.clear()        
                restore_version_list = self.find_versions(prefs().backup_path)
                restore_version_list.sort(reverse=True) 

                backup_version_list.clear() 
                backup_version_list = set(self.find_versions(bpy.utils.resource_path(type='USER').strip(prefs().active_blender_version)) + restore_version_list)
                backup_version_list = list(dict.fromkeys(backup_version_list))
                for version in backup_version_list: # remove custom items from list (assuming non floats are invalid)
                    try:
                        float(version[0])
                    except:
                        backup_version_list.remove(version)
                backup_version_list.sort(reverse=True)     

        else:
            self.ShowReport(["Specify a Backup Path"] , "Backup Path missing", 'COLORSET_04_VEC')
        return {'FINISHED'}
    

preferences_tabs = [("BACKUP", "Backup Options", ""),
                    ("RESTORE", "Restore Options", "")]

class BackupManagerPreferences(AddonPreferences):
    bl_idname = __package__  
    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])  

    def update_version_list(self, context):
        bpy.ops.bm.run_backup_manager(button_input='SEARCH_' + self.tabs)        

    # when user specified a custom temp path use that one as default, otherwise use the app default
    if bpy.context.preferences.filepaths.temporary_directory:        
        default_path = bpy.context.preferences.filepaths.temporary_directory 
    else: 
        default_path = bpy.app.tempdir
    """ 
    def update_system_id(self, context):
        if self.use_system_id:
            default_path = os.path.join(self.default_path , '!backupmanager/', self.system_id)
        else:            
            default_path = os.path.join(self.default_path , '!backupmanager/')            
        print(default_path) 
    #"""

    print("Backup Manager Default path: ", default_path)

    backup_path: StringProperty(name="Backup Path", description="Backup Location", subtype='DIR_PATH', default=os.path.join(default_path , '!backupmanager/'), update=update_version_list)
    blender_user_path: bpy.props.StringProperty(default=bpy.utils.resource_path(type='USER'))
    tabs: EnumProperty(name="Tabs", items=preferences_tabs, default="BACKUP", update=update_version_list)   
    config_path: StringProperty( name="config_path", description="config_path", subtype='DIR_PATH', default=bpy.utils.user_resource('CONFIG')) #Resource type in [‘DATAFILES’, ‘CONFIG’, ‘SCRIPTS’, ‘AUTOSAVE’].
    system_id: StringProperty(name="ID", description="Current Computer Name", subtype='NONE', default=str(socket.getfqdn()))  
    #use_system_id: BoolProperty(name="Use System ID", description="use_system_id", update=update_system_id, default=False)  
    active_blender_version: StringProperty(name="Current Blender Version", description="Current Blender Version", subtype='NONE', default=this_version)
    dry_run: BoolProperty(name="Dry Run", description="Run code without modifying any files on the drive. NOTE: this will not create or restore any backups!", default=False)    
    advanced_mode: BoolProperty(name="Advanced", description="Advanced backup and restore options", default=False, update=update_version_list)
    expand_version_selection: BoolProperty(name="Expand Versions", description="Switch between dropdown and expanded version layout", default=False, update=update_version_list)
    # BACKUP  
    custom_version_toggle: BoolProperty(name="Custom Version", description="Set your custom backup version", default=False, update=update_version_list)  
    custom_version: StringProperty(name="Custom Version", description="Custom version folder", subtype='NONE', default='custom')

    clean_path: BoolProperty(name="Clean Backup", description="delete before backup", default=False)
    def populate_backuplist(self, context):
        global backup_version_list  
        return backup_version_list
    backup_versions: EnumProperty(items=populate_backuplist, name="Backup", description="Choose the version to backup")
    backup_cache: BoolProperty(name="cache", description="backup_cache", default=False)      
    backup_bookmarks: BoolProperty(name="bookmarks", description="backup_bookmarks", default=True)   
    backup_recentfiles: BoolProperty(name="recentfiles", description="backup_recentfiles", default=True) 
    backup_startup_blend: BoolProperty( name="startup.blend", description="backup_startup_blend", default=True)    
    backup_userpref_blend: BoolProperty(name="userpref.blend", description="backup_userpref_blend", default=True)   
    backup_workspaces_blend: BoolProperty(name="workspaces.blend", description="backup_workspaces_blend", default=True)  
    backup_datafile: BoolProperty( name="datafile", description="backup_datafile", default=True)        
    backup_addons: BoolProperty(name="addons", description="backup_addons", default=True)     
    backup_presets: BoolProperty(name="presets", description="backup_presets", default=True)

    ## RESTORE   
    
    def populate_restorelist(self, context):
        global restore_version_list
        return restore_version_list        
    restore_versions: EnumProperty(items=populate_restorelist, name="Restore", description="Choose the version to Resotre")
    restore_cache: BoolProperty(name="cache", description="restore_cache", default=False)   
    restore_bookmarks: BoolProperty(name="bookmarks", description="restore_bookmarks", default=True)   
    restore_recentfiles: BoolProperty(name="recentfiles", description="restore_recentfiles", default=True) 
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
        #col.prop(self, 'use_system_id')
        
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


    def draw_backup_age(self, col, path):       
        try:
            files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(path) for f in filenames]
            latest_file = max(files, key=os.path.getmtime)            
            current_time = datetime.now()
            backup_date = datetime.fromtimestamp(os.path.getmtime(latest_file))       
            backup_age = str(current_time - backup_date).split('.')[0]             
            col.label(text= "Last change: " + backup_age)
        except:
            col.label(text= "no data")


    def draw_backup_size(self, col, path):
        try:
            #initialize the size
            size = 0            
            #use the walk() method to navigate through directory tree
            for dirpath, dirnames, filenames in os.walk(path):
                for i in filenames:                  
                    #use join to concatenate all the components of path
                    f = os.path.join(dirpath, i).replace("\\", "/")
                    #use getsize to generate size in bytes and add it to the total size
                    size += os.path.getsize(f)
            #print(path, "\nsize: ", round(size*0.000001, 2))
            col.label(text= "Size: " + str(round(size * 0.000001, 2)) +" MB  (" + "{:,}".format(size) + " bytes)")
        except:
            pass


    def draw_backup(self, box): 

        row  = box.row()
        box1 = row.box() 
        col = box1.column()
        if not self.advanced_mode:            
            path = self.blender_user_path
            col.label(text = "Backup From: " + str(self.active_blender_version), icon='COLORSET_03_VEC')   
            col.label(text = path)      
            self.draw_backup_age(col, path) 
            self.draw_backup_size(col, path)            
                   
            box = row.box() 
            col = box.column()  
            path =  os.path.join(self.backup_path, str(self.active_blender_version))
            col.label(text = "Backup To: " + str(self.active_blender_version), icon='COLORSET_04_VEC')   
            col.label(text = path)          
            self.draw_backup_age(col, path)    
            self.draw_backup_size(col, path)  
        elif self.advanced_mode:   
            if self.custom_version_toggle:    
                path = os.path.join(self.blender_user_path.strip(self.active_blender_version),  prefs().backup_versions)
                col.label(text = "Backup From: " + prefs().backup_versions, icon='COLORSET_03_VEC') 
                col.label(text = path)       
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)
                                
                box2 = row.box() 
                col = box2.column()  
                path = os.path.join(self.backup_path, str(self.custom_version))
                col.label(text = "Backup To: " + str(self.custom_version), icon='COLORSET_04_VEC')   
                col.label(text = path)     
                self.draw_backup_age(col, path)    
                self.draw_backup_size(col, path)                

            else:                
                path = os.path.join(self.blender_user_path.strip(self.active_blender_version),  prefs().backup_versions)
                col.label(text = "Backup From: " + prefs().backup_versions, icon='COLORSET_03_VEC') 
                col.label(text = path)       
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)
                
                box2 = row.box() 
                col = box2.column()  
                path =  os.path.join(self.backup_path, prefs().restore_versions)
                col.label(text = "Backup To: " + prefs().restore_versions, icon='COLORSET_04_VEC')   
                col.label(text = path)
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)

            # Advanced options
            col = box1.column()   
            col.scale_x = 0.8   
            col.prop(self, 'backup_versions', text='Backup From', expand = self.expand_version_selection) 
    
            col = box2.column()   
            if self.custom_version_toggle: 
                col.scale_x = 0.8
                col.prop(self, 'custom_version')
            else:      
                col.scale_x = 0.8 
                col.prop(self, 'restore_versions', text='Backup To', expand = self.expand_version_selection)
            
            self.draw_selection(box)

        col = row.column()   
        col.scale_x = 0.8
        col.operator("bm.run_backup_manager", text="Backup Selected", icon='COLORSET_03_VEC').button_input = 'BACKUP' 
        col.prop(self, 'dry_run')  
        col.prop(self, 'clean_path')  
        col.prop(self, 'advanced_mode') 
        if self.advanced_mode:
            col.prop(self, 'custom_version_toggle')  
            col.prop(self, 'expand_version_selection')   
            col.operator("bm.run_backup_manager", text="Batch Backup", icon='COLORSET_01_VEC').button_input = 'BATCH_BACKUP'  

         
    def draw_restore(self, box):        
        row  = box.row() 
        box1 = row.box() 
        col = box1.column()
        if not self.advanced_mode:            
            path = os.path.join(prefs().backup_path, str(self.active_blender_version))
            col.label(text = "Restore From: " + str(self.active_blender_version), icon='COLORSET_04_VEC')   
            col.label(text = path)                  
            self.draw_backup_age(col, path) 
            self.draw_backup_size(col, path)            
                   
            box = row.box() 
            col = box.column()  
            path =  self.blender_user_path
            col.label(text = "Restore To: " + str(self.active_blender_version), icon='COLORSET_03_VEC')   
            col.label(text = path)              
            self.draw_backup_age(col, path)    
            self.draw_backup_size(col, path)  

        else:        
            path = os.path.join(prefs().backup_path, prefs().restore_versions)
            col.label(text = "Restore From: " + prefs().restore_versions, icon='COLORSET_04_VEC')   
            col.label(text = path)    
            self.draw_backup_age(col, path)
            self.draw_backup_size(col, path)
            
            box2 = row.box() 
            col = box2.column()  
            path =  os.path.join(self.blender_user_path.strip(self.active_blender_version),  prefs().backup_versions)
            col.label(text = "Restore To: " + prefs().backup_versions, icon='COLORSET_03_VEC')   
            col.label(text = path)    
            self.draw_backup_age(col, path)
            self.draw_backup_size(col, path)

            # Advanced options
            col = box1.column() 
            col.scale_x = 0.8
            col.prop(self, 'restore_versions', text='Restore From', expand = self.expand_version_selection) 
            
            col = box2.column()  
            col.scale_x = 0.8                 
            col.prop(self, 'backup_versions', text='Restore To', expand = self.expand_version_selection)

            self.draw_selection(box)

        col = row.column()
        col.scale_x = 0.8
        col.operator("bm.run_backup_manager", text="Restore Selected", icon='COLORSET_04_VEC').button_input = 'RESTORE'
        col.prop(self, 'dry_run')      
        col.prop(self, 'clean_path')   
        col.prop(self, 'advanced_mode')  
        if self.advanced_mode:
            col.prop(self, 'expand_version_selection')  
 
    def draw_selection(self, box):     
        if  self.tabs == 'BACKUP':  
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
        
        elif  self.tabs == 'RESTORE':  
            box = box.box()
            row = box.row()            
            col = row.column() 
            col.prop(self, 'restore_addons') 
            col.prop(self, 'restore_presets')  
            col.prop(self, 'restore_datafile') 

            col = row.column()  
            col.prop(self, 'restore_startup_blend') 
            col.prop(self, 'restore_userpref_blend') 
            col.prop(self, 'restore_workspaces_blend') 
            
            col = row.column()  
            col.prop(self, 'restore_cache') 
            col.prop(self, 'restore_bookmarks') 
            col.prop(self, 'restore_recentfiles') 
        


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
