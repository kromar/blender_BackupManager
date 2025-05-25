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
import fnmatch # For pattern matching in ignore list
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
        # print("\nVersion List: ", version_list)
        _end_time_fv = datetime.now()
        # Consider summarizing 'version_list' if it can be very long.
        # For now, printing the full list for detailed debugging.
        print(f"DEBUG: (took: {(_end_time_fv - _start_time_fv).total_seconds():.6f}s) find_versions END for path: '{filepath}', found {len(version_list)} versions. List: {version_list}")

    return version_list


class OT_AbortOperation(Operator):
    """Operator to signal cancellation of the ongoing backup/restore operation."""
    bl_idname = "bm.abort_operation"
    bl_label = "Abort Backup/Restore"
    bl_description = "Requests cancellation of the current operation"

    def execute(self, context):
        prefs().abort_operation_requested = True
        # The modal operator will pick this up and handle the actual cancellation.
        if prefs().debug:
            print("DEBUG: OT_AbortOperation executed, abort_operation_requested set to True.")
        return {'FINISHED'}
    
    
class OT_BackupManager(Operator):
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    
    button_input: StringProperty()
    
    # --- Modal operator state variables ---
    _timer = None
    files_to_process: list = []
    total_files: int = 0
    processed_files_count: int = 0
    current_source_path: str = ""
    current_target_path: str = ""
    current_operation_type: str = "" # 'BACKUP' or 'RESTORE'

    ignore_backup = []
    ignore_restore = []
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
    
    def ShowReport(self, message = [], title = "Message Box", icon = 'INFO'):
        def draw(self, context):
            for i in message:
                self.layout.label(text=i)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

    
    def _prepare_file_list(self):
        """Scans source_path and populates self.files_to_process and self.total_files."""
        self.files_to_process.clear()
        self.total_files = 0
        self.processed_files_count = 0

        if not self.current_source_path or not os.path.isdir(self.current_source_path):
            self.report({'WARNING'}, f"Source path does not exist or is not a directory: {self.current_source_path}")
            return False

        self.create_ignore_pattern()
        current_ignore_list = self.ignore_backup if self.current_operation_type == 'BACKUP' else self.ignore_restore

        if prefs().debug:
            print(f"Preparing file list for {self.current_operation_type}")
            print(f"Source: {self.current_source_path}")
            print(f"Target: {self.current_target_path}")
            print(f"Ignore list: {current_ignore_list}")

        for dirpath, dirnames, filenames in os.walk(self.current_source_path):
            # Prune dirnames based on ignore list
            dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in current_ignore_list)]

            for filename in filenames:
                if any(fnmatch.fnmatch(filename, pat) for pat in current_ignore_list):
                    continue
                
                src_file = os.path.join(dirpath, filename)
                relative_dir = os.path.relpath(dirpath, self.current_source_path)
                # On Windows, relpath might return '.' for the top level, handle this.
                if relative_dir == '.':
                    dest_file = os.path.join(self.current_target_path, filename)
                else:
                    dest_file = os.path.join(self.current_target_path, relative_dir, filename)

                # Basic check to prevent copying a directory into itself if paths are misconfigured
                # This is a simplified check; robust cycle detection is more complex.
                if os.path.commonpath([src_file, dest_file]) == os.path.normpath(src_file) and \
                   os.path.commonpath([src_file, dest_file]) == os.path.normpath(dest_file):
                    if prefs().debug: print(f"Skipping copy, source and destination might be problematic: {src_file} -> {dest_file}")
                    continue

                self.files_to_process.append((src_file, dest_file))
        
        self.total_files = len(self.files_to_process)
        if prefs().debug:
            print(f"Total files to process: {self.total_files}")
        return True

    def modal(self, context, event):
        # Capture the state of the abort request flag at the beginning of this modal event
        was_aborted_by_ui_button = prefs().abort_operation_requested

        # Check for abort request first or ESC key
        if was_aborted_by_ui_button or event.type == 'ESC' or \
           (not self.files_to_process and self.processed_files_count == self.total_files):
            prefs().show_operation_progress = False
            
            if self._timer: # Ensure timer is removed
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

            # Reset the flag now that its state (was_aborted_by_ui_button) has been used for the decision to exit the modal.
            if was_aborted_by_ui_button:
                prefs().abort_operation_requested = False

            if event.type == 'ESC' or was_aborted_by_ui_button: # Use the captured state
                cancel_message = f"{self.current_operation_type} cancelled by user."
                self.report({'WARNING'}, cancel_message)
                self.ShowReport(message=[cancel_message], title="Operation Cancelled", icon='WARNING')
                prefs().operation_progress_message = f"{self.current_operation_type} cancelled." # For the brief moment before UI hides
                return {'CANCELLED'}
            else: # Operation completed successfully
                completion_status = "Dry run complete" if prefs().dry_run else "Complete"
                
                report_message = (
                    f"{self.current_operation_type} {completion_status.lower()}.\n"
                    f"{self.processed_files_count}/{self.total_files} files processed.\n"
                    f"Source: {self.current_source_path}\n"
                    f"Target: {self.current_target_path}"
                )
                if prefs().dry_run and self.total_files > 0: 
                    report_message += "\n(Dry Run - No files were actually copied/deleted)"

                report_icon = 'INFO' # Default
                if self.current_operation_type == 'BACKUP':
                    report_icon = 'COLORSET_03_VEC'
                elif self.current_operation_type == 'RESTORE':
                    report_icon = 'COLORSET_04_VEC'

                self.report({'INFO'}, report_message)
                self.ShowReport(message=report_message.split('\n'), title=f"{self.current_operation_type} Report", icon=report_icon)
                prefs().operation_progress_message = f"{self.current_operation_type} {completion_status.lower()}." # For the brief moment before UI hides
            return {'FINISHED'}

        if event.type == 'TIMER':
            if not self.files_to_process: # Should be caught above, but as a safeguard
                # context.window_manager.progress_end() # Replaced
                prefs().show_operation_progress = False
                if self._timer:
                    context.window_manager.event_timer_remove(self._timer)
                    self._timer = None
                return {'FINISHED'}

            # Process a small batch of files per timer event to keep UI responsive
            # For simplicity, let's process one file per tick. Can be increased.
            src_file, dest_file = self.files_to_process.pop(0)

            if not prefs().dry_run:
                try:
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_file, dest_file) # copy2 preserves metadata
                except Exception as e:
                    print(f"Error copying {src_file} to {dest_file}: {e}")
                    # Optionally report this error or collect errors to show at the end
            
            self.processed_files_count += 1
            progress_value = (self.processed_files_count / self.total_files) * 100 if self.total_files > 0 else 100
            # context.window_manager.progress_update(progress_value) # Replaced
            prefs().operation_progress_value = progress_value
            prefs().operation_progress_message = f"{self.current_operation_type}: {self.processed_files_count}/{self.total_files} files..."

            # Force redraw of the preferences area to update the progress bar
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'PREFERENCES':
                        area.tag_redraw()
                        break # Found and tagged, no need to check other areas in this window
        return {'PASS_THROUGH'} # Allow other events to be processed


    def execute(self, context): 
        pref_backup_versions = preferences.BM_Preferences.backup_version_list
        pref_restore_versions = preferences.BM_Preferences.restore_version_list

        if prefs().debug:
            print("\n\nbutton_input: ", self.button_input)                    
        
        if prefs().backup_path:
            self.current_operation_type = "" # Reset

            if self.button_input in {'BACKUP', 'RESTORE'}:
                self.current_operation_type = self.button_input
                if not prefs().advanced_mode:            
                    if self.button_input == 'BACKUP':
                        self.current_source_path = prefs().blender_user_path
                        self.current_target_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version))
                    else: # RESTORE
                        self.current_source_path = os.path.join(prefs().backup_path, str(prefs().active_blender_version))
                        self.current_target_path = prefs().blender_user_path
                else:    
                    if self.button_input == 'BACKUP':
                        self.current_source_path = os.path.join(os.path.dirname(prefs().blender_user_path),  prefs().backup_versions)
                        if prefs().custom_version_toggle:
                            self.current_target_path = os.path.join(prefs().backup_path, str(prefs().custom_version))
                        else: 
                            self.current_target_path = os.path.join(prefs().backup_path, prefs().restore_versions) # Should be backup_versions for target?
                            # Corrected: If not custom, target for backup should be based on source version name
                            self.current_target_path = os.path.join(prefs().backup_path, prefs().backup_versions)

                    else: # RESTORE
                        self.current_source_path = os.path.join(prefs().backup_path, prefs().restore_versions)
                        self.current_target_path = os.path.join(os.path.dirname(prefs().blender_user_path),  prefs().backup_versions)

                if prefs().clean_path and os.path.exists(self.current_target_path) and self.button_input == 'BACKUP': # Clean only for backup
                    if prefs().debug: print(f"Attempting to clean path: {self.current_target_path}")
                    try:
                        if not prefs().dry_run: shutil.rmtree(self.current_target_path)
                        print(f"Cleaned path: {self.current_target_path}")
                    except OSError as e:
                        print(f"Failed to clean path {self.current_target_path}: {e}")
                        self.report({'WARNING'}, f"Failed to clean {self.current_target_path}: {e}")

                if not self._prepare_file_list(): # Populates self.files_to_process
                    return {'CANCELLED'}
                
                if self.total_files == 0 and not prefs().dry_run:
                    report_message = f"No files to {self.current_operation_type.lower()}"
                    if self.current_source_path:
                         report_message += f" from {self.current_source_path}"
                    if prefs().dry_run:
                        report_message += " (Dry Run)."
                    else:
                        report_message += "."
                    self.report({'INFO'}, report_message)
                    self.ShowReport(message=report_message.split('\n'), title="Operation Status", icon='INFO')
                    # No need to set prefs().show_operation_progress as modal won't start
                    return {'FINISHED'}

                prefs().show_operation_progress = True
                prefs().operation_progress_value = 0
                prefs().operation_progress_message = f"Starting {self.current_operation_type}..."
                self._timer = context.window_manager.event_timer_add(0.01, window=context.window) # Short interval for responsiveness
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            
            elif self.button_input == 'BATCH_BACKUP': # TODO: Adapt BATCH to use modal logic sequentially
                for version in pref_backup_versions: # Iterate over the list from preferences
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(os.path.dirname(prefs().blender_user_path),  version[0])
                    target_path = os.path.join(prefs().backup_path, version[0])
                    # This needs to be adapted to call the modal setup for each.
                    # For now, it will run the old blocking way if run_backup was a separate method.
                    # With run_backup logic integrated, this needs a loop that re-invokes the operator
                    # or a more complex internal loop that re-initializes the modal state.
                    # For simplicity, this will be blocking for now or needs a separate operator.
                    self.report({'INFO'}, f"Batch Backup for {version[0]} - (Modal progress for batch not yet fully implemented, runs blocking)")
                    self._execute_single_backup_restore_blocking(source_path, target_path, 'BACKUP')
             
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
                        
                        action_verb = "Would delete" if prefs().dry_run else "Deleted"
                        report_msg_line1 = f"{action_verb} backup:"
                        report_msg_line2 = target_path
                        self.report({'INFO'}, f"{report_msg_line1} {report_msg_line2}")
                        self.ShowReport(message=[report_msg_line1, report_msg_line2], title="Delete Backup Report", icon='COLORSET_01_VEC')
                        if prefs().debug or prefs().dry_run:
                             print(f"\n{action_verb} Backup: {target_path}")

                    except OSError as e:
                        action_verb = "Failed to (dry run) delete" if prefs().dry_run else "Failed to delete"
                        error_msg_line1 = f"{action_verb} {target_path}:"
                        error_msg_line2 = str(e)
                        self.report({'WARNING'}, f"{error_msg_line1} {error_msg_line2}")
                        self.ShowReport(message=[error_msg_line1, error_msg_line2], title="Delete Backup Error", icon='WARNING')
                        if prefs().debug: # Keep print for debug
                            print(f"\n{action_verb} {target_path}: {e}")
                else:
                    not_found_msg = f"Not found, nothing to delete: {target_path}"
                    self.report({'INFO'}, not_found_msg)
                    self.ShowReport(message=[f"Not found, nothing to delete:", target_path], title="Delete Backup Report", icon='INFO')
                    if prefs().debug: # Keep print for debug
                        print(f"\nBackup to delete not found: {target_path}")

            elif self.button_input == 'BATCH_RESTORE': # TODO: Adapt BATCH
                for version in pref_restore_versions: # Iterate over the list from preferences
                    if prefs().debug:
                        print(version[0])
                    source_path = os.path.join(prefs().backup_path, version[0])
                    target_path = os.path.join(os.path.dirname(prefs().blender_user_path),  version[0])
                    self.report({'INFO'}, f"Batch Restore for {version[0]} - (Modal progress for batch not yet fully implemented, runs blocking)")
                    self._execute_single_backup_restore_blocking(source_path, target_path, 'RESTORE')
           

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
            self.ShowReport(["Specify a Backup Path"] , "Backup Path missing", 'ERROR')
        return {'FINISHED'}

    def _execute_single_backup_restore_blocking(self, source_path, target_path, operation_type):
        """ Helper for BATCH operations to run the old blocking way for now. """
        if prefs().debug:
            print(f"Executing blocking {operation_type}: {source_path} -> {target_path}")

        self.current_source_path = source_path
        self.current_target_path = target_path
        self.current_operation_type = operation_type

        if operation_type == 'BACKUP' and prefs().clean_path and os.path.exists(target_path):
            if not prefs().dry_run: shutil.rmtree(target_path)

        self.create_ignore_pattern()
        current_ignore_list = self.ignore_backup if operation_type == 'BACKUP' else self.ignore_restore

        if os.path.isdir(source_path):
            try:
                if not prefs().dry_run:
                    # Simplified recursive copy for the blocking version
                    for dirpath, dirnames, filenames in os.walk(source_path):
                        dirnames[:] = [d for d in dirnames if not any(fnmatch.fnmatch(d, pat) for pat in current_ignore_list)]
                        for filename in filenames:
                            if any(fnmatch.fnmatch(filename, pat) for pat in current_ignore_list): continue
                            src_file = os.path.join(dirpath, filename)
                            relative_dir = os.path.relpath(dirpath, source_path)
                            dest_file = os.path.join(target_path, relative_dir if relative_dir != '.' else '', filename)
                            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                            shutil.copy2(src_file, dest_file) # This line is skipped in dry_run
                
                completion_status = "Dry run complete" if prefs().dry_run else "Complete"
                report_message = (
                    f"{operation_type} for {os.path.basename(source_path)} {completion_status.lower()}.\n"
                    f"Source: {source_path}\n"
                    f"Target: {target_path}"
                )
                if prefs().dry_run:
                    # We don't have an exact file count here for blocking mode without re-scanning,
                    # so the message is simpler.
                    report_message += "\n(Dry Run - No files were actually copied/deleted)"
                
                report_icon = 'INFO' # Default
                if operation_type == 'BACKUP':
                    report_icon = 'COLORSET_03_VEC'
                elif operation_type == 'RESTORE':
                    report_icon = 'COLORSET_04_VEC'
                self.report({'INFO'}, report_message)
                self.ShowReport(message=report_message.split('\n'), title=f"{operation_type} Report", icon=report_icon)

            except Exception as e:
                error_report_msg = f"{operation_type} for {os.path.basename(source_path)} failed: {e}\nSource: {source_path}\nTarget: {target_path}"
                self.report({'ERROR'}, error_report_msg)
                self.ShowReport(message=error_report_msg.split('\n'), title=f"{operation_type} Error", icon='ERROR')
        else:
            warning_report_msg = f"Source for {operation_type} not found: {source_path}"
            self.report({'WARNING'}, warning_report_msg)
            self.ShowReport(message=warning_report_msg.split('\n'), title=f"{operation_type} Warning", icon='WARNING')
    
