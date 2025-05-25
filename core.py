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
from bpy.props import StringProperty, EnumProperty # Added EnumProperty
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
        self._timer = context.window_manager.event_timer_add(0.001, window=context.window) # Very short delay
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
        prefs_instance_for_cancel = prefs()
        _debug_active = prefs_instance_for_cancel.debug

        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
                if _debug_active: print(f"DEBUG: OT_ShowFinalReport.cancel(): Timer removed.")
            except Exception as e:
                if _debug_active: print(f"DEBUG: OT_ShowFinalReport.cancel(): Error removing timer: {e}")
            self._timer = None
        if _debug_active:
            print(f"DEBUG: OT_ShowFinalReport.cancel() EXIT.")
        return None # Must return None

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

    def draw(self, context):
        layout = self.layout
        _start_time_draw = None
        prefs_instance = None

        try:
            prefs_instance = prefs() # Get current addon preferences

            if prefs_instance.debug:
                print("\n" + "-"*10 + " OT_BackupManagerWindow.draw() START " + "-"*10 + "\n") # Visual separator
                _start_time_draw = datetime.now()
                print(f"DEBUG: OT_BackupManagerWindow.draw() CALLED. Tabs: {self.tabs}")

            # --- Top section for global settings ---
            col_top = layout.column(align=True)
            col_top.prop(prefs_instance, 'backup_path')            
            col_top.prop(prefs_instance, 'ignore_files')
            col_top.prop(prefs_instance, 'debug')
            col_top.prop(prefs_instance, 'show_path_details')

            # --- Progress UI (reads from BM_Preferences) ---
            if prefs_instance.show_operation_progress:
                progress_outer_box = layout.box() # Use a separate box for progress
                progress_box = progress_outer_box.column(align=True)
                progress_box.label(text=prefs_instance.operation_progress_message)
                row_progress = progress_box.row(align=True)
                row_progress.prop(prefs_instance, "operation_progress_value", text="", slider=True)
                row_progress.operator("bm.abort_operation", text="", icon='CANCEL')

            # --- Tabs for Backup/Restore ---
            layout.prop(self, "tabs", expand=True) # Use the operator's own tabs property
            
            tab_content_box = layout.box() # Box for the content of the selected tab
            if self.tabs == "BACKUP":
                self._draw_backup_tab(tab_content_box, context, prefs_instance)
            elif self.tabs == "RESTORE":
                self._draw_restore_tab(tab_content_box, context, prefs_instance)
            
            if prefs_instance and prefs_instance.debug and _start_time_draw: # Check prefs_instance again
                _end_time_draw = datetime.now()
                print(f"DEBUG: (took: {(_end_time_draw - _start_time_draw).total_seconds():.6f}s) OT_BackupManagerWindow.draw() END" + "\n" + "-"*40 + "\n") # Visual separator

        except Exception as e:
            print(f"ERROR: Backup Manager: Error in OT_BackupManagerWindow.draw() (likely during script reload): {e}")
            layout.label(text="Error drawing Backup Manager window. Please re-open if this persists after reload.")
            # Avoid further drawing if prefs_instance might be invalid or other errors occurred.


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
        
        # Ensure cleanup is performed, similar to cancel.
        self.cancel(context) # This will handle timer removal.
        
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

        # Trigger initial scan for path details if shown
        if prefs_instance.show_path_details:
            paths = preferences.get_paths_for_details(prefs_instance)
            prefs_instance._update_path_details_for_paths(paths) # Update cache, redraw will happen via timer if needed

        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.invoke() - Calling window_manager.invoke_props_dialog(self). Self: {self}")
        
        # This will make Blender open a dialog for this operator.
        # The operator's draw() method will be called to populate it.
        result = context.window_manager.invoke_props_dialog(self, width=700) # Specify a width for the dialog
        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.invoke() EXIT. invoke_props_dialog returned: {result}. Self: {self}")
        return result

    def modal(self, context, event):
        # This method is unlikely to be called if modal_handler_add is removed from invoke().
        # Kept as a fallback; invoke_props_dialog should handle most events for the dialog.
        # The primary role of a custom modal method here was for the timer, which has been removed.

        # Safety check for context.window, though invoke_props_dialog should manage this.
        # Initial critical check: if the window context is gone, always try to cancel.
        if not context.window:
            # Try to log if debug was active, but prioritize cancellation.
            _debug_active_check = False
            try: _debug_active_check = bpy.context.preferences.addons[__package__].preferences.debug
            except Exception: pass # Ignore if prefs can't be read here
            if _debug_active_check:
                 print(f"DEBUG: OT_BackupManagerWindow.modal() - context.window is None, calling cancel. Self: {self}")
            return self.cancel(context)

        prefs_instance = None
        try:
            prefs_instance = prefs() # Attempt to get preferences
        except Exception as e:
            # If prefs() fails during a modal event, log and cancel to prevent a hard crash.
            print(f"ERROR: OT_BackupManagerWindow.modal() - Failed to get preferences: {e}. Calling cancel. Self: {self}")
            return self.cancel(context)

        # If prefs_instance is available and debug is on
        if prefs_instance and prefs_instance.debug:
            # The 'TIMER' event type check is no longer relevant as the timer was removed.
            # Log other event types if this modal method is somehow still reached.
            # However, with modal_handler_add removed, this method should not be directly
            # invoked by Blender's main event loop for this operator instance.
                 print(f"DEBUG: OT_BackupManagerWindow.modal() ENTER. Event: {event.type}, Self: {self}")

        if event.type == 'ESC': # Allow ESC to close the window
             if prefs_instance.debug: print(f"DEBUG: OT_BackupManagerWindow.modal() - ESC detected, calling cancel. Self: {self}")
             return self.cancel(context)

        # If the Blender window itself is closed, cancel the operator
        # This check is now at the top of the modal method.
        
        # REMOVED: Timer event handling logic, as the timer for OT_BackupManagerWindow was removed.
        # The progress bar display relies on invoke_props_dialog redrawing the window,
        # which will pick up changes in preferences made by the OT_BackupManager operator.
        # Allow other UI interactions within this modal "window"
        # This is important so buttons and properties in our draw() method work.
        # For events not handled above (ESC, window close, TIMER), pass them through.
        # This allows invoke_props_dialog to handle its own UI elements.
        if prefs_instance.debug:
            if event.type != 'TIMER': # Avoid spamming for timer
                # Ensure prefs_instance is valid before accessing debug
                if prefs_instance and prefs_instance.debug: print(f"DEBUG: OT_BackupManagerWindow.modal() EXIT. Returning {{'PASS_THROUGH'}}. Event: {event.type}, Self: {self}")
        return {'PASS_THROUGH'}

    def cancel(self, context):
        # Use the robust prefs() function from core.py
        prefs_instance_for_cancel = prefs()
        _debug_active = prefs_instance_for_cancel.debug
        if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() ENTER. Context: {context}, Self: {self}")
        
        # REMOVED: Timer removal logic as self._timer is no longer used by OT_BackupManagerWindow
        # if self._timer:
        #     if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Timer found, removing. Timer: {self._timer}, Self: {self}")
        #     try:
        #         context.window_manager.event_timer_remove(self._timer)
        #         self._timer = None
        #         if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Timer removed successfully. Self: {self}")
        #     except Exception as e:
        #         if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - ERROR removing timer: {e}. Self: {self}")
        #         self._timer = None # Ensure it's None anyway
        # elif _debug_active:
        #     print(f"DEBUG: OT_BackupManagerWindow.cancel() - No timer to remove. Self: {self}")

        # If an operation (from OT_BackupManager) is in progress, request it to abort.
        try:
            # prefs_instance_for_cancel is already the robust preferences object
            if prefs_instance_for_cancel.show_operation_progress: # Check if OT_BackupManager is likely active
                if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Operation in progress, setting abort_operation_requested.")
                prefs_instance_for_cancel.abort_operation_requested = True
        except Exception as e:
            if _debug_active: print(f"DEBUG: OT_BackupManagerWindow.cancel() - Error accessing prefs to request operation abort: {e}")
            
        if _debug_active:
            print(f"DEBUG: OT_BackupManagerWindow.cancel() EXIT. Returning None. Self: {self}")
        return None # Cancel method should return None when called by Blender's C API for cleanup

    # def execute(self, context): # Not typically used for a modal UI operator like this
    #     self.report({'INFO'}, "Backup Manager window opened (this is execute, should be invoke)")
    #     return {'FINISHED'}

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
        prefs_instance_for_cancel = prefs()
        _debug_active = prefs_instance_for_cancel.debug

        if self._timer:
            try:
                context.window_manager.event_timer_remove(self._timer)
                if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Timer removed.")
            except Exception as e:
                if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Error removing timer: {e}")
            self._timer = None

        # Reset UI state related to this operator's modal operation
        try:
            # prefs_instance_for_cancel is already the robust preferences object
            prefs_instance_for_cancel.show_operation_progress = False
            prefs_instance_for_cancel.abort_operation_requested = False # Reset this flag too
            if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): show_operation_progress and abort_operation_requested reset.")
        except Exception as e:
            if _debug_active: print(f"DEBUG: OT_BackupManager.cancel(): Error resetting preference flags: {e}")

        if _debug_active: print(f"DEBUG: OT_BackupManager.cancel() EXIT.")
        return None # Must return None


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
                # Log for immediate feedback in console/status bar
                self.report({'WARNING'}, cancel_message)
                
                # Defer the popup display
                bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static([cancel_message], "Operation Cancelled", "WARNING"), first_interval=0.01)
                
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
                # Check if current_operation_type is set before using it for icon
                if hasattr(self, 'current_operation_type') and self.current_operation_type:
                    if self.current_operation_type == 'BACKUP':
                        report_icon = 'COLORSET_03_VEC'
                    elif self.current_operation_type == 'RESTORE':
                        report_icon = 'COLORSET_04_VEC'
                
                # Capture the value of current_operation_type before creating the lambda
                operation_type_for_report = self.current_operation_type
                # Defer the completion report popup as well for consistency
                bpy.app.timers.register(lambda: OT_BackupManager._deferred_show_report_static(report_message.split('\n'), f"{operation_type_for_report} Report", report_icon), first_interval=0.01)
                self.report({'INFO'}, report_message) # Keep immediate status bar report
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
                    OT_BackupManager.ShowReport_static(message=report_message.split('\n'), title="Operation Status", icon='INFO')
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
                        OT_BackupManager.ShowReport_static(message=[report_msg_line1, report_msg_line2], title="Delete Backup Report", icon='COLORSET_01_VEC')
                        if prefs().debug or prefs().dry_run:
                             print(f"\n{action_verb} Backup: {target_path}")

                    except OSError as e:
                        action_verb = "Failed to (dry run) delete" if prefs().dry_run else "Failed to delete"
                        error_msg_line1 = f"{action_verb} {target_path}:"
                        error_msg_line2 = str(e)
                        self.report({'WARNING'}, f"{error_msg_line1} {error_msg_line2}")
                        OT_BackupManager.ShowReport_static(message=[error_msg_line1, error_msg_line2], title="Delete Backup Error", icon='WARNING')
                        if prefs().debug: # Keep print for debug
                            print(f"\n{action_verb} {target_path}: {e}")
                else:
                    not_found_msg = f"Not found, nothing to delete: {target_path}"
                    self.report({'INFO'}, not_found_msg)
                    OT_BackupManager.ShowReport_static(message=[f"Not found, nothing to delete:", target_path], title="Delete Backup Report", icon='INFO')
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
            OT_BackupManager.ShowReport_static(["Specify a Backup Path"] , "Backup Path missing", 'ERROR')
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
                OT_BackupManager.ShowReport_static(message=report_message.split('\n'), title=f"{operation_type} Report", icon=report_icon)

            except Exception as e:
                error_report_msg = f"{operation_type} for {os.path.basename(source_path)} failed: {e}\nSource: {source_path}\nTarget: {target_path}"
                self.report({'ERROR'}, error_report_msg)
                OT_BackupManager.ShowReport_static(message=error_report_msg.split('\n'), title=f"{operation_type} Error", icon='ERROR')
        else:
            warning_report_msg = f"Source for {operation_type} not found: {source_path}"
            self.report({'WARNING'}, warning_report_msg)
            OT_BackupManager.ShowReport_static(message=warning_report_msg.split('\n'), title=f"{operation_type} Warning", icon='WARNING')
    
