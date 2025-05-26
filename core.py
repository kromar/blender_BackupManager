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
import os, blf, gpu # Import blf and gpu for custom drawing
import shutil
import fnmatch # For pattern matching in ignore list
import re # Moved from create_ignore_pattern
from datetime import datetime # Added for debug timestamps
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty, FloatProperty, IntProperty
from . import preferences


def prefs():
    """
    Directly retrieves the addon's preferences.
    Assumes bpy.context and addon preferences are always accessible.
    """
    user_preferences = bpy.context.preferences
    return user_preferences.addons[__package__].preferences

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

class OT_ShowFinalReport(bpy.types.Operator):
    """Operator to display a popup message. Used by timers for deferred reports."""
    bl_idname = "bm.show_final_report"
    bl_label = "Show Operation Report"
    bl_options = {'INTERNAL'} # This operator is not meant to be called directly by the user from UI search

    # Static class variables to hold the report data
    _title: str = "Report"
    _icon: str = "INFO"
    _lines: list = []
    _timer = None # Timer for the modal part

    @classmethod
    def set_report_data(cls, lines, title, icon):
        """Sets the data to be displayed by the popup."""
        cls._lines = lines
        cls._title = title
        cls._icon = icon
        if prefs().debug:
            print(f"DEBUG: OT_ShowFinalReport.set_report_data: Title='{cls._title}', Icon='{cls._icon}', Lines={cls._lines}")

    def invoke(self, context, event): # event is not used here but is part of the signature
        """Invokes the operator, sets up a modal timer to display the popup."""
        if prefs().debug:
            print(f"DEBUG: OT_ShowFinalReport.invoke: Setting up modal handler. Title='{OT_ShowFinalReport._title}'")
        context.window_manager.modal_handler_add(self)
        self._timer = context.window_manager.event_timer_add(0.0, window=context.window) # Very short delay
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'TIMER':
            if self._timer: # Ensure timer is removed before finishing
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None

            if prefs().debug:
                print(f"DEBUG: OT_ShowFinalReport.modal (TIMER): Displaying popup. Title='{OT_ShowFinalReport._title}'")

            def draw_for_popup(self_menu, context_inner):
                for line in OT_ShowFinalReport._lines:
                    self_menu.layout.label(text=line)
            
            context.window_manager.popup_menu(draw_for_popup, title=OT_ShowFinalReport._title, icon=OT_ShowFinalReport._icon)
            return {'FINISHED'}

        return {'PASS_THROUGH'} # Allow other events if any, though we expect to finish on first timer

    def cancel(self, context):
        """Ensures timer is cleaned up if the operator is cancelled externally (e.g., during unregister)."""
        # Use the robust prefs() function from core.py
        _debug_active = False # Default to False for safety during cancel
        try:
            prefs_instance_for_cancel = prefs()
            if prefs_instance_for_cancel:
                _debug_active = prefs_instance_for_cancel.debug
        except Exception:
            pass # Ignore errors getting prefs during cancel, prioritize cleanup

        if _debug_active:
            print(f"DEBUG: OT_ShowFinalReport.cancel() EXIT.")
        # Blender expects cancel() to return None

class OT_BackupManagerWindow(Operator):
    bl_idname = "bm.open_backup_manager_window"
    bl_label = "Backup Manager"
    bl_options = {'REGISTER'} # No UNDO needed for a UI window
    _timer = None # For periodic UI updates (e.g., progress, path details)


    def _update_window_tabs(self, context):
        """Ensures BM_Preferences.tabs is updated when this window's tabs change, triggering searches."""
        try:
            prefs_instance = prefs()
            if prefs_instance.tabs != self.tabs:
                prefs_instance.tabs = self.tabs # This will call BM_Preferences.update_version_list
        except Exception as e:
            # During script reload, prefs() might fail or self might be in an inconsistent state.
            # It's hard to safely use self.debug here.
            print(f"ERROR: Backup Manager: Error in OT_BackupManagerWindow._update_window_tabs (likely during script reload): {e}")
            # Avoid further operations if prefs are not accessible or an error occurred.
            
    tabs: EnumProperty(
        name="Operation Mode",
        items=[("BACKUP", "Backup", "Switch to Backup mode"),
               ("RESTORE", "Restore", "Switch to Restore mode")],
        default="BACKUP",
        update=_update_window_tabs
    )

    def _draw_path_age(self, layout, path_to_check):
        """Helper to draw cached path age."""
        prefs_instance = prefs() # Get prefs for debug flag
        if not path_to_check or not os.path.isdir(path_to_check): # Basic check before cache lookup
            layout.label(text="Last change: Path N/A")
            return
        display_text = preferences.BM_Preferences._age_cache.get(path_to_check)
        if display_text is None:
            display_text = "Last change: Calculating..."
            if prefs_instance.debug:
                print(f"DEBUG: OT_BackupManagerWindow._draw_path_age: No cache for '{path_to_check}', displaying 'Calculating...'")
        elif prefs_instance.debug:
            print(f"DEBUG: OT_BackupManagerWindow._draw_path_age: Using cached value for '{path_to_check}': {display_text}")
        layout.label(text=display_text)

    def _draw_path_size(self, layout, path_to_check):
        """Helper to draw cached path size."""
        prefs_instance = prefs() # Get prefs for debug flag
        if not path_to_check or not os.path.isdir(path_to_check): # Basic check
            layout.label(text="Size: Path N/A")
            return
        display_text = preferences.BM_Preferences._size_cache.get(path_to_check)
        if display_text is None:
            display_text = "Size: Calculating..."
            if prefs_instance.debug:
                print(f"DEBUG: OT_BackupManagerWindow._draw_path_size: No cache for '{path_to_check}', displaying 'Calculating...'")
        elif prefs_instance.debug:
            print(f"DEBUG: OT_BackupManagerWindow._draw_path_size: Using cached value for '{path_to_check}': {display_text}")
        layout.label(text=display_text)

    def _draw_selection_toggles(self, layout_box, mode, prefs_instance):
        """Replicates BM_Preferences.draw_selection for the new window."""
        prefix = "backup_" if mode == "BACKUP" else "restore_"
        
        row = layout_box.row(align=True)
        col1 = row.column() 
        col1.prop(prefs_instance, f'{prefix}addons') 
        col1.prop(prefs_instance, f'{prefix}extensions') 
        col1.prop(prefs_instance, f'{prefix}presets')  
        col1.prop(prefs_instance, f'{prefix}datafile') 

        col2 = row.column()  
        col2.prop(prefs_instance, f'{prefix}startup_blend') 
        col2.prop(prefs_instance, f'{prefix}userpref_blend') 
        col2.prop(prefs_instance, f'{prefix}workspaces_blend') 
        
        col3 = row.column()  
        col3.prop(prefs_instance, f'{prefix}cache') 
        col3.prop(prefs_instance, f'{prefix}bookmarks') 
        col3.prop(prefs_instance, f'{prefix}recentfiles')

    def _draw_backup_tab(self, layout, context, prefs_instance):
        """Draws the Backup tab content."""
        row_main  = layout.row(align=True) # Main row for From/To/Actions
        
        box_from = row_main.box() 
        col_from = box_from.column()

        if not prefs_instance.advanced_mode:
            path_from_val = prefs_instance.blender_user_path
            col_from.label(text = "Backup From: " + str(prefs_instance.active_blender_version), icon='COLORSET_03_VEC')   
            col_from.label(text = path_from_val)      
            if prefs_instance.show_path_details:
                self._draw_path_age(col_from, path_from_val) 
                self._draw_path_size(col_from, path_from_val)

            box_to = row_main.box() # Add box_to to row_main
            col_to = box_to.column()
            path_to_val =  os.path.join(prefs_instance.backup_path, str(prefs_instance.active_blender_version)) if prefs_instance.backup_path else "N/A"
            col_to.label(text = "Backup To: " + str(prefs_instance.active_blender_version), icon='COLORSET_04_VEC')
            col_to.label(text = path_to_val)          
            if prefs_instance.show_path_details:
                self._draw_path_age(col_to, path_to_val)    
                self._draw_path_size(col_to, path_to_val)
        else: # Advanced mode
            # --- Backup From Box ---
            source_version_selected = prefs_instance.backup_versions # This is the string value of the selected item
            path_from_val = os.path.join(os.path.dirname(prefs_instance.blender_user_path), source_version_selected) if prefs_instance.blender_user_path and source_version_selected else "N/A"
            
            col_from.label(text="Backup From: " + source_version_selected, icon='COLORSET_03_VEC')
            col_from.label(text=path_from_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val)
            if prefs_instance.show_path_details: self._draw_path_size(col_from, path_from_val)
            col_from.prop(prefs_instance, 'backup_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

            # --- Backup To Box ---
            box_to = row_main.box() # Add box_to to row_main
            col_to = box_to.column()
            if prefs_instance.custom_version_toggle:
                target_version_displayed = prefs_instance.custom_version
                path_to_val = os.path.join(prefs_instance.backup_path, target_version_displayed) if prefs_instance.backup_path and target_version_displayed else "N/A"
                col_to.label(text="Backup To: " + target_version_displayed, icon='COLORSET_04_VEC')
                col_to.label(text=path_to_val)
                if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val)
                if prefs_instance.show_path_details: self._draw_path_size(col_to, path_to_val)
                col_to.prop(prefs_instance, 'custom_version', text='Version')
            else: # Not custom_version_toggle, use restore_versions for dropdown
                target_version_displayed = prefs_instance.restore_versions # This is the string value of the selected item
                path_to_val = os.path.join(prefs_instance.backup_path, target_version_displayed) if prefs_instance.backup_path and target_version_displayed else "N/A"
                col_to.label(text="Backup To: " + target_version_displayed, icon='COLORSET_04_VEC')
                col_to.label(text=path_to_val)
                if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val)
                if prefs_instance.show_path_details: self._draw_path_size(col_to, path_to_val)
                col_to.prop(prefs_instance, 'restore_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

        # --- Actions Column ---
        col_actions = row_main.column() # For main action buttons and global toggles
        col_actions.scale_x = 0.9 # Slightly narrower for this column
        col_actions.operator("bm.run_backup_manager", text="Backup Selected", icon='COLORSET_03_VEC').button_input = 'BACKUP' 
        if prefs_instance.advanced_mode:
            col_actions.operator("bm.run_backup_manager", text="Backup All", icon='COLORSET_03_VEC').button_input = 'BATCH_BACKUP' 
        col_actions.separator(factor=1.0)
        col_actions.prop(prefs_instance, 'dry_run')  
        col_actions.prop(prefs_instance, 'clean_path')  
        col_actions.prop(prefs_instance, 'advanced_mode') 
        if prefs_instance.advanced_mode:
            col_actions.prop(prefs_instance, 'custom_version_toggle')  
            col_actions.prop(prefs_instance, 'expand_version_selection')    
            col_actions.separator(factor=1.0)
            col_actions.operator("bm.run_backup_manager", text="Delete Backup", icon='COLORSET_01_VEC').button_input = 'DELETE_BACKUP'

        # --- Selection Toggles (Advanced Mode Only) ---
        # Drawn *after* the main row is complete, and only if in advanced mode.
        if prefs_instance.advanced_mode:
            selection_toggles_box = layout.box() # Create a new box at the 'layout' (tab_content_box) level
            self._draw_selection_toggles(selection_toggles_box, "BACKUP", prefs_instance)

    def _draw_restore_tab(self, layout, context, prefs_instance):
        """Draws the Restore tab content."""
        row_main  = layout.row(align=True) # Main row for From/To/Actions

        box_from = row_main.box()
        col_from = box_from.column()

        if not prefs_instance.advanced_mode:
            path_from_val = os.path.join(prefs_instance.backup_path, str(prefs_instance.active_blender_version)) if prefs_instance.backup_path else "N/A"
            col_from.label(text = "Restore From: " + str(prefs_instance.active_blender_version), icon='COLORSET_04_VEC')   
            col_from.label(text = path_from_val)                  
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            
            box_to = row_main.box() # Add box_to to row_main
            col_to = box_to.column()
            path_to_val =  prefs_instance.blender_user_path
            col_to.label(text = "Restore To: " + str(prefs_instance.active_blender_version), icon='COLORSET_03_VEC')   
            col_to.label(text = path_to_val)              
            if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
        else: # Advanced Mode
            source_ver = prefs_instance.restore_versions
            path_from_val = os.path.join(prefs_instance.backup_path, source_ver) if prefs_instance.backup_path and source_ver else "N/A"
            col_from.label(text="Restore From: " + source_ver, icon='COLORSET_04_VEC')
            col_from.label(text=path_from_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            col_from.prop(prefs_instance, 'restore_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

            box_to = row_main.box() # Add box_to to row_main
            col_to = box_to.column()
            target_ver = prefs_instance.backup_versions
            path_to_val = os.path.join(os.path.dirname(prefs_instance.blender_user_path), target_ver) if prefs_instance.blender_user_path and target_ver else "N/A"
            col_to.label(text="Restore To: " + target_ver, icon='COLORSET_03_VEC')
            col_to.label(text=path_to_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
            col_to.prop(prefs_instance, 'backup_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

        # --- Actions Column ---
        col_actions = row_main.column()
        col_actions.scale_x = 0.9
        col_actions.operator("bm.run_backup_manager", text="Restore Selected", icon='COLORSET_04_VEC').button_input = 'RESTORE'
        if prefs_instance.advanced_mode:
            col_actions.operator("bm.run_backup_manager", text="Restore All", icon='COLORSET_04_VEC').button_input = 'BATCH_RESTORE'
        col_actions.separator(factor=1.0)
        col_actions.prop(prefs_instance, 'dry_run')      
        col_actions.prop(prefs_instance, 'clean_path')   
        col_actions.prop(prefs_instance, 'advanced_mode')  
        if prefs_instance.advanced_mode:
            col_actions.prop(prefs_instance, 'expand_version_selection')

        # --- Selection Toggles (Advanced Mode Only) ---
        # Drawn *after* the main row is complete, and only if in advanced mode.
        if prefs_instance.advanced_mode:
            selection_toggles_box = layout.box() # Create a new box at the 'layout' (tab_content_box) level
            self._draw_selection_toggles(selection_toggles_box, "RESTORE", prefs_instance)

    def draw(self, context): # Standard signature for invoke_props_dialog
        layout = self.layout # Provided by invoke_props_dialog
        prefs_instance = None

        try:
            prefs_instance = prefs() # Get current addon preferences

            _debug_draw = prefs_instance.debug if prefs_instance else False
            _start_time_draw_obj = None # Use a different name to avoid conflict if prefs_instance is None initially

            if _debug_draw:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                # Adjust for 0-1 scale for debug display
                progress_val_str = f"{prefs_instance.operation_progress_value:.1f}%" if prefs_instance.show_operation_progress else "N/A (hidden)"
                op_message = prefs_instance.operation_progress_message if prefs_instance.show_operation_progress else "N/A (hidden)"
                print(f"DEBUG: [{timestamp}] OT_BackupManagerWindow.draw() CALLED. Progress: {progress_val_str}, Msg: '{op_message}', show_op_progress: {prefs_instance.show_operation_progress}, Tabs: {self.tabs}")
                _start_time_draw_obj = datetime.now()

            # --- Top section for global settings ---
            # Ensure prefs_instance is valid before using it for drawing
            col_top = layout.column(align=True)
            col_top.prop(prefs_instance, 'backup_path')            
            col_top.prop(prefs_instance, 'ignore_files')
            col_top.prop(prefs_instance, 'debug')
            col_top.prop(prefs_instance, 'show_path_details')

            # --- Progress UI ---
            if prefs_instance.show_operation_progress:
                op_status_box = layout.box()
                op_status_col = op_status_box.column(align=True)

                # Display the progress message
                if prefs_instance.operation_progress_message:
                    op_status_col.label(text=prefs_instance.operation_progress_message)
                
                # Create a new row for the progress bar and abort button
                progress_row = op_status_col.row(align=True)

                # Display the progress value as a slider (without its own text label)
                # operation_progress_value is a 0.0-100.0 factor. The text="" hides the label to its left.
                progress_row.prop(prefs_instance, "operation_progress_value", slider=True, text="")
                                
                # Abort button
                progress_row.operator("bm.abort_operation", text="", icon='CANCEL') # Text removed for compactness

            # --- Tabs for Backup/Restore ---
            layout.prop(self, "tabs", expand=True) # Use the operator's own tabs property
            tab_content_box = layout.box() # Box for the content of the selected tab
            if self.tabs == "BACKUP":
                self._draw_backup_tab(tab_content_box, context, prefs_instance)
            elif self.tabs == "RESTORE":
                self._draw_restore_tab(tab_content_box, context, prefs_instance)
            
            if _debug_draw and _start_time_draw_obj:
                _end_time_draw_obj = datetime.now()
                print(f"DEBUG: (took: {(_end_time_draw_obj - _start_time_draw_obj).total_seconds():.6f}s) OT_BackupManagerWindow.draw() END")
                print("-" * 70) # Add a separator line

        except Exception as e:
            print(f"ERROR: Backup Manager: Error in OT_BackupManagerWindow.draw() (prefs_instance might be None): {e}")
            layout.label(text=f"Error drawing Backup Manager window: {e}")


    def execute(self, context):
        prefs_instance = None
        try:
            prefs_instance = prefs()
        except Exception as e:
            # Log error and attempt to cancel gracefully
            print(f"ERROR: OT_BackupManagerWindow.execute() - Failed to get preferences: {e}. Self: {self}")
            self.cancel(context) # Ensure timer cleanup
            return {'CANCELLED'} # Indicate failure

        if prefs_instance.debug:
            print(f"DEBUG: OT_BackupManagerWindow.execute() ENTER. Context: {context}, Self: {self}")
        
        # Ensure timer is cleaned up if execute is called (e.g. by an "OK" button if one existed)
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            if prefs_instance.debug: print(f"DEBUG: OT_BackupManagerWindow.execute() - Timer removed.")
        
        # Check prefs_instance again in case it was None from the try-except block
        # but cancel didn't lead to an immediate return (though it should).
        # This is more for defensive logging.
        if prefs_instance and prefs_instance.debug:
            print(f"DEBUG: OT_BackupManagerWindow.execute() EXIT. Returning {{'FINISHED'}}. Self: {self}")
        return {'FINISHED'} # Signal successful completion.

    def invoke(self, context, event):
        prefs_instance = prefs()

        # Critical check: If preferences are not available, cancel immediately.
        if not prefs_instance:
            print(f"ERROR: OT_BackupManagerWindow.invoke() - Failed to get addon preferences. Cannot initialize window. Self: {self}")
            return {'CANCELLED'}

        # Now it's safe to use prefs_instance
        _debug_active = prefs_instance.debug # Store debug state for local use

        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.invoke() CALLED. Initializing tabs from prefs: {prefs_instance.tabs}")
        
        self.tabs = prefs_instance.tabs # Initialize window tabs from preferences

        # Explicitly trigger the version list update (which includes the SEARCH operator call)
        # and subsequent path detail scan (if show_path_details is true).
        # This ensures that the necessary scans are performed on first window open,
        # as the update chain via self.tabs -> _update_window_tabs -> prefs.tabs
        # might not fire if the tab values are already synchronized.
        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.invoke() - Explicitly calling prefs_instance.update_version_list(context) for initial scan.")
        prefs_instance.update_version_list(context)
        # The call to update_version_list will handle path details if prefs_instance.show_path_details is true,
        # so the separate path detail scan previously here is no longer needed.

        # Always add the timer for the modal UI window.
        # The modal() method will manage its activity based on show_operation_progress.
        if self._timer is None:
            self._timer = context.window_manager.event_timer_add(0.0) # Make timer global, not window-bound
            if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.invoke() - UI Update Timer ADDED (global): {self._timer}")

        context.window_manager.modal_handler_add(self)

        # Use invoke_props_dialog to open the window.
        # The operator's draw() method will be called by Blender to populate the dialog.
        result = context.window_manager.invoke_props_dialog(self, width=700)
        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.invoke() EXIT. invoke_props_dialog returned: {result}. Self: {self}")
        # If invoke_props_dialog returns {'RUNNING_MODAL'}, our modal() method will also run.

        return {'RUNNING_MODAL'} # Crucial for the modal() method to keep running

    def modal(self, context, event):
        prefs_instance = prefs() # Get fresh prefs
        _debug_active = prefs_instance.debug if prefs_instance else False

        if not context.window:
            if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.modal() - context.window is None, cancelling.")
            return self.cancel(context)

        if not prefs_instance: # Should not happen if invoke checks, but safeguard
            print(f"ERROR: OT_BackupManagerWindow.modal() - Failed to get preferences, cancelling.")
            return self.cancel(context)

        if event.type == 'ESC': # Allow ESC to close the window
             if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.modal() - ESC detected, cancelling.")
             self.cancel(context) # Perform cleanup
             return {'CANCELLED'} # Modal operator itself returns CANCELLED
        
        if event.type == 'TIMER':
            if _debug_active:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"DEBUG: [{timestamp}] OT_BackupManagerWindow.modal() (TIMER) event.")
                print(f"DEBUG: ... self._timer: {self._timer}, show_op_progress: {prefs_instance.show_operation_progress}, current_progress_val: {prefs_instance.operation_progress_value:.1f}%")
                print(f"DEBUG: ... Invoking context.area.type: {context.area.type if context.area else 'N/A'}")

            # For invoke_props_dialog, the dialog is its own window. The modal() method's 'context'
            # is from the invoking window. We must ensure the dialog window itself is tagged for redraw.
            # Iterating all areas of all windows is the most robust way to catch the dialog.
            for wm_window in context.window_manager.windows:
                for area in wm_window.screen.areas:
                    area.tag_redraw() # Tag each area individually
            if _debug_active: # Log after the loop
                print(f"DEBUG: ... All areas in all windows tagged for redraw.")

            if prefs_instance.show_operation_progress:
                # The tag_redraw() loop above should be sufficient.
                # Aggressive redraw_timer can cause flickering.

                # Operation is in progress, timer should continue.
                # Debug message for this state is already part of the initial timer log block
                # Safeguard: If timer was somehow removed while an operation is supposed to be in progress, re-add it.
                if self._timer is None:
                    self._timer = context.window_manager.event_timer_add(0.0) # Make timer global
                    if _debug_active: print(f"DEBUG: ... UI Update Timer RE-ADDED (global) for active operation.")

            else: # Operation not in progress or finished
                if self._timer: # If timer is still around
                    # And no operation is in progress, we can remove this UI update timer.
                    context.window_manager.event_timer_remove(self._timer)
                    self._timer = None
                    if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.modal() (TIMER) - Operation not in progress, UI timer removed.")
                    # The redraw tagged above (and potentially redraw_timer if it ran one last time) will handle displaying the final UI state.
        
        # If we were handling button clicks for a fully custom UI, it would be here.
        # For now, we only care about the timer and ESC.
        if event.type in {'RIGHTMOUSE', 'LEFTMOUSE'}: # Example event handling
            pass # Handle mouse clicks if drawing custom buttons

        return {'PASS_THROUGH'}

    def cancel(self, context):
        # Use the robust prefs() function from core.py
        _debug_active = False # Default to False for safety during cancel
        prefs_instance_for_cancel = None
        try:
            prefs_instance_for_cancel = prefs()
            if prefs_instance_for_cancel:
                _debug_active = prefs_instance_for_cancel.debug
        except Exception:
            pass # Ignore errors getting prefs during cancel, prioritize cleanup
        if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() ENTER. Context: {context}, Self: {self}")
        
        if self._timer:
            if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Timer found, removing. Timer: {self._timer}")
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception as e: # Timer might already be gone
                if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Error removing timer (might be already gone): {e}")
            self._timer = None

        # If an operation (from OT_BackupManager) is in progress, request it to abort.
        try:
            # prefs_instance_for_cancel is already the robust preferences object
            if prefs_instance_for_cancel and prefs_instance_for_cancel.show_operation_progress: # Check if OT_BackupManager is likely active
                if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Operation in progress, setting abort_operation_requested.")
                prefs_instance_for_cancel.abort_operation_requested = True
        except Exception as e:
            if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Error accessing prefs to request operation abort: {e}")
            
        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.cancel() EXIT. Returning {{'CANCELLED'}}. Self: {self}")
        # Blender expects cancel() to return None

                
class OT_BackupManager(Operator):
    ''' run backup & restore '''
    bl_idname = "bm.run_backup_manager"
    bl_label = "Blender Versions"     
    # bl_options = {'REGISTER'} # Removed, not typically needed for modal operators unless specific registration behavior is desired.
    
    button_input: StringProperty()
    
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
    
    def cancel(self, context):
        """Ensures timer and progress UI are cleaned up if the operator is cancelled externally."""
        # Use the robust prefs() function from core.py
        _debug_active = False # Default to False for safety during cancel
        prefs_instance_for_cancel = None
        try:
            prefs_instance_for_cancel = prefs()
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
    def _deferred_show_report_static(message_lines, title, icon):
        if prefs().debug: 
            print(f"DEBUG: _deferred_show_report_static: Preparing to invoke bm.show_final_report. Title='{title}'")
        OT_ShowFinalReport.set_report_data(lines=message_lines, title=title, icon=icon)
        bpy.ops.bm.show_final_report('INVOKE_SCREEN')
        return None # Stop the timer

    # Keep the instance method for direct calls if needed, though static is preferred for deferred.
    def ShowReport(self, message = [], title = "Message Box", icon = 'INFO'):
        OT_BackupManager.ShowReport_static(message, title, icon)
    
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

    def _process_next_batch_item_or_finish(self, context):
        """
        Sets up the next item in a batch operation for modal processing,
        or finalizes the batch if all items are done.
        Returns {'RUNNING_MODAL'} if a new item is started modally,
        {'FINISHED'} if batch is complete or no items to process initially.
        """
        pref_instance = prefs() # Get fresh preferences

        if self.current_batch_item_index < self.total_batch_items:
            source_path, target_path, op_type, version_name = self.batch_operations_list[self.current_batch_item_index]
            self.current_source_path = source_path
            self.current_target_path = target_path
            self.current_operation_type = op_type

            item_name_for_log = version_name # Use the version name for logging

            if pref_instance.clean_path and os.path.exists(self.current_target_path) and self.current_operation_type == 'BACKUP':
                if pref_instance.debug: print(f"DEBUG: Batch: Attempting to clean path for {item_name_for_log}: {self.current_target_path}")
                try:
                    if not pref_instance.dry_run: shutil.rmtree(self.current_target_path)
                    cleaned_msg = f"Cleaned path for {item_name_for_log}: {self.current_target_path}"
                    if pref_instance.debug or pref_instance.dry_run: print(cleaned_msg)
                    self.batch_report_lines.append(f"INFO: {cleaned_msg}")
                except OSError as e:
                    fail_clean_msg = f"Failed to clean path for {item_name_for_log} ({self.current_target_path}): {e}"
                    if pref_instance.debug: print(f"ERROR: {fail_clean_msg}")
                    self.batch_report_lines.append(f"WARNING: {fail_clean_msg}")

            if not self._prepare_file_list(): # Populates self.files_to_process, self.total_files
                err_msg = f"Batch item {self.current_batch_item_index + 1}/{self.total_batch_items} ({op_type} {item_name_for_log}): Error preparing file list. Skipping."
                self.report({'WARNING'}, err_msg)
                self.batch_report_lines.append(f"WARNING: {err_msg}")
                pref_instance.operation_progress_message = err_msg
                self.current_batch_item_index += 1
                return self._process_next_batch_item_or_finish(context) # Try next

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
                 report_title = f"Batch {overall_op_type} Report"

            final_report_lines = [final_batch_message] + self.batch_report_lines[:]
            bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static(
                final_report_lines, report_title, 'INFO'
            ), first_interval=0.01)

            pref_instance.show_operation_progress = False
            pref_instance.operation_progress_message = final_batch_message
            pref_instance.operation_progress_value = 100.0
            pref_instance.abort_operation_requested = False # Reset abort flag
            
            if self._timer: # Clean up timer if it was from the last item
                context.window_manager.event_timer_remove(self._timer)
                self._timer = None
                if pref_instance.debug: print(f"DEBUG: Batch: Final timer removed.")
            return {'FINISHED'}

    def modal(self, context, event):
        pref_instance = prefs() # Get fresh preferences
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
                bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static([cancel_message], "Operation Cancelled", "WARNING"), first_interval=0.01)
                
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
                    report_message_lines = [
                        f"{self.current_operation_type} {completion_status_item.lower()}.",
                        f"{display_processed_count}/{self.total_files} files processed."
                    ]
                    if self.current_source_path: report_message_lines.append(f"Source: {self.current_source_path}")
                    if self.current_target_path: report_message_lines.append(f"Target: {self.current_target_path}")
                    if pref_instance.dry_run and self.total_files > 0: 
                        report_message_lines.append("(Dry Run - No files were actually copied/deleted)")

                    report_icon = 'INFO' 
                    if self.current_operation_type == 'BACKUP': report_icon = 'COLORSET_03_VEC'
                    elif self.current_operation_type == 'RESTORE': report_icon = 'COLORSET_04_VEC'
                    
                    bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static(
                        report_message_lines, f"{self.current_operation_type} Report", report_icon
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

                if not prefs().dry_run:
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

        return {'PASS_THROUGH'} # Allow other events to be processed

    def execute(self, context): 
        pref_instance = prefs() # Get fresh preferences
        pref_backup_versions = preferences.BM_Preferences.backup_version_list
        pref_restore_versions = preferences.BM_Preferences.restore_version_list

        if prefs().debug:
            print("\n\nbutton_input: ", self.button_input)                    
        
        if prefs().backup_path:
            self.current_operation_type = "" # Reset for single ops
            self.is_batch_operation = False # Reset for single ops

            if self.button_input in {'BACKUP', 'RESTORE'}:
                self.current_operation_type = self.button_input
                if not pref_instance.advanced_mode:            
                    if self.button_input == 'BACKUP':
                        self.current_source_path = pref_instance.blender_user_path
                        self.current_target_path = os.path.join(pref_instance.backup_path, str(pref_instance.active_blender_version))
                    else: # RESTORE
                        self.current_source_path = os.path.join(pref_instance.backup_path, str(pref_instance.active_blender_version))
                        self.current_target_path = pref_instance.blender_user_path
                else:    
                    if self.button_input == 'BACKUP':
                        self.current_source_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  pref_instance.backup_versions)
                        if pref_instance.custom_version_toggle:
                            self.current_target_path = os.path.join(pref_instance.backup_path, str(pref_instance.custom_version))
                        else: 
                            # Corrected: If not custom, target for backup should be based on source version name
                            self.current_target_path = os.path.join(pref_instance.backup_path, pref_instance.backup_versions)

                    else: # RESTORE
                        self.current_source_path = os.path.join(pref_instance.backup_path, pref_instance.restore_versions)
                        self.current_target_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  pref_instance.backup_versions)

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
                    op_type_for_report = self.current_operation_type if self.current_operation_type else "Operation"
                    icon_for_report = 'INFO' # Default
                    if self.current_operation_type == 'BACKUP': icon_for_report = 'COLORSET_03_VEC'
                    elif self.current_operation_type == 'RESTORE': icon_for_report = 'COLORSET_04_VEC'
                    
                    # Capture values for the lambda to ensure they are correct at execution time
                    _msg_lines = report_message.split('\n')
                    _title = f"{op_type_for_report} Report"
                    _icon = icon_for_report

                    bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static(
                        _msg_lines, _title, _icon
                    ), first_interval=0.01)
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
                    version_name = version[0]
                    source_path = os.path.join(os.path.dirname(pref_instance.blender_user_path), version_name)
                    target_path = os.path.join(pref_instance.backup_path, version_name)
                    self.batch_operations_list.append((source_path, target_path, 'BACKUP', version_name))
                self.total_batch_items = len(self.batch_operations_list)
                self.current_batch_item_index = 0
                if self.total_batch_items == 0:
                    self.report({'INFO'}, "No items found for batch backup.")
                    self.is_batch_operation = False # Reset
                    return {'FINISHED'}
                context.window_manager.modal_handler_add(self) # Add modal handler ONCE for the whole batch
                return self._process_next_batch_item_or_finish(context)

            elif self.button_input == 'BATCH_RESTORE':
                self.is_batch_operation = True
                self.batch_operations_list.clear()
                self.batch_report_lines.clear()
                for version in pref_restore_versions: # Iterate over the list from preferences
                    version_name = version[0]
                    source_path = os.path.join(pref_instance.backup_path, version_name)
                    target_path = os.path.join(os.path.dirname(pref_instance.blender_user_path),  version_name)
                    self.batch_operations_list.append((source_path, target_path, 'RESTORE', version_name))
                self.total_batch_items = len(self.batch_operations_list)
                self.current_batch_item_index = 0
                if self.total_batch_items == 0:
                    self.report({'INFO'}, "No items found for batch restore.")
                    self.is_batch_operation = False # Reset
                    return {'FINISHED'}
                context.window_manager.modal_handler_add(self) # Add modal handler ONCE for the whole batch
                return self._process_next_batch_item_or_finish(context)

            elif self.button_input == 'DELETE_BACKUP':
                if not pref_instance.advanced_mode:            
                    target_path = os.path.join(pref_instance.backup_path, str(pref_instance.active_blender_version)).replace("\\", "/")                    
                else:                                                 
                    if pref_instance.custom_version_toggle:
                        target_path = os.path.join(pref_instance.backup_path, str(pref_instance.custom_version))
                    else:                
                        target_path = os.path.join(pref_instance.backup_path, pref_instance.restore_versions)

                if os.path.exists(target_path):
                    try:
                        if not prefs().dry_run:
                            shutil.rmtree(target_path)
                        
                        action_verb = "Would delete" if prefs().dry_run else "Deleted"
                        report_msg_line1 = f"{action_verb} backup:"
                        report_msg_line2 = target_path
                        self.report({'INFO'}, f"{report_msg_line1} {report_msg_line2}")
                        bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static([report_msg_line1, report_msg_line2], "Delete Backup Report", 'COLORSET_01_VEC'), first_interval=0.01)
                        if pref_instance.debug or pref_instance.dry_run:
                             print(f"\n{action_verb} Backup: {target_path}")

                    except OSError as e:
                        action_verb = "Failed to (dry run) delete" if pref_instance.dry_run else "Failed to delete"
                        error_msg_line1 = f"{action_verb} {target_path}:"
                        error_msg_line2 = str(e)
                        self.report({'WARNING'}, f"{error_msg_line1} {error_msg_line2}")
                        OT_BackupManager.ShowReport_static(message=[error_msg_line1, error_msg_line2], title="Delete Backup Error", icon='WARNING')
                        if prefs().debug: # Keep print for debug
                            print(f"\n{action_verb} {target_path}: {e}")
                else:
                    not_found_msg = f"Not found, nothing to delete: {target_path}"
                    self.report({'INFO'}, not_found_msg)
                    bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static([f"Not found, nothing to delete:", target_path], "Delete Backup Report", 'INFO'), first_interval=0.01)
                    if pref_instance.debug: # Keep print for debug
                        print(f"\nBackup to delete not found: {target_path}")

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
            OT_BackupManager.ShowReport_static(["Specify a Backup Path"] , "Backup Path missing", 'ERROR')
        return {'FINISHED'}
    
