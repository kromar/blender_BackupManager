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
from bpy.types import Operator
from bpy.props import StringProperty
from . import preferences


def prefs():
    return bpy.context.preferences.addons[__package__].preferences


def find_versions(filepath):
    version_list = []
    
    try:          
        for file in os.listdir(os.path.dirname(filepath)):
            path = os.path.join(filepath, file)
            if os.path.isdir(path):      
                version_list.append((file, file, ''))

    except Exception:
        print("filepath invalid: ", filepath)
    
    if prefs().debug:
        print("\nVersion List: ", version_list)

    return version_list


    
class OT_BackupManager(Operator):
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    button_input: StringProperty()
    ignore_backup = []
    ignore_restore = []


    def max_list_value(self, list):
        i = numpy.argmax(list)
        v = list[i]
        return (i, v)
    
    
    def create_ignore_pattern(self):
        self.ignore_backup.clear()
        self.ignore_restore.clear()

        
        import re     
        list = [x for x in re.split(',|\s+', prefs().ignore_files) if x!='']        
        for item in list:
            self.ignore_backup.append(item)
            self.ignore_restore.append(item)

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
            
        if not prefs().backup_extensions:
            self.ignore_backup.append('extensions')
        if not prefs().restore_extensions:
            self.ignore_restore.append('extensions')

        if not prefs().backup_presets:
            self.ignore_backup.append('presets')
        if not prefs().restore_presets:
            self.ignore_restore.append('presets')
    

    def recursive_overwrite(self, src, dest, ignore=None):
        if os.path.isdir(src):
            if not os.path.isdir(dest):
                os.makedirs(dest)
            files = os.listdir(src)
            ignored = ignore(src, files) if ignore is not None else set()
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
                os.system(f'rmdir /S /Q "{target_path}"')
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
        
        backup_version_list = preferences.BM_Preferences.backup_version_list
        restore_version_list = preferences.BM_Preferences.restore_version_list  

        if prefs().debug:
            print("\n\nbutton_input: ", self.button_input)                    
        
        if prefs().backup_path:     

            if prefs().use_system_id:
                system_id_path = os.path.join(prefs().backup_path, prefs().system_id, prefs().backup_versions).replace("\\", "/")  
            else:            
                system_id_path = os.path.join(prefs().backup_path, prefs().backup_versions).replace("\\", "/") 

            shared_path = os.path.join(prefs().backup_path, 'shared', prefs().backup_versions).replace("\\", "/") 

            if prefs().debug: 
                print("system_id_path: ", system_id_path)
                print("shared_path: ", shared_path)


            if self.button_input == 'BACKUP':         
                if not prefs().advanced_mode:            
                    source_path = os.path.join(prefs().blender_user_path).replace("\\", "/")
                    target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")                    
                else:    
                    source_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  prefs().backup_versions).replace("\\", "/")                                             
                    if prefs().custom_version_toggle:
                        target_path = os.path.join(prefs().backup_path, str(prefs().custom_version)).replace("\\", "/")
                    else: 
                        target_path = os.path.join(prefs().backup_path, prefs().restore_versions).replace("\\", "/")
                self.run_backup(source_path, target_path)  
            
            elif self.button_input == 'BATCH_BACKUP':
                for version in backup_version_list:
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  version[0]).replace("\\", "/")
                    target_path = os.path.join(prefs().backup_path, version[0]).replace("\\", "/")
                    self.run_backup(source_path, target_path)   
             
            elif self.button_input == 'DELETE_BACKUP':
                if not prefs().advanced_mode:            
                    target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")                    
                else:                                                 
                    if prefs().custom_version_toggle:
                        target_path = os.path.join(prefs().backup_path, str(prefs().custom_version)).replace("\\", "/")
                    else:                
                        target_path = os.path.join(prefs().backup_path, prefs().restore_versions).replace("\\", "/")

                if os.path.exists(target_path): # TODO: does this need to go into clean mode?
                    os.system('rmdir /S /Q "{}"'.format(target_path))
                    print("\nDeleted Backup: ", target_path)

            elif self.button_input == 'RESTORE':
                if not prefs().advanced_mode:            
                    source_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")
                    target_path = os.path.join(prefs().blender_user_path).replace("\\", "/")
                else:             
                    source_path = os.path.join(prefs().backup_path, prefs().restore_versions).replace("\\", "/")
                    target_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  prefs().backup_versions).replace("\\", "/")
                self.run_backup(source_path, target_path) 
                
            elif self.button_input == 'BATCH_RESTORE':
                for version in restore_version_list:
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(prefs().backup_path, version[0]).replace("\\", "/")
                    target_path = os.path.join(prefs().blender_user_path.strip(prefs().active_blender_version),  version[0]).replace("\\", "/")                    
                    self.run_backup(source_path, target_path) 
           

            elif self.button_input == 'SEARCH_BACKUP':
                backup_version_list.clear() 
                backup_version_list = find_versions(bpy.utils.resource_path(type='USER').strip(prefs().active_blender_version))
                backup_version_list.sort(reverse=True)

                restore_version_list.clear()    
                restore_version_list = set(find_versions(prefs().backup_path) + backup_version_list)
                restore_version_list = list(dict.fromkeys(restore_version_list))
                restore_version_list.sort(reverse=True)   
                
                # update version lists
                preferences.BM_Preferences.restore_version_list = restore_version_list
                preferences.BM_Preferences.backup_version_list = backup_version_list
            

            elif self.button_input == 'SEARCH_RESTORE': 
                restore_version_list.clear()        
                restore_version_list = find_versions(prefs().backup_path)
                restore_version_list.sort(reverse=True) 

                backup_version_list.clear() 
                backup_version_list = set(find_versions(bpy.utils.resource_path(type='USER').strip(prefs().active_blender_version)) + restore_version_list)
                if prefs().debug:
                    print("list 1: ", backup_version_list)
                backup_version_list = list(dict.fromkeys(backup_version_list))
                if prefs().debug:
                    print("list 2: ", backup_version_list)
                
                # remove custom items from list (assuming non floats are invalid)
                for version in backup_version_list: 
                    try:
                        float(version[0])
                    except:
                        backup_version_list.remove(version)
                backup_version_list.sort(reverse=True)  
                
                # update version lists
                preferences.BM_Preferences.restore_version_list = restore_version_list
                preferences.BM_Preferences.backup_version_list = backup_version_list            

        else:
            self.ShowReport(["Specify a Backup Path"] , "Backup Path missing", 'COLORSET_04_VEC')
        return {'FINISHED'}
    


