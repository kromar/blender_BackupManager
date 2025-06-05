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
import re as regular_expression
import pathlib # Added for path manipulation
from datetime import datetime # Added for debug timestamps
from bpy.types import Operator
from bpy.props import StringProperty
from . import preferences # For BM_Preferences, ITEM_DEFINITIONS
from . import utils # For get_addon_preferences, find_versions
from . import ui # For OT_ShowFinalReport, OT_QuitBlenderNoSave
                
class OT_BackupManager(Operator):
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    # bl_options = {'REGISTER'} # Removed, not typically needed for modal operators unless specific registration behavior is desired.
    
    button_input: StringProperty() # type: ignore
    SHARED_FOLDER_NAME = "SharedConfigs" # Used for shared item backups
    
    # --- Modal operator state variables ---
    _timer = None
    files_to_process: list = []
    total_files: int = 0
    processed_files_count: int = 0
    current_source_path: str = ""
    current_target_path: str = ""
    current_operation_type: str = "" # 'BACKUP' or 'RESTORE'
    _progress_started_on_wm: bool = False # True if Blender's WM progress has been started
    # --- Batch operation state variables ---
    is_batch_operation: bool = False
    batch_operations_list: list = []
    current_batch_item_index: int = 0
    total_batch_items: int = 0
    batch_report_lines: list = [] # To accumulate reports from each sub-operation

    ignore_backup = []
    ignore_restore = []
    def create_ignore_pattern(self):
        self.ignore_backup.clear()
        self.ignore_restore.clear()
        list = [x for x in regular_expression.split(',|\s+', utils.get_addon_preferences().ignore_files) if x!='']        
        for item in list:
            self.ignore_backup.append(item)
            self.ignore_restore.append(item)

        if not utils.get_addon_preferences().backup_bookmarks:
            self.ignore_backup.append('bookmarks.txt')
        if not utils.get_addon_preferences().restore_bookmarks:
            self.ignore_restore.append('bookmarks.txt') # Use utils.get_addon_preferences()
        if not utils.get_addon_preferences().backup_recentfiles:
            self.ignore_backup.append('recent-files.txt')
        if not utils.get_addon_preferences().restore_recentfiles:
            self.ignore_restore.append('recent-files.txt') # Use utils.get_addon_preferences()

        if not utils.get_addon_preferences().backup_startup_blend:
            self.ignore_backup.append('startup.blend')
        if not utils.get_addon_preferences().restore_startup_blend:
            self.ignore_restore.append('startup.blend') # Use utils.get_addon_preferences()
        if not utils.get_addon_preferences().backup_userpref_blend:
            self.ignore_backup.append('userpref.blend')
        if not utils.get_addon_preferences().restore_userpref_blend:
            self.ignore_restore.append('userpref.blend') # Use utils.get_addon_preferences()
        if not utils.get_addon_preferences().backup_workspaces_blend:
            self.ignore_backup.append('workspaces.blend')
        if not utils.get_addon_preferences().restore_workspaces_blend:
            self.ignore_restore.append('workspaces.blend') # Use utils.get_addon_preferences()

        if not utils.get_addon_preferences().backup_cache:
            self.ignore_backup.append('cache')
        if not utils.get_addon_preferences().restore_cache:
            self.ignore_restore.append('cache') # Use utils.get_addon_preferences()

        if not utils.get_addon_preferences().backup_datafile:
            self.ignore_backup.append('datafiles')
        if not utils.get_addon_preferences().restore_datafile:
            self.ignore_restore.append('datafiles') # Use utils.get_addon_preferences()

        if not utils.get_addon_preferences().backup_addons:
            self.ignore_backup.append('addons')
        if not utils.get_addon_preferences().restore_addons:
            self.ignore_restore.append('addons') # Use utils.get_addon_preferences()
            
        if not utils.get_addon_preferences().backup_extensions:
            self.ignore_backup.append('extensions')
        if not utils.get_addon_preferences().restore_extensions:
            self.ignore_restore.append('extensions')

        if not utils.get_addon_preferences().backup_presets:
            self.ignore_backup.append('presets')
        if not utils.get_addon_preferences().restore_presets:
            self.ignore_restore.append('presets') # Use utils.get_addon_preferences()
    
    def cancel(self, context):
        """Ensures timer and progress UI are cleaned up if the operator is cancelled externally."""
        # Use the robust prefs() function from core.py
        _debug_active = False # Default to False for safety during cancel
        prefs_instance_for_cancel = None
        try:
            prefs_instance_for_cancel = utils.get_addon_preferences()
            if prefs_instance_for_cancel:
                _debug_active = prefs_instance_for_cancel.debug
        except Exception:
            pass # Ignore errors getting prefs during cancel, prioritize cleanup

        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
                if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Timer removed.")
            except Exception as e:
                if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Error removing timer: {e}")
            self._timer = None

        # Reset UI state related to this operator's modal operation
        try:
            if prefs_instance_for_cancel:
                prefs_instance_for_cancel.show_operation_progress = False
                prefs_instance_for_cancel.operation_progress_message = f"{self.current_operation_type if hasattr(self, 'current_operation_type') and self.current_operation_type else 'Operation'} cancelled (operator cleanup)."
                if self.is_batch_operation:
                    prefs_instance_for_cancel.operation_progress_message = f"Batch operation cancelled."
                self.is_batch_operation = False # Reset batch flag

                prefs_instance_for_cancel.operation_progress_value = 0.0 # Reset progress value
                prefs_instance_for_cancel.abort_operation_requested = False # Reset this flag too
                if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): show_operation_progress and abort_operation_requested reset.")
        except Exception as e:
            if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Error resetting preference flags: {e}")
        if _debug_active: print(f"DEBUG: OT_BackupManager.cancel() EXIT.")
        # Blender expects cancel() to return None


    @staticmethod
    def ShowReport_static(message = [], title = "Message Box", icon = 'INFO'):
        def draw(self_popup, context): # self_popup refers to the Menu instance for the popup
            # This function is kept for direct calls, but deferred calls will use BM_MT_PopupMessage
            for i in message:
                self_popup.layout.label(text=i)
        bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)

    @staticmethod
    def _deferred_show_report_static(message_lines, title, icon, show_restart=False, restart_op_idname=""):
        from . import ui # Import ui locally
        if utils.get_addon_preferences().debug: 
            print(f"DEBUG: _deferred_show_report_static: Preparing to invoke bm.show_final_report. Title='{title}', ShowRestart={show_restart}, RestartOp='{restart_op_idname}'")
        ui.OT_ShowFinalReport.set_report_data(lines=message_lines, 
                                           title=title, 
                                           icon=icon, 
                                           show_restart=show_restart, 
                                           restart_op_idname=restart_op_idname)
        bpy.ops.bm.show_final_report('EXEC_DEFAULT')
        return None # Stop the timer

    # Keep the instance method for direct calls if needed, though static is preferred for deferred.
    def ShowReport(self, message = None, title = "Message Box", icon = 'INFO'):
        OT_BackupManager.ShowReport_static(message, title, icon)
    
    def _get_destination_base_for_item(self, prefs_instance, item_identifier_or_None, target_version_folder_name):
        """
        Determines the base destination directory for an item during BACKUP,
        or the base target directory during RESTORE (which is always local Blender config).
        target_version_folder_name: e.g., "4.1" or "custom_backup_name"
        """
        is_shared = False
        if item_identifier_or_None:
            # Check against actual ITEM_DEFINITIONS identifiers
            # ITEM_DEFINITIONS is available via preferences.ITEM_DEFINITIONS
            if item_identifier_or_None in [item[0] for item in preferences.ITEM_DEFINITIONS]:
                 is_shared = getattr(prefs_instance, f"shared_{item_identifier_or_None}", False)

        if self.current_operation_type == 'BACKUP':
            backup_root = prefs_instance.backup_path
            if is_shared:
                return os.path.join(backup_root, OT_BackupManager.SHARED_FOLDER_NAME, target_version_folder_name)
            else: # Not shared, goes to normal backup location
                return os.path.join(backup_root, prefs_instance.system_id, target_version_folder_name) 
        elif self.current_operation_type == 'RESTORE':
            # Target is always the local Blender user path for that version.
            # self.current_target_path is already set to this in execute()
            # e.g., .../Blender/4.1 or .../Blender/target_backup_version_from_dropdown
            return self.current_target_path
        return None # Should not happen

    def _prepare_file_list(self):
        """Scans source_path and populates self.files_to_process and self.total_files."""
        self.files_to_process.clear()
        self.total_files = 0
        self.processed_files_count = 0

        if not self.current_source_path or not os.path.isdir(self.current_source_path):
            self.report({'WARNING'}, f"Source path does not exist or is not a directory: {self.current_source_path}")
            return False

        prefs_instance = utils.get_addon_preferences()
        self.create_ignore_pattern()
        current_ignore_list = self.ignore_backup if self.current_operation_type == 'BACKUP' else self.ignore_restore

        # Determine the target version folder name for constructing destination paths (during backup)
        version_name_for_path_construction = ""
        if self.current_operation_type == 'BACKUP':
            if self.is_batch_operation:
                # For batch backup, the version name comes directly from the current batch item
                if self.current_batch_item_index < len(self.batch_operations_list):
                    version_name_for_path_construction = self.batch_operations_list[self.current_batch_item_index][3]
                else:
                    # This case should ideally not be reached if batch processing is managed correctly.
                    # Log an error and use a fallback to prevent crashes.
                    print("ERROR: Backup Manager: current_batch_item_index out of bounds during batch backup path construction.")
                    version_name_for_path_construction = "batch_error_version" # Fallback
            elif not prefs_instance.advanced_mode: # Single, non-advanced backup
                version_name_for_path_construction = str(prefs_instance.active_blender_version)
            else: # Single, advanced backup
                if prefs_instance.custom_version_toggle:
                    version_name_for_path_construction = str(prefs_instance.custom_version)
                else:
                    # For advanced single backup, the target version name is derived from the selected source version
                    version_name_for_path_construction = prefs_instance.backup_versions
        # For RESTORE, this specific variable isn't directly used in this function as dest is always local.
        # The _prepare_restore_files_from_source handles its own version_name logic for iterating source.

        if prefs_instance.debug:
            print(f"Preparing file list for {self.current_operation_type}")
            print(f"Source: {self.current_source_path}")
            print(f"Target: {self.current_target_path}")
            print(f"Ignore list: {current_ignore_list}")
            if self.current_operation_type == 'BACKUP':
                print(f"Target version name for path construction: {version_name_for_path_construction}")

        for dirpath, dirnames, filenames in os.walk(self.current_source_path, topdown=True):
            # Prune dirnames based on ignore list (items globally disabled by user)
            dirnames[:] = [
                d for d in dirnames
                if not any(fnmatch.fnmatch(d, pat) for pat in current_ignore_list)
            ]

            for filename in filenames:
                # Check if this file (by its basename) is globally ignored
                if any(fnmatch.fnmatch(filename, pat) for pat in current_ignore_list):
                    continue
                
                src_file = os.path.join(dirpath, filename)

                # Path segment relative to version root (e.g., "scripts/addons/file.py" or "userpref.blend")
                # This is the path of the file relative to self.current_source_path (local Blender version root for backup)
                path_segment_in_version = filename
                relative_dir_part = os.path.relpath(dirpath, self.current_source_path)
                if relative_dir_part != '.':
                    path_segment_in_version = os.path.join(relative_dir_part, filename)

                dest_file = ""
                if self.current_operation_type == 'BACKUP':
                    # Determine the item_identifier for this file to check its shared_status
                    effective_item_id_for_shared_check = None # Use preferences.ITEM_DEFINITIONS
                    if filename in [item[0] for item in preferences.ITEM_DEFINITIONS]:
                        effective_item_id_for_shared_check = filename
                    else:
                        if relative_dir_part and relative_dir_part != '.':
                            # Check parts of the relative path
                            parts = pathlib.Path(relative_dir_part).parts
                            for part in reversed(parts): # Check deeper parts first
                                if part in [item[0] for item in preferences.ITEM_DEFINITIONS]:
                                    effective_item_id_for_shared_check = part
                                    break
                    
                    destination_base = self._get_destination_base_for_item(
                        prefs_instance,
                        effective_item_id_for_shared_check,
                        version_name_for_path_construction # Target version folder name
                    )
                    dest_file = os.path.join(destination_base, path_segment_in_version)

                elif self.current_operation_type == 'RESTORE':
                    # For RESTORE, _prepare_file_list is (or should be) called by a helper that sets current_source_path.
                    # The destination is always self.current_target_path (local Blender config).
                    # The path_segment_in_version is relative to the backup source (shared or non-shared).
                    dest_file = os.path.join(self.current_target_path, path_segment_in_version)

                if os.path.normpath(src_file) == os.path.normpath(dest_file):
                    if prefs_instance.debug: print(f"Skipping copy, source and destination are the same file: {src_file}")
                    continue

                # Ensure no duplicates if this function is somehow called in a way that could overlap
                # (More relevant for the RESTORE multi-call pattern if not handled carefully there)
                if (src_file, dest_file) not in self.files_to_process:
                    self.files_to_process.append((src_file, dest_file))
                elif prefs_instance.debug:
                    print(f"DEBUG: _prepare_file_list: Duplicate file pair skipped: ({src_file}, {dest_file})")
        
        self.total_files = len(self.files_to_process)
        if prefs_instance.debug:
            print(f"Total files to process: {self.total_files}")
        return True

    # _process_next_batch_item_or_finish and modal methods remain largely the same,
    # as they operate on the prepared self.files_to_process list.
    # The key is that self.files_to_process now contains the correct (src, dest)
    # pairs, including those for shared items.

    def _process_next_batch_item_or_finish(self, context):
        """
        Sets up the next item in a batch operation for modal processing,
        or finalizes the batch if all items are done.
        Returns {'RUNNING_MODAL'} if a new item is started modally,
        {'FINISHED'} if batch is complete or no items to process initially.
        """
        pref_instance = utils.get_addon_preferences() # Get fresh preferences

        if self.current_batch_item_index < self.total_batch_items:
            source_path, target_path, op_type, version_name = self.batch_operations_list[self.current_batch_item_index]
            # For BACKUP, source_path is local Blender version, target_path is primary backup location (e.g. .../system_id/version_name)
            # For RESTORE, source_path is primary backup location (e.g. .../system_id/version_name), target_path is local Blender version

            self.current_operation_type = op_type # 'BACKUP' or 'RESTORE'
            item_name_for_log = version_name # Use the version name for logging

            if pref_instance.clean_path and self.current_operation_type == 'BACKUP':
                # Clean default target path for this batch item
                default_target_path_to_clean = target_path # This is the .../system_id/version_name path for backup
                if os.path.exists(default_target_path_to_clean):
                    if pref_instance.debug: print(f"DEBUG: Batch Clean: Attempting to clean default path for {item_name_for_log}: {default_target_path_to_clean}")
                    try:
                        if not pref_instance.dry_run: shutil.rmtree(default_target_path_to_clean)
                        cleaned_msg = f"Cleaned default path for {item_name_for_log}: {default_target_path_to_clean}"
                        if pref_instance.debug or pref_instance.dry_run: print(cleaned_msg); self.batch_report_lines.append(f"INFO: {cleaned_msg}")
                    except OSError as e:
                        fail_clean_msg = f"Failed to clean default path for {item_name_for_log} ({default_target_path_to_clean}): {e}"; print(f"ERROR: {fail_clean_msg}" if pref_instance.debug else ""); self.batch_report_lines.append(f"WARNING: {fail_clean_msg}")
                # Clean shared target path for this batch item's version_name
                shared_target_path_to_clean = os.path.join(pref_instance.backup_path, OT_BackupManager.SHARED_FOLDER_NAME, version_name)
                if os.path.exists(shared_target_path_to_clean):
                    if pref_instance.debug: print(f"DEBUG: Batch Clean: Attempting to clean shared path for {item_name_for_log}: {shared_target_path_to_clean}")
                    # Similar try-except for shutil.rmtree(shared_target_path_to_clean)
                    # For brevity, assuming similar error handling as above.
                    if not pref_instance.dry_run: shutil.rmtree(shared_target_path_to_clean) # Simplified for example
                    self.batch_report_lines.append(f"INFO: Cleaned shared path for {item_name_for_log}: {shared_target_path_to_clean}")

            # --- Prepare File List ---
            self.files_to_process.clear() # Always clear before preparing for a new item

            if self.current_operation_type == 'BACKUP':
                self.current_source_path = source_path # Local Blender version
                # For BACKUP, self.current_target_path is not directly used by _prepare_file_list in the same way.
                # _get_destination_base_for_item uses version_name and backup_root to construct paths.
                # Setting it conceptually to the non-shared backup destination for clarity.
                self.current_target_path = target_path 
                if not self._prepare_file_list(): # Populates self.files_to_process, self.total_files
                    err_msg = f"Batch item {self.current_batch_item_index + 1}/{self.total_batch_items} ({op_type} {item_name_for_log}): Error preparing file list for BACKUP. Skipping."
                    self.report({'WARNING'}, err_msg); self.batch_report_lines.append(f"WARNING: {err_msg}")
                    pref_instance.operation_progress_message = err_msg
                    self.current_batch_item_index += 1
                    return self._process_next_batch_item_or_finish(context) # Try next
            elif self.current_operation_type == 'RESTORE':
                # source_path from batch list is the non-shared backup location (e.g., .../backup_path/system_id/version_name)
                non_shared_source_for_restore = source_path
                shared_source_for_restore = os.path.join(pref_instance.backup_path, OT_BackupManager.SHARED_FOLDER_NAME, version_name)
                # target_path from batch list is the ultimate local Blender config destination (e.g., .../Blender/version_name)
                self.current_target_path = target_path # Set for _prepare_restore_files_from_source

                self._prepare_restore_files_from_source(context, non_shared_source_for_restore, self.current_target_path, version_name, process_shared_state=False)
                self._prepare_restore_files_from_source(context, shared_source_for_restore, self.current_target_path, version_name, process_shared_state=True)
                self.total_files = len(self.files_to_process) # Update total files after both calls

            if self.total_files == 0:
                no_files_msg = f"Batch item {self.current_batch_item_index + 1}/{self.total_batch_items} ({op_type} {item_name_for_log}): No files to process. Skipping."
                self.report({'INFO'}, no_files_msg)
                self.batch_report_lines.append(f"INFO: {no_files_msg}")
                pref_instance.operation_progress_message = no_files_msg
                self.current_batch_item_index += 1
                return self._process_next_batch_item_or_finish(context) # Try next

            # Item has files, set up for modal processing
            self.processed_files_count = 0 # Reset for the new item
            initial_message = f"Batch {self.current_operation_type} ({self.current_batch_item_index + 1}/{self.total_batch_items} - {item_name_for_log}): Starting... ({self.total_files} files)"
            self.report({'INFO'}, initial_message) # Report to Blender status bar
            pref_instance.show_operation_progress = True
            pref_instance.operation_progress_message = initial_message
            pref_instance.operation_progress_value = 0.0
            
            if self._timer is None:
                self._timer = context.window_manager.event_timer_add(0.0, window=context.window)
                if pref_instance.debug: print(f"DEBUG: Batch: Timer ADDED for item {self.current_batch_item_index + 1} ('{item_name_for_log}')")
            # Modal handler should already be active from the initial execute call for the batch.
            return {'RUNNING_MODAL'} # Signal that an item is ready for modal processing
        else:
            # All batch items processed
            self.is_batch_operation = False # Reset flag
            final_batch_message = f"Batch operation complete. Processed {self.total_batch_items} items."
            self.report({'INFO'}, final_batch_message)
            
            report_title = "Batch Operation Report"
            overall_op_type = "Operation"
            if self.batch_operations_list:
                 overall_op_type = self.batch_operations_list[0][2] # Get op_type from first item
                 report_title = f"Batch {overall_op_type.capitalize()} Report"

            show_restart_btn_batch = False
            if overall_op_type == 'RESTORE': # Show restart info even on dry run for simulation
                self.batch_report_lines.append("") # Add a blank line for spacing
                self.batch_report_lines.append("IMPORTANT: For restored settings to fully apply, this Blender session must be ended.")
                self.batch_report_lines.append(f"Use the '{ui.OT_QuitBlenderNoSave.bl_label}' button in the report.")
                show_restart_btn_batch = True

            final_report_lines = [final_batch_message] + self.batch_report_lines[:]            
            bpy.app.timers.register(
                lambda final_report_lines=final_report_lines, report_title=report_title, show_restart_btn_batch=show_restart_btn_batch:
                    OT_BackupManager._deferred_show_report_static(
                        final_report_lines, report_title, 'INFO', show_restart=show_restart_btn_batch, restart_op_idname="bm.quit_blender_no_save"
                    ), # This will call ui.OT_ShowFinalReport via _deferred_show_report_static
                first_interval=0.01
                )

            pref_instance.show_operation_progress = False
            pref_instance.operation_progress_message = final_batch_message
            pref_instance.operation_progress_value = 100.0
            pref_instance.abort_operation_requested = False # Reset abort flag
            
            if self._timer: # Clean up timer if it was from the last item
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
            return {'FINISHED'}

    def modal(self, context, event):
        pref_instance = utils.get_addon_preferences() # Get fresh preferences
        # Capture the state of the abort request flag at the beginning of this modal event
        was_aborted_by_ui_button = pref_instance.abort_operation_requested
        
        # Check for abort request first or ESC key
        # Or if all files are processed (files_to_process is empty AND processed_files_count matches total_files)
        # Or if total_files was 0 to begin with (and processed is also 0)
        if was_aborted_by_ui_button or event.type == 'ESC' or \
           (not self.files_to_process and self.processed_files_count >= self.total_files and self.total_files > 0) or \
           (self.total_files == 0 and self.processed_files_count == 0): # Handles case of no files to process initially

            # Timer for the *just completed* item (or an item that had 0 files)
            if self._timer:
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
                if pref_instance.debug: print(f"DEBUG: OT_BackupManager.modal(): Timer removed for completed/cancelled item.")

            # Reset the flag now that its state (was_aborted_by_ui_button) has been used for the decision to exit the modal.
            if was_aborted_by_ui_button:
                pref_instance.abort_operation_requested = False # Reset for next potential operation

            if event.type == 'ESC' or was_aborted_by_ui_button:
                op_description = f"{self.current_operation_type}"
                if self.is_batch_operation:
                    op_description = f"Batch {self.current_operation_type} (item {self.current_batch_item_index + 1}/{self.total_batch_items})"
                
                cancel_message = f"{op_description} cancelled by user."
                self.report({'WARNING'}, cancel_message)
                bpy.app.timers.register(
                    lambda: OT_BackupManager._deferred_show_report_static([cancel_message], "Operation Cancelled", "ERROR"), 
                    first_interval=0.01
                ) # This will call ui.OT_ShowFinalReport
                
                pref_instance.operation_progress_message = cancel_message
                pref_instance.operation_progress_value = 0.0 
                pref_instance.show_operation_progress = False 
                self.is_batch_operation = False # Ensure batch mode is exited
                return {'CANCELLED'}
            else: # Operation completed successfully or no files to process
                # This block handles completion of an individual item (could be part of a batch or a single op)
                completion_status_item = "Dry run complete" if pref_instance.dry_run else "Complete"
                display_processed_count = min(self.processed_files_count, self.total_files)
                version_name_for_item_report = os.path.basename(self.current_source_path) if self.current_operation_type == 'BACKUP' else os.path.basename(self.current_target_path)
                if self.is_batch_operation and self.current_batch_item_index < self.total_batch_items:
                     version_name_for_item_report = self.batch_operations_list[self.current_batch_item_index][3] # Get version_name

                item_report_msg = f"Item '{version_name_for_item_report}' ({self.current_operation_type}) {completion_status_item.lower()}: {display_processed_count}/{self.total_files} files."
                if pref_instance.dry_run and self.total_files > 0: item_report_msg += " (Dry Run)"

                if self.is_batch_operation:
                    self.batch_report_lines.append(f"INFO: {item_report_msg}")
                    if pref_instance.debug: print(f"DEBUG: Batch item reported: {item_report_msg}")
                    
                    self.current_batch_item_index += 1
                    result_next_item = self._process_next_batch_item_or_finish(context)
                    
                    if result_next_item == {'RUNNING_MODAL'}:
                        # New item is set up, its timer is running. Modal loop continues.
                        return {'PASS_THROUGH'} 
                    else: # {'FINISHED'} - batch fully complete
                        # _process_next_batch_item_or_finish handled final report and prefs update
                        return {'FINISHED'}
                else: # Single operation completed
                    # Initialize show_restart_btn and prepare report_message_lines *before* scheduling the report
                    show_restart_btn = False
                    report_message_lines = [
                        f"{self.current_operation_type} {completion_status_item.lower()}.",
                        f"{display_processed_count}/{self.total_files} files processed."
                    ]
                    if self.current_source_path: report_message_lines.append(f"Source: {self.current_source_path}")
                    if self.current_target_path: report_message_lines.append(f"Target: {self.current_target_path}")

                    report_message_lines = [
                        f"{self.current_operation_type} {completion_status_item.lower()}.",
                        f"{display_processed_count}/{self.total_files} files processed."
                    ]
                    if self.current_source_path: report_message_lines.append(f"Source: {self.current_source_path}")
                    if self.current_target_path: report_message_lines.append(f"Target: {self.current_target_path}")
                    if pref_instance.dry_run and self.total_files > 0: 
                        report_message_lines.append("(Dry Run - No files were actually copied/deleted)")

                    # Add restart instructions if it's a successful non-dry run RESTORE
                    _restart_op_idname_for_lambda = "" # Default to empty string
                    if self.current_operation_type == 'RESTORE': # Show restart info even on dry run for simulation
                        report_message_lines.append("") # Add a blank line for spacing
                        report_message_lines.append("IMPORTANT: For restored settings to fully apply, this Blender session must be ended.")
                        report_message_lines.append(f"Use the '{ui.OT_QuitBlenderNoSave.bl_label}' button below.")
                        show_restart_btn = True
                        _restart_op_idname_for_lambda = ui.OT_QuitBlenderNoSave.bl_idname # Set the idname string

                    report_icon = 'INFO' 
                    if self.current_operation_type == 'BACKUP': report_icon = 'COLORSET_03_VEC'
                    elif self.current_operation_type == 'RESTORE': report_icon = 'COLORSET_04_VEC'
                    
                    # Capture self.current_operation_type for the lambda
                    op_type_for_report_title = self.current_operation_type
                    
                    # Capture all necessary values for the lambda using default arguments
                    bpy.app.timers.register(
                        lambda lines=report_message_lines[:], # Pass a copy
                               title=f"{op_type_for_report_title} Report",
                               icon_val=report_icon,
                               show_restart_val=show_restart_btn,
                               op_idname_val=_restart_op_idname_for_lambda:
                        OT_BackupManager._deferred_show_report_static(
                            lines, title, icon_val,
                            show_restart=show_restart_val, restart_op_idname=op_idname_val
                        ), first_interval=0.01)
                    self.report({'INFO'}, " ".join(report_message_lines)) 
                    
                    pref_instance.operation_progress_message = f"{self.current_operation_type} {completion_status_item.lower()}."
                    pref_instance.operation_progress_value = 100.0 
                    pref_instance.show_operation_progress = False 
                    pref_instance.abort_operation_requested = False # Reset abort flag
                    return {'FINISHED'}


        if event.type == 'TIMER':
            if not self.files_to_process: 
                # This state (timer event but no files left) should lead to FINISHED via the top condition
                # in the next event cycle. Update progress one last time for safety.
                if self.total_files > 0:
                    current_progress_val = (self.processed_files_count / self.total_files) * 100.0
                else: # No files to begin with
                    current_progress_val = 100.0
                
                finalizing_msg = f"{self.current_operation_type}: {self.processed_files_count}/{self.total_files} files ({current_progress_val:.1f}%) - Finalizing..."
                if self.is_batch_operation:
                    version_name_finalize = self.batch_operations_list[self.current_batch_item_index][3] if self.current_batch_item_index < self.total_batch_items else "item"
                    finalizing_msg = f"Batch {self.current_operation_type} ({self.current_batch_item_index + 1}/{self.total_batch_items} - {version_name_finalize}): Finalizing..."

                pref_instance.operation_progress_message = finalizing_msg
                pref_instance.operation_progress_value = current_progress_val
                return {'PASS_THROUGH'} # Let the next cycle handle termination via top conditions

            # Process a batch of files
            for _ in range(preferences.BM_Preferences.FILES_PER_TICK_MODAL_OP): # Use constant from preferences
                if not self.files_to_process:
                    break # No more files in the list for this tick

                src_file, dest_file = self.files_to_process.pop(0)

                if not pref_instance.dry_run:
                    try:
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        shutil.copy2(src_file, dest_file)
                    except (OSError, shutil.Error) as e: # Catch more specific errors
                        print(f"Error copying {src_file} to {dest_file}: {e}")
                        # Consider collecting errors for a summary report
                
                self.processed_files_count += 1
            
            # Update progress after processing the batch
            if self.total_files > 0:
                current_progress_val = (self.processed_files_count / self.total_files) * 100.0
            else: 
                current_progress_val = 100.0 # Should be caught by initial total_files == 0 check
            
            # Update the message string for window label and status bar
            progress_display_message = f"{self.current_operation_type}: {self.processed_files_count}/{self.total_files} files ({current_progress_val:.1f}%)"
            if self.is_batch_operation:
                version_name_progress = "item"
                if self.current_batch_item_index < len(self.batch_operations_list): # Check bounds
                    version_name_progress = self.batch_operations_list[self.current_batch_item_index][3] # version_name
                
                progress_display_message = (
                    f"Batch {self.current_operation_type} ({self.current_batch_item_index + 1}/{self.total_batch_items} - {version_name_progress}): "
                    f"{self.processed_files_count}/{self.total_files} files ({current_progress_val:.1f}%)"
                )
            pref_instance.operation_progress_message = progress_display_message
            pref_instance.operation_progress_value = current_progress_val
            if pref_instance.debug:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"DEBUG: [{timestamp}] OT_BackupManager.modal() (TIMER) updated progress to: {pref_instance.operation_progress_value:.1f}%, Msg: '{pref_instance.operation_progress_message}'")

            # Force redraw of UI to show progress, including the Backup Manager window if it's open
            for wm_window_iter in context.window_manager.windows:
                for area_iter in wm_window_iter.screen.areas:
                    area_iter.tag_redraw()
            if pref_instance.debug:
                # This log can be very verbose, so it's commented out by default.
                # print(f"DEBUG: OT_BackupManager.modal() (TIMER) tagged all areas for redraw at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}.")
                pass

        return {'PASS_THROUGH'} # Allow other events to be processed

    def _prepare_restore_files_from_source(self, context, source_dir_for_items, ultimate_target_dir, version_name_for_path, process_shared_state):
        """
        Helper to populate self.files_to_process for RESTORE operations from a specific source directory.
        source_dir_for_items: The backup location to scan (e.g., .../MyPC/4.1/ OR .../SharedConfigs/4.1/)
        ultimate_target_dir: The local Blender version path (e.g., .../Blender/4.1/)
        process_shared_state: True if we are looking for items that are marked as shared in prefs.
        """
        prefs_instance = utils.get_addon_preferences()
        # self.ignore_restore should already be set by create_ignore_pattern() in execute()
        current_ignore_list = self.ignore_restore

        shared_item_identifiers_globally = { # All items marked as shared in prefs
            item_def[0] for item_def in preferences.ITEM_DEFINITIONS # Use preferences.ITEM_DEFINITIONS
            if getattr(prefs_instance, f"shared_{item_def[0]}", False)
        }

        if not os.path.isdir(source_dir_for_items):
            if prefs_instance.debug:
                print(f"DEBUG: _prepare_restore_files_from_source: Source directory not found, skipping: {source_dir_for_items}")
            return

        for dirpath, dirnames, filenames in os.walk(source_dir_for_items, topdown=True):
            dirnames_copy = list(dirnames)
            dirnames[:] = []
            for d_name in dirnames_copy:
                is_d_globally_shared = d_name in shared_item_identifiers_globally
                is_d_ignored_by_user = any(fnmatch.fnmatch(d_name, pat) for pat in current_ignore_list)

                if is_d_ignored_by_user: continue

                if process_shared_state: # Looking for items that should come from shared backup
                    if is_d_globally_shared: dirnames.append(d_name)
                else: # Looking for items that should come from non-shared backup
                    if not is_d_globally_shared: dirnames.append(d_name)
            
            for f_name in filenames:
                is_f_globally_shared = f_name in shared_item_identifiers_globally
                is_f_ignored_by_user = any(fnmatch.fnmatch(f_name, pat) for pat in current_ignore_list)

                if is_f_ignored_by_user: continue

                process_this_file = False
                if process_shared_state:
                    if is_f_globally_shared: process_this_file = True
                else:
                    if not is_f_globally_shared: process_this_file = True
                
                if not process_this_file: continue

                src_file = os.path.join(dirpath, f_name)
                path_segment_in_backup = os.path.relpath(src_file, source_dir_for_items)
                dest_file = os.path.join(ultimate_target_dir, path_segment_in_backup)

                if os.path.normpath(src_file) == os.path.normpath(dest_file): continue
                if (src_file, dest_file) not in self.files_to_process: # Avoid duplicates
                    self.files_to_process.append((src_file, dest_file))

        return {'PASS_THROUGH'} # Allow other events to be processed

    def execute(self, context): 
        pref_instance = utils.get_addon_preferences()
        pref_backup_versions = preferences.BM_Preferences.backup_version_list
        pref_restore_versions = preferences.BM_Preferences.restore_version_list

        if pref_instance.debug:
            print("\n\nbutton_input: ", self.button_input)                    
        
        if pref_instance.backup_path:
            self.current_operation_type = "" # Reset for single ops
            self.files_to_process.clear() # Clear before any operation
            self.is_batch_operation = False # Reset for single ops
            self.create_ignore_pattern() # Initialize ignore lists based on current prefs

            if self.button_input in {'BACKUP', 'RESTORE'}:
                self.current_operation_type = self.button_input
                version_name_for_operation = "" # e.g. "4.1" or "custom_name"
                if not pref_instance.advanced_mode:            
                    if self.button_input == 'BACKUP':
                        self.current_source_path = pref_instance.blender_user_path # Local Blender version
                        self.current_target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, str(pref_instance.active_blender_version)) # Backup location
                    elif self.button_input == 'RESTORE':
                        # --- Temporarily disable 'Save on Quit' for RESTORE operation ---
                        prefs_main = context.preferences # Use bpy.context.preferences
                        if prefs_main and hasattr(prefs_main, 'use_preferences_save'):
                            if prefs_main.use_preferences_save: # Only change if it was True
                                prefs_main.use_preferences_save = False
                                if pref_instance.debug:
                                    print(f"DEBUG: OT_BackupManager.execute RESTORE (non-advanced): Temporarily disabled 'Save Preferences on Quit'.")
                        elif pref_instance.debug:
                            print(f"DEBUG: OT_BackupManager.execute RESTORE (non-advanced): Could not access 'use_save_on_quit'.")
                        # --- Set paths for non-advanced RESTORE ---
                        # self.current_source_path will be set by _prepare_restore_files_from_source calls
                        self.current_target_path = pref_instance.blender_user_path
                        version_name_for_operation = str(pref_instance.active_blender_version)

                else:    
                    if self.button_input == 'BACKUP': # Advanced Mode Backup
                        self.current_source_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  pref_instance.backup_versions)
                        if pref_instance.custom_version_toggle:
                            self.current_target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, str(pref_instance.custom_version))
                        else: 
                            # Target for backup is based on source version name (backup_versions)
                            self.current_target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, pref_instance.backup_versions)
                    elif self.button_input == 'RESTORE': # Advanced Mode Restore
                        # --- Temporarily disable 'Save on Quit' for RESTORE operation (Advanced) ---
                        prefs_main = context.preferences # Use bpy.context.preferences
                        if prefs_main and hasattr(prefs_main, 'use_preferences_save'):
                            if prefs_main.use_preferences_save: # Only change if it was True
                                prefs_main.use_preferences_save = False
                                if pref_instance.debug:
                                    print(f"DEBUG: OT_BackupManager.execute RESTORE (advanced): Temporarily disabled 'Save Preferences on Quit'.")
                        elif pref_instance.debug:
                            print(f"DEBUG: OT_BackupManager.execute RESTORE (advanced): Could not access 'use_save_on_quit'.")
                        # --- Set paths for advanced RESTORE ---
                        # self.current_source_path will be set by _prepare_restore_files_from_source calls
                        self.current_target_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  pref_instance.backup_versions)
                        version_name_for_operation = pref_instance.restore_versions # This is the version name from backup list

                if self.button_input == 'BACKUP':
                    if pref_instance.clean_path:
                        # Determine version name for cleaning backup paths
                        version_to_clean_name = ""
                        if not pref_instance.advanced_mode:
                            version_to_clean_name = str(pref_instance.active_blender_version)
                        else:
                            if pref_instance.custom_version_toggle:
                                version_to_clean_name = str(pref_instance.custom_version)
                            else:
                                version_to_clean_name = pref_instance.backup_versions

                        # Clean default target path
                        # System ID is always used for non-shared backups
                        default_target_to_clean = os.path.join(pref_instance.backup_path, pref_instance.system_id, version_to_clean_name)

                        if os.path.exists(default_target_to_clean):
                            if pref_instance.debug: print(f"Attempting to clean default backup path: {default_target_to_clean}")
                            try:
                                if not pref_instance.dry_run: shutil.rmtree(default_target_to_clean)
                            except OSError as e: self.report({'WARNING'}, f"Failed to clean {default_target_to_clean}: {e}")
                        # Clean shared target path
                        shared_target_to_clean = os.path.join(pref_instance.backup_path, OT_BackupManager.SHARED_FOLDER_NAME, version_to_clean_name)
                        if os.path.exists(shared_target_to_clean):
                            if pref_instance.debug: print(f"Attempting to clean shared backup path: {shared_target_to_clean}")
                            try:
                                if not utils.get_addon_preferences().dry_run: shutil.rmtree(shared_target_to_clean)
                            except OSError as e: self.report({'WARNING'}, f"Failed to clean {shared_target_to_clean}: {e}")
                    if not self._prepare_file_list(): return {'CANCELLED'} # Populates self.files_to_process for BACKUP

                elif self.button_input == 'RESTORE':
                    # Non-shared source path
                    # System ID is always used for non-shared backups
                    non_shared_source_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, version_name_for_operation)
                    self._prepare_restore_files_from_source(context, non_shared_source_path, self.current_target_path, version_name_for_operation, process_shared_state=False)
                    # Shared source path
                    shared_source_path = os.path.join(pref_instance.backup_path, OT_BackupManager.SHARED_FOLDER_NAME, version_name_for_operation)
                    self._prepare_restore_files_from_source(context, shared_source_path, self.current_target_path, version_name_for_operation, process_shared_state=True)
                    self.total_files = len(self.files_to_process) # Update total files after both calls
                
                if self.total_files == 0: # Handle case where no files are found to process
                    report_message = f"No files to {self.current_operation_type.lower()}"
                    if self.current_source_path:
                         report_message += f" from {self.current_source_path}"
                    
                    if pref_instance.dry_run: # Clarify dry run message for 0 files
                        report_message += " (Dry Run - no files would have been processed)."
                    else:
                        report_message += "."


                    self.report({'INFO'}, report_message) # Report to Blender status bar
                    pref_instance.show_operation_progress = False # No modal progress needed
                    pref_instance.operation_progress_message = report_message # For window if open

                    # Determine title and icon for the deferred report
                    op_type_for_report = op_type_for_report = self.current_operation_type or "Operation"
                    icon_for_report = 'INFO' # Default
                    if self.current_operation_type == 'BACKUP': icon_for_report = 'COLORSET_03_VEC'
                    elif self.current_operation_type == 'RESTORE': icon_for_report = 'COLORSET_04_VEC'
                    
                    # Capture values for the lambda to ensure they are correct at execution time
                    _msg_lines = report_message.split('\n')
                    _title = f"{op_type_for_report} Report"
                    _icon = icon_for_report

                    bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static(
                        _msg_lines, _title, _icon
                    ), first_interval=0.01) # This will call ui.OT_ShowFinalReport

                    return {'FINISHED'}

                initial_message = f"Starting {self.current_operation_type}... ({self.total_files} files)"
                self.report({'INFO'}, initial_message) # Report initial status to Blender status bar
                
                # Set preferences for the addon window's display
                pref_instance.show_operation_progress = True
                pref_instance.operation_progress_message = initial_message # For the window label
                pref_instance.operation_progress_value = 0.0 # Initialize progress value
                
                self._timer = context.window_manager.event_timer_add(0.0, window=context.window) # Adjusted interval
                
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            
            elif self.button_input == 'BATCH_BACKUP':
                self.is_batch_operation = True
                self.batch_operations_list.clear()
                self.batch_report_lines.clear()
                for version in pref_backup_versions: # Iterate over the list from preferences
                    version_name = version[0] # e.g., "4.1"
                    source_path = os.path.join(os.path.dirname(pref_instance.blender_user_path), version_name) # Local Blender version path
                    target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, version_name) # Backup location
                    self.batch_operations_list.append((source_path, target_path, 'BACKUP', version_name))
                self.total_batch_items = len(self.batch_operations_list)
                self.current_batch_item_index = 0
                if not self.batch_operations_list: # Check if list is empty
                    self.report({'INFO'}, "No items found for batch backup.")
                    self.is_batch_operation = False # Reset
                    return {'FINISHED'}
                context.window_manager.modal_handler_add(self) # Add modal handler ONCE for the whole batch
                return self._process_next_batch_item_or_finish(context)

            elif self.button_input == 'BATCH_RESTORE':
                # --- Temporarily disable 'Save on Quit' for BATCH_RESTORE operation ---
                prefs_main = context.preferences # Use bpy.context.preferences
                if prefs_main and hasattr(prefs_main, 'use_preferences_save'):
                    if prefs_main.use_preferences_save: # Only change if it was True
                        prefs_main.use_preferences_save = False
                        if pref_instance.debug:
                            print(f"DEBUG: OT_BackupManager.execute BATCH_RESTORE: Temporarily disabled 'Save Preferences on Quit' for the batch.")
                elif pref_instance.debug:
                    print(f"DEBUG: OT_BackupManager.execute BATCH_RESTORE: Could not access 'use_save_on_quit' to disable it for the batch.")
                # --- End temporary disable ---
                self.is_batch_operation = True
                self.batch_operations_list.clear()
                self.batch_report_lines.clear()
                for version in pref_restore_versions: # Iterate over the list from preferences
                    version_name = version[0] # e.g., "4.1" from backup
                    source_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, version_name) # Backup location
                    target_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  version_name) # Local Blender version path
                    self.batch_operations_list.append((source_path, target_path, 'RESTORE', version_name))
                self.total_batch_items = len(self.batch_operations_list)
                self.current_batch_item_index = 0
                if not self.batch_operations_list: # Check if list is empty
                    self.report({'INFO'}, "No items found for batch restore.")
                    self.is_batch_operation = False # Reset
                    return {'FINISHED'}
                context.window_manager.modal_handler_add(self) # Add modal handler ONCE for the whole batch
                return self._process_next_batch_item_or_finish(context)

            elif self.button_input == 'DELETE_BACKUP':
                if not pref_instance.advanced_mode:            
                    target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, str(pref_instance.active_blender_version))
                else:                                                 
                    if pref_instance.custom_version_toggle:
                        target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, str(pref_instance.custom_version))
                    else:                
                        target_path = os.path.join(pref_instance.backup_path, pref_instance.system_id, pref_instance.restore_versions)

                if os.path.exists(target_path):
                    try:
                        if not pref_instance.dry_run:
                            shutil.rmtree(target_path)
                        action_verb = "Would delete" if pref_instance.dry_run else "Deleted"
                        report_msg_line1 = f"{action_verb} backup:"
                        report_msg_line2 = target_path
                        final_report_lines = [report_msg_line1, report_msg_line2]

                        # Also attempt to delete the corresponding shared path for that version
                        version_name_of_deleted = os.path.basename(target_path)
                        shared_path_to_delete = os.path.join(pref_instance.backup_path, OT_BackupManager.SHARED_FOLDER_NAME, version_name_of_deleted)
                        if os.path.exists(shared_path_to_delete):
                            if not pref_instance.dry_run:
                                shutil.rmtree(shared_path_to_delete)
                            final_report_lines.append(f"{action_verb} shared backup part:")
                            final_report_lines.append(shared_path_to_delete)
                            if pref_instance.debug or pref_instance.dry_run: print(f"{action_verb} Shared Backup Part: {shared_path_to_delete}")
                        
                        self.report({'INFO'}, " ".join(final_report_lines))
                        # This will call ui.OT_ShowFinalReport
                        bpy.app.timers.register(
                            lambda lines=final_report_lines: OT_BackupManager._deferred_show_report_static(lines, "Delete Backup Report", 'COLORSET_01_VEC'),
                            first_interval=0.01
                        )
                        if pref_instance.debug or pref_instance.dry_run:
                             print(f"\n{action_verb} Backup: {target_path}")

                    except OSError as e:
                        action_verb = "Failed to (dry run) delete" if pref_instance.dry_run else "Failed to delete"
                        error_msg_line1 = f"{action_verb} {target_path}:"
                        error_msg_line2 = str(e)
                        self.report({'WARNING'}, f"{error_msg_line1} {error_msg_line2}")
                        # This will call ui.OT_ShowFinalReport
                        bpy.app.timers.register(
                            lambda lines=[error_msg_line1, error_msg_line2]: OT_BackupManager._deferred_show_report_static(lines, "Delete Backup Error", 'ERROR'),
                            first_interval=0.01
                        )
                        if utils.get_addon_preferences().debug: # Keep print for debug
                            print(f"\n{action_verb} {target_path}: {e}")
                else:
                    not_found_msg = f"Not found, nothing to delete: {target_path}"
                    self.report({'INFO'}, not_found_msg)
                    # This will call ui.OT_ShowFinalReport
                    bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static([f"Not found, nothing to delete:", target_path], "Delete Backup Report", 'INFO'), first_interval=0.01)
                    if pref_instance.debug: # Keep print for debug
                        print(f"\nBackup to delete not found: {target_path}")

            elif self.button_input == 'SEARCH_BACKUP':
                _search_start_sb = None
                if pref_instance.debug:
                    _search_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP START")
                # Path to the directory containing Blender version folders (e.g., .../Blender/3.6, .../Blender/4.0)
                blender_versions_parent_dir = os.path.dirname(bpy.utils.resource_path(type='USER'))

                pref_backup_versions.clear()
                _fv1_start_sb = None
                if pref_instance.debug:
                    _fv1_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP calling find_versions for blender_versions_parent_dir: {blender_versions_parent_dir}")
                found_backup_versions = utils.find_versions(blender_versions_parent_dir) # Use utils
                if pref_instance.debug:
                    _fv1_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_fv1_end_sb - _fv1_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP find_versions for blender_versions_parent_dir DONE")
                pref_backup_versions.extend(found_backup_versions)
                pref_backup_versions.sort(reverse=True)

                # For restore_versions, search within the system_id folder in the backup_path
                system_specific_backup_path = os.path.join(pref_instance.backup_path, pref_instance.system_id)
                pref_restore_versions.clear()
                _fv2_start_sb = None
                if pref_instance.debug:
                    _fv2_start_sb = datetime.now()
                    print(f"DEBUG: execute SEARCH_BACKUP calling find_versions for backup_path: {system_specific_backup_path}")
                combined_restore_versions = utils.find_versions(system_specific_backup_path) + pref_backup_versions # Use utils
                if pref_instance.debug:
                    _fv2_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_fv2_end_sb - _fv2_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP find_versions for backup_path DONE")
                # Use dict.fromkeys to preserve order of first appearance if that's desired before sorting
                pref_restore_versions.extend(list(dict.fromkeys(combined_restore_versions)))
                pref_restore_versions.sort(reverse=True)
                if pref_instance.debug and _search_start_sb:
                    _search_end_sb = datetime.now()
                    print(f"DEBUG: (took: {(_search_end_sb - _search_start_sb).total_seconds():.6f}s) execute SEARCH_BACKUP END")

            elif self.button_input == 'SEARCH_RESTORE': 
                _search_start_sr = None
                if pref_instance.debug:
                    _search_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE START")
                blender_versions_parent_dir = os.path.dirname(bpy.utils.resource_path(type='USER'))

                # For restore_versions, search within the system_id folder in the backup_path
                system_specific_backup_path = os.path.join(pref_instance.backup_path, pref_instance.system_id)
                pref_restore_versions.clear()
                _fv1_start_sr = None
                if pref_instance.debug:
                    _fv1_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE calling find_versions for backup_path: {system_specific_backup_path}")
                found_restore_versions = utils.find_versions(system_specific_backup_path) # Use utils
                if pref_instance.debug:
                    _fv1_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_fv1_end_sr - _fv1_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE find_versions for backup_path DONE")
                pref_restore_versions.extend(found_restore_versions)
                pref_restore_versions.sort(reverse=True) 

                pref_backup_versions.clear()
                _fv2_start_sr = None
                if pref_instance.debug:
                    _fv2_start_sr = datetime.now()
                    print(f"DEBUG: execute SEARCH_RESTORE calling find_versions for blender_versions_parent_dir: {blender_versions_parent_dir}")
                combined_backup_versions = utils.find_versions(blender_versions_parent_dir) + pref_restore_versions # Use utils
                if pref_instance.debug:
                    _fv2_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_fv2_end_sr - _fv2_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE find_versions for blender_versions_parent_dir DONE")

                if pref_instance.debug:
                    print("Combined backup versions before filtering: ", combined_backup_versions)
                
                # Filter and sort backup versions
                unique_backup_versions = list(dict.fromkeys(combined_backup_versions))
                valid_backup_versions = []
                for version_tuple in unique_backup_versions:
                    try:
                        float(version_tuple[0]) # Check if version name can be a float
                        valid_backup_versions.append(version_tuple)
                    except ValueError:
                        if pref_instance.debug:
                            print(f"Filtered out non-float-like version from backup_versions: {version_tuple[0]}")
                
                pref_backup_versions.extend(valid_backup_versions)
                if pref_instance.debug:
                    print("Final backup_versions list: ", pref_backup_versions)
                pref_backup_versions.sort(reverse=True)
                if pref_instance.debug and _search_start_sr:
                    _search_end_sr = datetime.now()
                    print(f"DEBUG: (took: {(_search_end_sr - _search_start_sr).total_seconds():.6f}s) execute SEARCH_RESTORE END")

        else:
            OT_BackupManager.ShowReport_static(["Specify a Backup Path"] , "Backup Path missing", 'ERROR')
        return {'FINISHED'}
    
