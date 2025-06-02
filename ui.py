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
import subprocess
import sys
from datetime import datetime
from bpy.types import Operator, UIList
from bpy.props import StringProperty, EnumProperty, BoolProperty

from . import preferences # For ITEM_DEFINITIONS, BM_Preferences
from . import utils # For get_addon_preferences
from . import core # For OT_BackupManager bl_idname

# --- UIList definition ---
class BM_UL_BackupItemsList(UIList):
    """UIList for displaying backup/restore items with enabled/shared toggles."""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        prefs_for_list = active_data 
        prop_enabled_name = f"{prefs_for_list.tabs.lower()}_{item.identifier}"
        is_enabled = getattr(prefs_for_list, prop_enabled_name, False)
        icon_enabled = 'CHECKBOX_HLT' if is_enabled else 'CHECKBOX_DEHLT'
        is_shared = getattr(prefs_for_list, f"shared_{item.identifier}", False)
        icon_shared = 'LINKED' if is_shared else 'UNLINKED'
        item_row = layout.row(align=True)
        item_row.prop(prefs_for_list, prop_enabled_name, text="", icon=icon_enabled, icon_only=True, emboss=False)
        item_row.label(text=item.name)
        shared_icon_container = item_row.row(align=True)
        shared_icon_container.alignment = 'RIGHT'
        shared_icon_container.prop(prefs_for_list, f"shared_{item.identifier}", text="", icon=icon_shared, icon_only=True, emboss=False)

# --- UI Helper Operators ---
class OT_OpenPathInExplorer(Operator):
    """Operator to open a given path in the system's file explorer."""
    bl_idname = "bm.open_path_in_explorer"
    bl_label = "Open Folder"
    bl_description = "Open the specified path in the system file explorer"
    bl_options = {'INTERNAL'}
    path_to_open: StringProperty(name="Path", description="The file or directory path to open")

    def execute(self, context):
        # (Content of this operator is moved from preferences.py without changes)
        # ... (implementation from preferences.py) ...
        if not self.path_to_open:
            self.report({'WARNING'}, "No path specified to open.")
            return {'CANCELLED'}
        normalized_path = os.path.normpath(self.path_to_open)
        if not os.path.exists(normalized_path):
            self.report({'WARNING'}, f"Path does not exist: {normalized_path}")
            return {'CANCELLED'}
        try:
            target_to_open_in_explorer = os.path.dirname(normalized_path) if os.path.isfile(normalized_path) else normalized_path
            if not os.path.isdir(target_to_open_in_explorer):
                self.report({'WARNING'}, f"Cannot open: Not a valid directory: {target_to_open_in_explorer}")
                return {'CANCELLED'}
            bpy.ops.wm.path_open(filepath=target_to_open_in_explorer)
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Could not open path '{normalized_path}': {e}")
            return {'CANCELLED'}

class OT_AbortOperation(Operator):
    """Operator to signal cancellation of the ongoing backup/restore operation."""
    bl_idname = "bm.abort_operation"
    bl_label = "Abort Backup/Restore"
    bl_description = "Requests cancellation of the current operation"

    def execute(self, context):
        prefs_instance = utils.get_addon_preferences()
        prefs_instance.abort_operation_requested = True
        if prefs_instance.debug:
            print("DEBUG (ui): OT_AbortOperation executed, abort_operation_requested set to True.")
        return {'FINISHED'}

class OT_QuitBlenderNoSave(Operator):
    """Quits Blender without saving current user preferences."""
    bl_idname = "bm.quit_blender_no_save"
    bl_label = "Quit & Restart Blender"
    # (Content of this operator is moved from core.py without significant changes, ensure utils.get_addon_preferences() is used)
    # ... (implementation from core.py, using utils.get_addon_preferences()) ...
    bl_description = "Attempts to start a new Blender instance, then quits the current one. If 'Save on Quit' is enabled in Blender's preferences, you will be warned."

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        addon_prefs_instance = utils.get_addon_preferences()
        prefs_main = context.preferences
        if prefs_main and hasattr(prefs_main, 'use_preferences_save') and prefs_main.use_preferences_save:
            return context.window_manager.invoke_confirm(self, event)
        else:
            return self.execute(context)
    
    def execute(self, context):
        addon_prefs = utils.get_addon_preferences()
        blender_exe = bpy.app.binary_path
        new_instance_launched_successfully = False
        if blender_exe and os.path.exists(blender_exe):
            try:
                args = [blender_exe]
                kwargs = {}
                if sys.platform == "win32": kwargs['creationflags'] = 0x00000008 # DETACHED_PROCESS
                elif sys.platform.startswith("linux"): kwargs['start_new_session'] = True
                subprocess.Popen(args, **kwargs)
                new_instance_launched_successfully = True
            except Exception as e:
                if addon_prefs.debug: print(f"ERROR (ui): OT_QuitBlenderNoSave: Failed to launch new Blender instance: {e}")
        bpy.ops.wm.quit_blender()
        return {'FINISHED'}

    def draw(self, context):
        # (Confirmation dialog drawing logic from core.py)
        layout = self.layout
        col = layout.column()
        col.label(text="Blender's 'Save Preferences on Quit' is currently ENABLED.", icon='ERROR')
        col.separator()
        col.label(text="If you proceed, Blender will save its current in-memory preferences when quitting.")
        # ... (rest of the dialog text)

class OT_CloseReportDialog(Operator):
    """Closes the report dialog without taking further action."""
    bl_idname = "bm.close_report_dialog"
    bl_label = "Don't Quit Now"
    bl_options = {'INTERNAL'}
    def execute(self, context):
        if utils.get_addon_preferences().debug:
            print("DEBUG (ui): OT_CloseReportDialog executed.")
        return {'FINISHED'}

class OT_ShowFinalReport(Operator):
    """Operator to display a popup message. Used by timers for deferred reports."""
    bl_idname = "bm.show_final_report"
    bl_label = "Show Operation Report"
    # (Content of this operator is moved from core.py without significant changes, ensure utils.get_addon_preferences() is used)
    # ... (implementation from core.py, using utils.get_addon_preferences()) ...
    bl_options = {'INTERNAL'}
    _title: str = "Report"
    _icon: str = "INFO"
    _lines: list = []
    _show_restart_button: bool = False
    _restart_operator_idname: str = ""

    @classmethod
    def set_report_data(cls, lines, title, icon, show_restart=False, restart_op_idname=""):
        cls._lines = lines
        cls._title = title
        cls._icon = icon
        cls._show_restart_button = show_restart
        cls._restart_operator_idname = restart_op_idname

    def execute(self, context):
        def draw_for_popup(self_menu, context_inner):
            layout = self_menu.layout
            for line in OT_ShowFinalReport._lines: layout.label(text=line)
            if OT_ShowFinalReport._show_restart_button and OT_ShowFinalReport._restart_operator_idname:
                layout.separator()
                row = layout.row(align=True)
                row.operator(OT_ShowFinalReport._restart_operator_idname, icon='FILE_REFRESH')
                row.operator(OT_CloseReportDialog.bl_idname, icon='CANCEL')
        context.window_manager.popup_menu(draw_for_popup, title=OT_ShowFinalReport._title, icon=OT_ShowFinalReport._icon)
        return {'FINISHED'}

# --- Main UI Window Operator ---
class OT_BackupManagerWindow(Operator):
    """Open the Backup Manager window."""
    bl_idname = "bm.open_backup_manager_window" # This ID is referenced by preferences.py for the addon prefs button
    bl_label = "Backup Manager"
    # (Content of this operator is moved from core.py, ensure utils.get_addon_preferences() and other new module paths are used)
    # ... (implementation from core.py, adapted for new structure) ...
    bl_options = {'REGISTER'}
    _cancelled: bool = False

    def _update_window_tabs(self, context):
        if getattr(self, '_cancelled', False): return
        prefs_instance = utils.get_addon_preferences()
        if not prefs_instance: return
        if prefs_instance.tabs != self.tabs:
            if prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow._update_window_tabs: Updating prefs.tabs to {self.tabs}")
            prefs_instance.tabs = self.tabs

    tabs: EnumProperty(
        name="Mode",
        items=[("BACKUP", "Backup", "Switch to Backup mode", "COLORSET_03_VEC", 0),
               ("RESTORE", "Restore", "Switch to Restore mode", "COLORSET_04_VEC", 1)],
        default="BACKUP",
        update=_update_window_tabs
    )
    show_item_configuration: BoolProperty(name="Configure Items", default=False)

    def _draw_path_age(self, layout, path_to_check):
        prefs_instance = utils.get_addon_preferences()
        if not path_to_check or not os.path.isdir(path_to_check):
            layout.label(text="Last change: Path N/A"); return
        display_text = preferences.BM_Preferences._age_cache.get(path_to_check, "Last change: Calculating...")
        layout.label(text=display_text)

    def _draw_path_size(self, layout, path_to_check):
        prefs_instance = utils.get_addon_preferences()
        if not path_to_check or not os.path.isdir(path_to_check):
            layout.label(text="Size: Path N/A"); return
        display_text = preferences.BM_Preferences._size_cache.get(path_to_check, "Size: Calculating...")
        layout.label(text=display_text)

    def _draw_backup_tab(self, layout, context, prefs_instance):
        row_main  = layout.row(align=True)
        box_from = row_main.box(); col_from = box_from.column()
        if not prefs_instance.advanced_mode:
            path_from_val = prefs_instance.blender_user_path
            col_from.label(text = "Backup From: " + str(prefs_instance.active_blender_version), icon='COLORSET_03_VEC')   
            col_from.label(text = path_from_val)      
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            box_to = row_main.box(); col_to = box_to.column()
            path_to_val =  os.path.join(prefs_instance.backup_path, prefs_instance.system_id, str(prefs_instance.active_blender_version)) if prefs_instance.backup_path and prefs_instance.system_id else "N/A"
            col_to.label(text = "Backup To: " + str(prefs_instance.active_blender_version), icon='COLORSET_04_VEC')
            col_to.label(text = path_to_val)          
            if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
        else: # Advanced mode
            source_version_selected = prefs_instance.backup_versions
            path_from_val = os.path.join(os.path.dirname(prefs_instance.blender_user_path), source_version_selected) if prefs_instance.blender_user_path and source_version_selected else "N/A"
            col_from.label(text="Backup From: " + source_version_selected, icon='COLORSET_03_VEC')
            col_from.label(text=path_from_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            col_from.prop(prefs_instance, 'backup_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)
            box_to = row_main.box(); col_to = box_to.column()
            if prefs_instance.custom_version_toggle:
                target_version_displayed = prefs_instance.custom_version
                path_to_val = os.path.join(prefs_instance.backup_path, prefs_instance.system_id, target_version_displayed) if prefs_instance.backup_path and prefs_instance.system_id and target_version_displayed else "N/A"
                col_to.label(text="Backup To: " + target_version_displayed, icon='COLORSET_04_VEC')
                col_to.label(text=path_to_val)
                if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
                col_to.prop(prefs_instance, 'custom_version', text='Version')
            else:
                target_version_displayed = prefs_instance.restore_versions
                path_to_val = os.path.join(prefs_instance.backup_path, prefs_instance.system_id, target_version_displayed) if prefs_instance.backup_path and prefs_instance.system_id and target_version_displayed else "N/A"
                col_to.label(text="Backup To: " + target_version_displayed, icon='COLORSET_04_VEC')
                col_to.label(text=path_to_val)
                if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
                col_to.prop(prefs_instance, 'restore_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

        col_actions = row_main.column(); col_actions.scale_x = 0.9
        col_actions.operator(core.OT_BackupManager.bl_idname, text="Backup Selected", icon='COLORSET_03_VEC').button_input = 'BACKUP' 
        if prefs_instance.advanced_mode:
            col_actions.operator(core.OT_BackupManager.bl_idname, text="Backup All", icon='COLORSET_03_VEC').button_input = 'BATCH_BACKUP' 
        col_actions.separator(factor=1.0)
        col_actions.prop(prefs_instance, 'dry_run'); col_actions.prop(prefs_instance, 'clean_path'); col_actions.prop(prefs_instance, 'advanced_mode') 
        if prefs_instance.advanced_mode:
            col_actions.prop(prefs_instance, 'custom_version_toggle'); col_actions.prop(prefs_instance, 'expand_version_selection')    
            col_actions.separator(factor=1.0)
            col_actions.operator(core.OT_BackupManager.bl_idname, text="Delete Backup", icon='COLORSET_01_VEC').button_input = 'DELETE_BACKUP'

    def _draw_restore_tab(self, layout, context, prefs_instance):
        row_main  = layout.row(align=True)
        box_from = row_main.box(); col_from = box_from.column()
        if not prefs_instance.advanced_mode:
            path_from_val = os.path.join(prefs_instance.backup_path, prefs_instance.system_id, str(prefs_instance.active_blender_version)) if prefs_instance.backup_path and prefs_instance.system_id else "N/A"
            col_from.label(text = "Restore From: " + str(prefs_instance.active_blender_version), icon='COLORSET_04_VEC')   
            col_from.label(text = path_from_val)                  
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            box_to = row_main.box(); col_to = box_to.column()
            path_to_val =  prefs_instance.blender_user_path
            col_to.label(text = "Restore To: " + str(prefs_instance.active_blender_version), icon='COLORSET_03_VEC')   
            col_to.label(text = path_to_val)              
            if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
        else: # Advanced Mode
            source_ver = prefs_instance.restore_versions
            path_from_val = os.path.join(prefs_instance.backup_path, prefs_instance.system_id, source_ver) if prefs_instance.backup_path and prefs_instance.system_id and source_ver else "N/A"
            col_from.label(text="Restore From: " + source_ver, icon='COLORSET_04_VEC')
            col_from.label(text=path_from_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_from, path_from_val); self._draw_path_size(col_from, path_from_val)
            col_from.prop(prefs_instance, 'restore_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)
            box_to = row_main.box(); col_to = box_to.column()
            target_ver = prefs_instance.backup_versions
            path_to_val = os.path.join(os.path.dirname(prefs_instance.blender_user_path), target_ver) if prefs_instance.blender_user_path and target_ver else "N/A"
            col_to.label(text="Restore To: " + target_ver, icon='COLORSET_03_VEC')
            col_to.label(text=path_to_val)
            if prefs_instance.show_path_details: self._draw_path_age(col_to, path_to_val); self._draw_path_size(col_to, path_to_val)
            col_to.prop(prefs_instance, 'backup_versions', text='Version' if prefs_instance.expand_version_selection else '', expand=prefs_instance.expand_version_selection)

        col_actions = row_main.column(); col_actions.scale_x = 0.9
        col_actions.operator(core.OT_BackupManager.bl_idname, text="Restore Selected", icon='COLORSET_04_VEC').button_input = 'RESTORE'
        if prefs_instance.advanced_mode:
            col_actions.operator(core.OT_BackupManager.bl_idname, text="Restore All", icon='COLORSET_04_VEC').button_input = 'BATCH_RESTORE'
        col_actions.separator(factor=1.0)
        col_actions.prop(prefs_instance, 'dry_run'); col_actions.prop(prefs_instance, 'clean_path'); col_actions.prop(prefs_instance, 'advanced_mode')  
        if prefs_instance.advanced_mode:
            col_actions.prop(prefs_instance, 'expand_version_selection')

    def draw(self, context):
        layout = self.layout
        prefs_instance = utils.get_addon_preferences()
        if self._cancelled or not prefs_instance:
            layout.label(text="Window closing..."); return

        _debug_draw = prefs_instance.debug
        is_operation_running = prefs_instance.show_operation_progress

        box_top = layout.box(); col_top = box_top.column(align=True)
        col_top.use_property_split = True; col_top.separator()
        row_system_id = col_top.row(); row_system_id.enabled = False
        row_system_id.prop(prefs_instance, "system_id")            
        settings_to_disable_group = col_top.column()
        settings_to_disable_group.enabled = not is_operation_running
        settings_to_disable_group.prop(prefs_instance, 'backup_path')
        settings_to_disable_group.prop(prefs_instance, 'show_path_details')
        col_top.prop(prefs_instance, 'debug'); col_top.separator()   

        if prefs_instance.debug:
            box_system_paths_display = col_top.box(); col_system_paths_display = box_system_paths_display.column(align=True)
            col_system_paths_display.label(text="Blender System Paths (Read-Only - Debug):")
            blender_install_path = os.path.dirname(bpy.app.binary_path)
            row_install = col_system_paths_display.row(align=True)
            row_install.label(text="Installation Path:")
            op_install = row_install.operator(OT_OpenPathInExplorer.bl_idname, icon='FILEBROWSER', text="")
            op_install.path_to_open = blender_install_path
            col_system_paths_display.label(text=blender_install_path)
            row_user_version_folder = col_system_paths_display.row(align=True)
            row_user_version_folder.label(text="User Version Folder:")
            op_user_version_folder = row_user_version_folder.operator(OT_OpenPathInExplorer.bl_idname, icon='FILEBROWSER', text="")
            op_user_version_folder.path_to_open = prefs_instance.blender_user_path
            col_system_paths_display.label(text=prefs_instance.blender_user_path)

        prefs_main = context.preferences
        show_manual_save_button = not (prefs_main and hasattr(prefs_main, 'use_preferences_save') and prefs_main.use_preferences_save)
        if show_manual_save_button:
            save_prefs_row = layout.row(align=True); save_prefs_row.enabled = not is_operation_running
            label_text = "Save Preferences" + (" *" if bpy.context.preferences.is_dirty else "")
            save_prefs_row.label(text=""); save_prefs_button_col = save_prefs_row.column(); save_prefs_button_col.scale_x = 0.5
            save_prefs_button_col.operator("wm.save_userpref", text=label_text, icon='PREFERENCES')
            
        layout.use_property_split = False
        layout.prop(self, "tabs", expand=False)

        if prefs_instance.show_operation_progress:
            op_status_box = layout.box(); op_status_col = op_status_box.column(align=True)
            if prefs_instance.operation_progress_message: op_status_col.label(text=prefs_instance.operation_progress_message)
            progress_row = op_status_col.row(align=True)
            progress_row.prop(prefs_instance, "operation_progress_value", slider=True, text="")
            progress_row.operator(OT_AbortOperation.bl_idname, text="", icon='CANCEL')

        tab_content_box = layout.box(); tab_content_box.enabled = not is_operation_running
        if self.tabs == "BACKUP": self._draw_backup_tab(tab_content_box, context, prefs_instance)
        elif self.tabs == "RESTORE": self._draw_restore_tab(tab_content_box, context, prefs_instance)
            
        if prefs_instance.advanced_mode:
            layout.separator()
            item_config_box = layout.box()
            item_config_box.prop(self, "show_item_configuration", icon="TRIA_DOWN" if self.show_item_configuration else "TRIA_RIGHT", icon_only=False, emboss=False)
            if self.show_item_configuration:
                prefs_instance._ensure_backup_items_populated()
                item_config_box.template_list(
                    "BM_UL_BackupItemsList", "",
                    prefs_instance, "backup_items_collection",
                    prefs_instance, "active_backup_item_index",
                    rows=len(preferences.ITEM_DEFINITIONS) if len(preferences.ITEM_DEFINITIONS) <= 10 else 10)

    def execute(self, context):
        prefs_instance = utils.get_addon_preferences()
        if prefs_instance and prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow.execute() EXIT.")
        return {'FINISHED'}

    def invoke(self, context, event):
        self._cancelled = False
        prefs_instance = utils.get_addon_preferences()
        if not prefs_instance: return {'CANCELLED'}
        if prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow.invoke() CALLED. Initializing tabs from prefs: {prefs_instance.tabs}")
        self.tabs = prefs_instance.tabs
        prefs_instance._update_backup_path_and_versions(context) # Ensure initial scan
        result = context.window_manager.invoke_props_dialog(self, width=700)
        if prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow.invoke() EXIT. Result: {result}.")
        return result

    def cancel(self, context):
        self._cancelled = True
        prefs_instance = utils.get_addon_preferences()
        if prefs_instance and prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow.cancel() ENTER.")
        # No need to abort OT_BackupManager operation from here.
        if prefs_instance and prefs_instance.debug: print(f"DEBUG (ui): OT_BackupManagerWindow.cancel() EXIT.")