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
import socket
from bpy.types import AddonPreferences
from bpy.props import StringProperty, EnumProperty, BoolProperty


class BM_Preferences(AddonPreferences):
    bl_idname = __package__  
    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])  
    
    initial_version = f'{str(bpy.app.version[0])}.{str(bpy.app.version[1])}'
    backup_version_list = [(initial_version, initial_version, '', 0)]
    restore_version_list = [(initial_version, initial_version, '', 0)]
    
    def update_version_list(self, context):
        if self.debug:
            print("update_version_list: ", f'SEARCH_{self.tabs}')
        bpy.ops.bm.run_backup_manager(button_input=f'SEARCH_{self.tabs}')        
    
    # when user specified a custom temp path use that one as default, otherwise use the app default
    if bpy.context.preferences.filepaths.temporary_directory:        
        default_path = bpy.context.preferences.filepaths.temporary_directory 
    else: 
        default_path = bpy.app.tempdir
    
    
    def update_system_id(self, context):
        if self.use_system_id:
            default_path = os.path.join(self.default_path , '!backupmanager/', self.system_id)
        else:            
            default_path = os.path.join(self.default_path , '!backupmanager/')            
        
        if self.debug:
            print("system id path: ", default_path)  

    print("Backup Manager Default path: ", default_path)

    backup_path: StringProperty(name="Backup Path", description="Backup Location", subtype='DIR_PATH', default=os.path.join(default_path , '!backupmanager/'), update=update_version_list)
    blender_user_path: bpy.props.StringProperty(default=bpy.utils.resource_path(type='USER'))
    
    preferences_tabs = [("BACKUP", "Backup Options", ""),
                ("RESTORE", "Restore Options", "")]
    
    tabs: EnumProperty(name="Tabs", 
                       items=preferences_tabs, 
                       default="BACKUP",
                       update=update_version_list)   
    
    config_path: StringProperty(name="config_path",
                                description="config_path", 
                                subtype='DIR_PATH', 
                                default=bpy.utils.user_resource('CONFIG')) #Resource type in [‘DATAFILES’, ‘CONFIG’, ‘SCRIPTS’, ‘AUTOSAVE’].
    
    system_id: StringProperty(name="ID", 
                              description="Current Computer Name", 
                              subtype='NONE',
                              default=str(socket.getfqdn()))  
    use_system_id: BoolProperty(name="Shared configs", 
                                description="use_system_id", 
                                update=update_system_id,
                                default=True)   # default = False 
    
    debug: BoolProperty(name="debug", 
                        description="debug", 
                        update=update_system_id, 
                        default=False) # default = False  
    
    active_blender_version: StringProperty(name="Current Blender Version", 
                                           description="Current Blender Version", 
                                           subtype='NONE', 
                                           default=this_version)
    dry_run: BoolProperty(name="Dry Run",
                          description="Run code without modifying any files on the drive."
                          "NOTE: this will not create or restore any backups!", 
                          default=True)     # default = False 
    
    advanced_mode: BoolProperty(name="Advanced", 
                                description="Advanced backup and restore options", 
                                update=update_version_list,
                                default=True)  # default = True
    
    expand_version_selection: BoolProperty(name="Expand Versions", 
                                           description="Switch between dropdown and expanded version layout",
                                           update=update_version_list, 
                                           default=True)  # default = True
    
    # BACKUP  
    custom_version_toggle: BoolProperty(name="Custom Version", description="Set your custom backup version", default=False, update=update_version_list)  # default = False  
    custom_version: StringProperty(name="Custom Version", description="Custom version folder", subtype='NONE', default='custom')
    clean_path: BoolProperty(name="Clean Backup", description="delete before backup", default=False) # default = False 
    
    def populate_backuplist(self, context):
        return self.backup_version_list      
      
    backup_versions: EnumProperty(items=populate_backuplist,
                                  name="Backup",  
                                  description="Choose the version to backup", 
                                  update=None)
    
    backup_cache: BoolProperty(name="cache", description="backup_cache", default=False)   # default = False      
    backup_bookmarks: BoolProperty(name="bookmarks", description="backup_bookmarks", default=True)   # default = True   
    backup_recentfiles: BoolProperty(name="recentfiles", description="backup_recentfiles", default=True)  # default = True
    backup_startup_blend: BoolProperty( name="startup.blend", description="backup_startup_blend", default=True)  # default = True   
    backup_userpref_blend: BoolProperty(name="userpref.blend", description="backup_userpref_blend", default=True)  # default = True  
    backup_workspaces_blend: BoolProperty(name="workspaces.blend", description="backup_workspaces_blend", default=True)  # default = True 
    backup_datafile: BoolProperty( name="datafile", description="backup_datafile", default=True)  # default = True       
    backup_addons: BoolProperty(name="addons", description="backup_addons", default=True)   # default = True   
    backup_presets: BoolProperty(name="presets", description="backup_presets", default=True) # default = True


    # RESTORE      
    def populate_restorelist(self, context):
        return self.restore_version_list  
          
    restore_versions: EnumProperty(items=populate_restorelist, 
                                   name="Restore", 
                                   description="Choose the version to Resotre", 
                                   update=None)
    
    restore_cache: BoolProperty(name="cache", description="restore_cache", default=False)  # default = False  
    restore_bookmarks: BoolProperty(name="bookmarks", description="restore_bookmarks", default=True)    # default = True
    restore_recentfiles: BoolProperty(name="recentfiles", description="restore_recentfiles", default=True)  # default = True
    restore_startup_blend: BoolProperty(name="startup.blend", description="restore_startup_blend",  default=True)   # default = True  
    restore_userpref_blend: BoolProperty(name="userpref.blend", description="restore_userpref_blend", default=True)  # default = True  
    restore_workspaces_blend: BoolProperty(name="workspaces.blend", description="restore_workspaces_blend", default=True)   # default = True
    restore_datafile: BoolProperty(name="datafile", description="restore_datafile", default=True)       # default = True  
    restore_addons: BoolProperty(name="addons", description="restore_addons", default=True)    # default = True  
    restore_presets: BoolProperty(name="presets", description="restore_presets", default=True)   # default = True  

    ignore_files: StringProperty(name="Ignore Files",
                                description="Ignore files from being backed up or restored", 
                                subtype='FILE_NAME', 
                                default='desktop.ini')

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
        
        col.prop(self, 'ignore_files')
        #col.prop(self, 'use_system_id')
        #col.prop(self, 'debug')
        
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
                path = os.path.join(self.blender_user_path.strip(self.active_blender_version),  self.backup_versions)
                col.label(text = "Backup From: " + self.backup_versions, icon='COLORSET_03_VEC') 
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
                path = os.path.join(self.blender_user_path.strip(self.active_blender_version),  self.backup_versions)
                col.label(text = "Backup From: " + self.backup_versions, icon='COLORSET_03_VEC') 
                col.label(text = path)       
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)
                
                box2 = row.box() 
                col = box2.column()  
                path =  os.path.join(self.backup_path, self.restore_versions)
                col.label(text = "Backup To: " + self.restore_versions, icon='COLORSET_04_VEC')   
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
        if self.advanced_mode:
            col.operator("bm.run_backup_manager", text="Backup All", icon='COLORSET_03_VEC').button_input = 'BATCH_BACKUP' 
        col.separator(factor=1.0)
        col.prop(self, 'dry_run')  
        col.prop(self, 'clean_path')  
        col.prop(self, 'advanced_mode') 
        if self.advanced_mode:
            col.prop(self, 'custom_version_toggle')  
            col.prop(self, 'expand_version_selection')    
            col.separator(factor=1.0)
            col.operator("bm.run_backup_manager", text="Delete Backup", icon='COLORSET_01_VEC').button_input = 'DELETE_BACKUP' 

         
    def draw_restore(self, box):        
        row  = box.row() 
        box1 = row.box() 
        col = box1.column()
        if not self.advanced_mode:            
            path = os.path.join(self.backup_path, str(self.active_blender_version))
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
            path = os.path.join(self.backup_path, self.restore_versions)
            col.label(text = "Restore From: " + self.restore_versions, icon='COLORSET_04_VEC')   
            col.label(text = path)    
            self.draw_backup_age(col, path)
            self.draw_backup_size(col, path)
            
            box2 = row.box() 
            col = box2.column()  
            path =  os.path.join(self.blender_user_path.strip(self.active_blender_version),  self.backup_versions)
            col.label(text = "Restore To: " + self.backup_versions, icon='COLORSET_03_VEC')   
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
        if self.advanced_mode:
            col.operator("bm.run_backup_manager", text="Restore All", icon='COLORSET_04_VEC').button_input = 'BATCH_RESTORE'
        col.separator(factor=1.0)
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
        
