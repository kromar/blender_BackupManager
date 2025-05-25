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
import re # Moved from create_ignore_pattern
from datetime import datetime # Added for debug timestamps
from bpy.types import Operator
from bpy.props import StringProperty
from . import preferences


def prefs():
    return bpy.context.preferences.addons[__package__].preferences


def find_versions(filepath):
    version_list = []
    _start_time_fv = None
    if prefs().debug:
        _start_time_fv = datetime.now()
        print(f"DEBUG: find_versions START for path: {filepath}")

    if not filepath or not os.path.isdir(filepath):
        if prefs().debug:
            print(f"DEBUG: find_versions: filepath invalid or not a directory: {filepath}")
        return version_list

    try:
        _listdir_start_time_fv = None
        if prefs().debug:
            _listdir_start_time_fv = datetime.now()
            print(f"DEBUG: find_versions CALLING os.listdir for path: {filepath}")
        for file_or_dir_name in os.listdir(filepath):
            path = os.path.join(filepath, file_or_dir_name)
            if os.path.isdir(path):      
                version_list.append((file_or_dir_name, file_or_dir_name, ''))
        if prefs().debug:
            _listdir_end_time_fv = datetime.now()
            print(f"DEBUG: (took: {(_listdir_end_time_fv - _listdir_start_time_fv).total_seconds():.6f}s) find_versions FINISHED os.listdir for path: {filepath}")
    except OSError as e: # Catch specific OS errors like PermissionError
        if prefs().debug:
            print(f"DEBUG: find_versions: Error accessing filepath {filepath}: {e}")
    
    if prefs().debug and _start_time_fv:
        print("\nVersion List: ", version_list)
        _end_time_fv = datetime.now()
        print(f"DEBUG: (took: {(_end_time_fv - _start_time_fv).total_seconds():.6f}s) find_versions END for path: {filepath}, found {len(version_list)} versions")

    return version_list


    
class OT_BackupManager(Operator):
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    button_input: StringProperty()
    ignore_backup = []
    ignore_restore = []

    # This method seems unused. If so, consider removing it and the numpy import.
    # For now, assuming it might be used elsewhere or intended for future use.
    # If removing, also remove `import numpy`
    """
    def max_list_value(self, list):
        import numpy # Keep numpy import local if this method is kept and rarely used
        i = numpy.argmax(list)
        v = list[i]
        return (i, v)
    """
    
    def create_ignore_pattern(self):
        self.ignore_backup.clear()
        self.ignore_restore.clear()
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

        if prefs().clean_path and os.path.exists(target_path):
            if prefs().debug:
                print(f"Attempting to clean path: {target_path}")
            try:
                if not prefs().dry_run:
                    shutil.rmtree(target_path)
                print(f"\nCleaned path: {target_path}")
            except OSError as e:
                print(f"\nFailed to clean path {target_path}: {e}")
                self.report({'WARNING'}, f"Failed to clean {target_path}: {e}")

        # backup
        self.create_ignore_pattern()
        #self.transfer_files(source_path, target_path)   
        print("source: ",  source_path)
        print("target: ", target_path)

        if os.path.isdir(source_path): 
            try:
                if not prefs().dry_run:
                    self.recursive_overwrite(source_path, target_path,  ignore = shutil.ignore_patterns(*self.ignore_backup)) 
                else:
                    print("Dry run: No files modified.")
            except Exception as e: # Generic catch for copy errors
                self.report({'ERROR'}, f"Backup/Restore failed: {e}")
                return {'CANCELLED'}


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
        
        pref_backup_versions = preferences.BM_Preferences.backup_version_list
        pref_restore_versions = preferences.BM_Preferences.restore_version_list

        if prefs().debug:
            print("\n\nbutton_input: ", self.button_input)                    
        
        if prefs().backup_path:     

            if prefs().use_system_id:
                # This path seems unused later, consider if it's needed or how it integrates.
                # system_id_path = os.path.join(prefs().backup_path, prefs().system_id, prefs().backup_versions)
                pass
            else:            
                # system_id_path = os.path.join(prefs().backup_path, prefs().backup_versions)
                pass

            # shared_path = os.path.join(prefs().backup_path, 'shared', prefs().backup_versions)

            if prefs().debug: 
                # print("system_id_path: ", system_id_path) # If re-enabled
                # print("shared_path: ", shared_path) # If re-enabled
                pass

            if self.button_input == 'BACKUP':         
                if not prefs().advanced_mode:            
                    source_path = prefs().blender_user_path
                    target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version))
                else:    
                    source_path = os.path.join(os.path.dirname(prefs().blender_user_path),  prefs().backup_versions)
                    if prefs().custom_version_toggle:
                        target_path = os.path.join(prefs().backup_path, str(prefs().custom_version))
                    else: 
                        target_path = os.path.join(prefs().backup_path, prefs().restore_versions)
                self.run_backup(source_path, target_path)  
            
            elif self.button_input == 'BATCH_BACKUP':
                for version in pref_backup_versions: # Iterate over the list from preferences
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(os.path.dirname(prefs().blender_user_path),  version[0])
                    target_path = os.path.join(prefs().backup_path, version[0])
                    self.run_backup(source_path, target_path)   
             
            elif self.button_input == 'DELETE_BACKUP':
                if not prefs().advanced_mode:            
                    target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version)).replace("\\", "/")                    
                else:                                                 
                    if prefs().custom_version_toggle:
                        target_path = os.path.join(prefs().backup_path, str(prefs().custom_version))
                    else:                
                        target_path = os.path.join(prefs().backup_path, prefs().restore_versions)

                if os.path.exists(target_path):
                    try:
                        if not prefs().dry_run:
                            shutil.rmtree(target_path)
                        print(f"\nDeleted Backup: {target_path}")
                        self.report({'INFO'}, f"Deleted: {target_path}")
                    except OSError as e:
                        print(f"\nFailed to delete {target_path}: {e}")
                        self.report({'WARNING'}, f"Failed to delete {target_path}: {e}")
                else:
                    print(f"\nBackup to delete not found: {target_path}")
                    self.report({'INFO'}, f"Not found, nothing to delete: {target_path}")

            elif self.button_input == 'RESTORE':
                if not prefs().advanced_mode:            
                    source_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version))
                    target_path = prefs().blender_user_path
                else:             
                    source_path = os.path.join(prefs().backup_path, prefs().restore_versions)
                    target_path = os.path.join(os.path.dirname(prefs().blender_user_path),  prefs().backup_versions)
                self.run_backup(source_path, target_path) 
                
            elif self.button_input == 'BATCH_RESTORE':
                for version in pref_restore_versions: # Iterate over the list from preferences
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(prefs().backup_path, version[0])
                    target_path = os.path.join(os.path.dirname(prefs().blender_user_path),  version[0])
                    self.run_backup(source_path, target_path) 
           

            elif self.button_input == 'SEARCH_BACKUP':
                _search_start_sb = None
                if prefs().debug:
                    _search_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP START")
                # Path to the directory containing Blender version folders (e.g., .../Blender/3.6, .../Blender/4.0)
                blender_versions_parent_dir = os.path.dirname(bpy.utils.resource_path(type='USER'))

                pref_backup_versions.clear()
                _fv1_start_sb = None
                if prefs().debug:
                    _fv1_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP calling find_versions for blender_versions_parent_dir: {blender_versions_parent_dir}")
                found_backup_versions = find_versions(blender_versions_parent_dir)
                if prefs().debug:
                    _fv1_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_fv1_end_sb - _fv1_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP find_versions for blender_versions_parent_dir DONE")
                pref_backup_versions.extend(found_backup_versions)
                pref_backup_versions.sort(reverse=True)

                pref_restore_versions.clear()
                # Combine found versions from backup path and current Blender versions, then make unique
                _fv2_start_sb = None
                if prefs().debug:
                    _fv2_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP calling find_versions for backup_path: {prefs().backup_path}")
                combined_restore_versions = find_versions(prefs().backup_path) + pref_backup_versions
                if prefs().debug:
                    _fv2_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_fv2_end_sb - _fv2_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP find_versions for backup_path DONE")
                # Use dict.fromkeys to preserve order of first appearance if that's desired before sorting
                pref_restore_versions.extend(list(dict.fromkeys(combined_restore_versions)))
                pref_restore_versions.sort(reverse=True)
                if prefs().debug and _search_start_sb:
                    _search_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_search_end_sb - _search_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP END")

            elif self.button_input == 'SEARCH_RESTORE': 
                _search_start_sr = None
                if prefs().debug:
                    _search_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE START")
                blender_versions_parent_dir = os.path.dirname(bpy.utils.resource_path(type='USER'))

                pref_restore_versions.clear()
                _fv1_start_sr = None
                if prefs().debug:
                    _fv1_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE calling find_versions for backup_path: {prefs().backup_path}")
                found_restore_versions = find_versions(prefs().backup_path)
                if prefs().debug:
                    _fv1_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_fv1_end_sr - _fv1_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE find_versions for backup_path DONE")
                pref_restore_versions.extend(found_restore_versions)
                pref_restore_versions.sort(reverse=True) 

                pref_backup_versions.clear()
                _fv2_start_sr = None
                if prefs().debug:
                    _fv2_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE calling find_versions for blender_versions_parent_dir: {blender_versions_parent_dir}")
                combined_backup_versions = find_versions(blender_versions_parent_dir) + pref_restore_versions
                if prefs().debug:
                    _fv2_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_fv2_end_sr - _fv2_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE find_versions for blender_versions_parent_dir DONE")

                if prefs().debug:
                    print("Combined backup versions before filtering: ", combined_backup_versions)
                
                # Filter and sort backup versions
                unique_backup_versions = list(dict.fromkeys(combined_backup_versions))
                valid_backup_versions = []
                for version_tuple in unique_backup_versions:
                    try:
                        float(version_tuple[0]) # Check if version name can be a float
                        valid_backup_versions.append(version_tuple)
                    except ValueError:
                        if prefs().debug:
                            print(f"Filtered out non-float-like version from backup_versions: {version_tuple[0]}")
                
                pref_backup_versions.extend(valid_backup_versions)
                if prefs().debug:
                    print("Final backup_versions list: ", pref_backup_versions)
                pref_backup_versions.sort(reverse=True)
                if prefs().debug and _search_start_sr:
                    _search_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_search_end_sr - _search_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE END")

        else:
            self.ShowReport(["Specify a Backup Path"] , "Backup Path missing", 'COLORSET_04_VEC')
        return {'FINISHED'}
    
