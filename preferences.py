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
from bpy.props import StringProperty, EnumProperty, BoolProperty, FloatProperty
from bpy.props import FloatVectorProperty
from . import utils # For helper functions like get_paths_for_details, _calculate_path_age_str, etc.

# ITEM_DEFINITIONS and BM_BackupItem moved here from core.py
ITEM_DEFINITIONS = [
    # identifier, display_name
    ("addons", "Addons"), # typically in 'scripts/addons'
    ("extensions", "Extensions"),
    ("presets", "Presets"),
    ("datafile", "Datafile"),
    ("startup_blend", "startup.blend"),
    ("userpref_blend", "userpref.blend"),
    ("workspaces_blend", "workspaces.blend"),
    ("cache", "Cache"),
    ("bookmarks", "Bookmarks"),
    ("recentfiles", "Recent Files"),
]

class BM_BackupItem(bpy.types.PropertyGroup):
    """Represents an item in the backup/restore configuration list."""
    name: StringProperty(name="Name", description="Display name of the backup item")
    identifier: StringProperty(name="Identifier", description="Internal identifier for the item (matches property suffix)")

class BM_Preferences(AddonPreferences):
    """Addon Preferences for the Backup Manager."""
    bl_idname = __package__  
    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])  
    
    _age_cache = {}
    _size_cache = {}
    _initial_scan_done = False # Flag to track if the initial version scan has run
    FILES_PER_TICK_MODAL_OP: int = 10 # Process this many files per timer event in OT_BackupManager
    
    initial_version = f'{str(bpy.app.version[0])}.{str(bpy.app.version[1])}'
    backup_version_list = [(initial_version, initial_version, '')] # Standardize to 3-element tuple
    restore_version_list = [(initial_version, initial_version, '')] # Standardize to 3-element tuple

    # Collection and active index for the UIList (data stored in prefs, list drawn in core.OT_BackupManagerWindow)
    # BM_BackupItem is now defined in this file.
    backup_items_collection: bpy.props.CollectionProperty(type=BM_BackupItem)
    active_backup_item_index: bpy.props.IntProperty()

    # _ITEM_DEFINITIONS_FOR_POPULATE now refers to the local ITEM_DEFINITIONS
    _ITEM_DEFINITIONS_FOR_POPULATE = ITEM_DEFINITIONS


    def _update_backup_path_and_versions(self, context):
        """
        Central update handler for backup_path and related UI settings.
        Refreshes version lists and details. System ID is always used.
        """
        if self.debug:
            print("\n" + "-"*10 + f" _update_backup_path_and_versions (NEW FRAME) for tabs: {self.tabs} " + "-"*10 + "\n")
            _start_time_main_update = datetime.now()
            print(f"DEBUG: _update_backup_path_and_versions START. Current backup_path: '{self.backup_path}'")

        if self.debug:
            # Clear caches when version lists are being updated
            BM_Preferences._age_cache.clear()
            print("DEBUG: _update_backup_path_and_versions: Cleared _age_cache.")
            BM_Preferences._size_cache.clear()
            print("DEBUG: _update_backup_path_and_versions: Cleared _size_cache.")

        if self.debug:
            _call_time_search_op = datetime.now()
            print(f"DEBUG: _update_backup_path_and_versions: CALLING bpy.ops.bm.run_backup_manager with SEARCH_{self.tabs}")
        try:
            bpy.ops.bm.run_backup_manager(button_input=f'SEARCH_{self.tabs}')
        except Exception as e:
            print(f"ERROR: Backup Manager: Error calling bpy.ops.bm.run_backup_manager in _update_backup_path_and_versions (likely during script reload): {e}")
            return # Stop further processing in this update if the op call failed
        if self.debug:
            _end_time_search_op = datetime.now()
            print(f"DEBUG: (took: {(_end_time_search_op - _call_time_search_op).total_seconds():.6f}s) _update_backup_path_and_versions: FINISHED bpy.ops.bm.run_backup_manager.")
        
        BM_Preferences._initial_scan_done = True
        
        if self.show_path_details:
            if self.debug:
                print("DEBUG (prefs): _update_backup_path_and_versions: show_path_details is True, recalculating details.")
            paths = utils.get_paths_for_details(self) # Use utils module
            if self._update_path_details_for_paths(paths):
                if context and hasattr(context, 'area') and context.area:
                    context.area.tag_redraw()
                elif self.debug:
                    print("DEBUG: _update_backup_path_and_versions: context or context.area not available for tag_redraw after detail update.")
        elif self.debug: # This else corresponds to "if self.show_path_details:"
            print("DEBUG: _update_backup_path_and_versions: show_path_details is False, not recalculating details.")

        if self.debug and _start_time_main_update:
            _end_time_main_update = datetime.now()
            print(f"DEBUG: (Total took: {(_end_time_main_update - _start_time_main_update).total_seconds():.6f}s) _update_backup_path_and_versions END")
    
    # Calculate the initial default backup path safely ONCE when the class is defined.
    # This function call happens during module import / class definition.
    _initial_default_backup_path = os.path.join(utils.get_default_base_temp_dir(), '!backupmanager')

    backup_path: StringProperty(name="Backup Path", 
                                description="Backup Location", 
                                subtype='DIR_PATH', 
                                default=_initial_default_backup_path, 
                                update=_update_backup_path_and_versions)
    
    blender_user_path: StringProperty(default=bpy.utils.resource_path(type='USER'))
    
    preferences_tabs = [("BACKUP", "Backup Options", ""),
                ("RESTORE", "Restore Options", "")]
    
    tabs: EnumProperty(name="Tabs", 
                       items=preferences_tabs, 
                       default="BACKUP",
                       update=_update_backup_path_and_versions)
    
    config_path: StringProperty(name="config_path",
                                description="config_path", 
                                subtype='DIR_PATH', 
                                default=bpy.utils.user_resource('CONFIG')) #Resource type in [‘DATAFILES’, ‘CONFIG’, ‘SCRIPTS’, ‘AUTOSAVE’].
    
    system_id: StringProperty(name="System ID", 
                              description="Current Computer ID, used to create unique backup paths", 
                              subtype='NONE',
                              default=str(socket.getfqdn())) 
    
    debug: BoolProperty(name="Debug Output", 
                        description="Enable debug logging", 
                        # update=update_system_id, # Debug toggle should not typically change system ID path logic
                        default=False) # default = False  
    
    active_blender_version: StringProperty(name="Current Blender Version", 
                                           description="Current Blender Version", 
                                           subtype='NONE', 
                                           default=this_version)
    dry_run: BoolProperty(name="Dry Run",
                          description="Run code without modifying any files on the drive."
                          "NOTE: this will not create or restore any backups!", 
                          default=False)     # default = False 
    
    def _update_path_details_for_paths(self, paths_to_update):
        """Helper to calculate and cache details for a list of paths."""
        if not self.show_path_details:
            return False # Do nothing if details are not shown

        cache_updated = False
        # Caches are now class attributes, no need for hasattr check here for initialization

        for path in paths_to_update:
            if self.debug: print(f"DEBUG: _update_path_details_for_paths: Processing '{path}'")
            new_age_text = utils._calculate_path_age_str(path) # Use utils module
            if BM_Preferences._age_cache.get(path) != new_age_text:
                BM_Preferences._age_cache[path] = new_age_text
                cache_updated = True
                if self.debug: print(f"DEBUG: _update_path_details_for_paths: Cached new age for '{path}'")

            new_size_text = utils._calculate_path_size_str(path) # Use utils module
            if BM_Preferences._size_cache.get(path) != new_size_text:
                BM_Preferences._size_cache[path] = new_size_text
                cache_updated = True
                if self.debug: print(f"DEBUG: _update_path_details_for_paths: Cached new size for '{path}'")
        
        if self.debug and not cache_updated and paths_to_update:
            print(f"DEBUG: _update_path_details_for_paths: No cache changes for paths: {paths_to_update if len(paths_to_update) < 5 else '[Multiple paths, no changes]'}")
        return cache_updated

    def _on_show_path_details_changed(self, context):
        """Update callback for show_path_details."""
        if self.debug:
            print(f"DEBUG: _on_show_path_details_changed called. self.show_path_details = {self.show_path_details}")
        if self.show_path_details:
            if self.debug: print("DEBUG: show_path_details enabled. Calculating details for current view.")
            paths = utils.get_paths_for_details(self) # Use utils module
            # Path list already printed by get_paths_for_details if debug is on
            # if self.debug: print(f"DEBUG: _on_show_path_details_changed: paths_to_update = {paths}")
            if self._update_path_details_for_paths(paths):
                if context and hasattr(context, 'area') and context.area:
                    context.area.tag_redraw()
                elif self.debug:
                    print("DEBUG: _on_show_path_details_changed: context or context.area not available for tag_redraw.")
        elif self.debug:
            print("DEBUG: _on_show_path_details_changed: show_path_details is now False.")

    def _on_version_or_custom_changed(self, context):
        """Update callback for version enums and custom_version string."""
        if self.debug:
            print(f"DEBUG: _on_version_or_custom_changed TRIGGERED. self.show_path_details = {self.show_path_details}")
            print(f"DEBUG: Current selections: backup_versions='{self.backup_versions}', restore_versions='{self.restore_versions}', custom_version='{self.custom_version}', custom_toggle={self.custom_version_toggle}")

        if self.show_path_details:
            if self.debug: print("DEBUG: Version selection or custom version changed. Recalculating details for current view.")
            paths = utils.get_paths_for_details(self) # Use utils module
            # Path list already printed by get_paths_for_details if debug is on
            # if self.debug: print(f"DEBUG: _on_version_or_custom_changed: paths_to_update = {paths}")
            
            if self._update_path_details_for_paths(paths):
                if self.debug: print("DEBUG: _on_version_or_custom_changed: Cache updated, tagging for redraw.")
                if context and hasattr(context, 'area') and context.area:
                    context.area.tag_redraw()
                elif self.debug:
                    print("DEBUG: _on_version_or_custom_changed: context or context.area not available for tag_redraw.")
            elif self.debug:
                print("DEBUG: _on_version_or_custom_changed: Cache was not updated by _update_path_details_for_paths.")
        elif self.debug:
            print("DEBUG: _on_version_or_custom_changed: show_path_details is False, not calculating details.")


    show_path_details: BoolProperty(name="Show Path Details",
                                    description="Display last change date and size for backup/restore paths. Calculated on demand.",
                                    default=True,
                                    update=_on_show_path_details_changed)
    
    show_operation_progress: BoolProperty(
        default=False, 
        options={'SKIP_SAVE'} # Internal: Controls visibility of progress UI, should not persist.
    )
    operation_progress_value: FloatProperty(
        default=0.0,
        min=0.0,
        max=100.0,  # Back to 0-100 range
        subtype='PERCENTAGE', # Back to PERCENTAGE subtype
        options={'SKIP_SAVE'} # Internal: Progress value, should not persist.
    )
    operation_progress_message: StringProperty(
        default="Waiting...", 
        options={'SKIP_SAVE'} # Internal: Progress message, should not persist.
    )
    abort_operation_requested: BoolProperty(
        default=False, 
        options={'SKIP_SAVE'} # Internal: Flag to signal abort from UI, should not persist.
    )
    
    advanced_mode: BoolProperty(name="Advanced", 
                                description="Advanced backup and restore options", 
                                update=_update_backup_path_and_versions,
                                default=True)  # default = True
    
    expand_version_selection: BoolProperty(name="Expand Versions", 
                                           description="Switch between dropdown and expanded version layout",
                                           update=_update_backup_path_and_versions,
                                           default=True)  # default = True
    
    custom_version: StringProperty(name="Custom Version", 
                                   description="Custom version folder", 
                                   subtype='NONE', 
                                   default='custom',
                                   update=_on_version_or_custom_changed) # This specific update is fine for path details
    
    # BACKUP  (custom_version_toggle was defined twice, keeping this one as it's grouped with other backup options)
    custom_version_toggle: BoolProperty(name="Custom Version", 
                                        description="Set your custom backup version", 
                                        default=False,  # default = False
                                        update=_update_backup_path_and_versions,
                                        )

    clean_path: BoolProperty(name="Clean Backup", 
                             description="delete before backup", 
                             default=False) # default = False 
    
    def populate_backuplist(self, context):
        #if hasattr(self, 'debug') and self.debug: # Check if self has debug, might not always if context is weird
            #print(f"DEBUG: populate_backuplist CALLED. Returning BM_Preferences.backup_version_list (len={len(BM_Preferences.backup_version_list)}): {BM_Preferences.backup_version_list}")
        current_list = BM_Preferences.backup_version_list
        if not isinstance(current_list, list) or not all(isinstance(item, tuple) and len(item) == 3 for item in current_list if item): # Check list integrity
            print("ERROR: Backup Manager: BM_Preferences.backup_version_list is malformed in populate_backuplist. Returning default.")
            return [(BM_Preferences.initial_version, BM_Preferences.initial_version, "Default version")]
        if not current_list: # If the list is empty
            return [("(NONE)", "No Versions Found", "Perform a search or check backup path")]
        # Ensure all items are 3-element tuples
        # The list should already contain 3-element tuples from find_versions
        return current_list
      
    backup_versions: EnumProperty(items=populate_backuplist,
                                  name="Backup",  
                                  description="Choose the version to backup", 
                                  update=_on_version_or_custom_changed) # This specific update is fine for path details
    
    backup_cache: BoolProperty(name="cache", description="backup_cache", default=False)   # default = False      
    backup_bookmarks: BoolProperty(name="bookmarks", description="backup_bookmarks", default=True)   # default = True   
    backup_recentfiles: BoolProperty(name="recentfiles", description="backup_recentfiles", default=True)  # default = True
    backup_startup_blend: BoolProperty( name="startup.blend", description="backup_startup_blend", default=True)  # default = True   
    backup_userpref_blend: BoolProperty(name="userpref.blend", description="backup_userpref_blend", default=True)  # default = True  
    backup_workspaces_blend: BoolProperty(name="workspaces.blend", description="backup_workspaces_blend", default=True)  # default = True 
    backup_datafile: BoolProperty( name="datafile", description="backup_datafile", default=True)  # default = True       
    backup_addons: BoolProperty(name="addons", description="backup_addons", default=True)   # default = True       
    backup_extensions: BoolProperty(name="extensions", description="backup_extensions", default=True)   # default = True     
    backup_presets: BoolProperty(name="presets", description="backup_presets", default=True) # default = True

    # Corresponding "shared" properties
    shared_cache: BoolProperty(name="Cache Shared", default=False) # default = False
    shared_bookmarks: BoolProperty(name="Bookmarks Shared", default=False) # default = False
    shared_recentfiles: BoolProperty(name="Recent Files Shared", default=False) # default = False
    shared_startup_blend: BoolProperty(name="startup.blend Shared", default=True) # default = True
    shared_userpref_blend: BoolProperty(name="userpref.blend Shared", default=True) # default = True
    shared_workspaces_blend: BoolProperty(name="workspaces.blend Shared", default=True) # default = True
    shared_datafile: BoolProperty(name="Datafile Shared", default=True) # default = True
    shared_addons: BoolProperty(name="Addons Shared", default=True) # default = True
    shared_extensions: BoolProperty(name="Extensions Shared", default=True) # default = True
    shared_presets: BoolProperty(name="Presets Shared", default=True) # default = True

    # RESTORE      
    def populate_restorelist(self, context):
        #if hasattr(self, 'debug') and self.debug:
            #print(f"DEBUG: populate_restorelist CALLED. Returning BM_Preferences.restore_version_list (len={len(BM_Preferences.restore_version_list)}): {BM_Preferences.restore_version_list}")
        current_list = BM_Preferences.restore_version_list
        if not isinstance(current_list, list) or not all(isinstance(item, tuple) and len(item) == 3 for item in current_list if item): # Check list integrity
            print("ERROR: Backup Manager: BM_Preferences.restore_version_list is malformed in populate_restorelist. Returning default.")
            return [(BM_Preferences.initial_version, BM_Preferences.initial_version, "Default version")]
        if not current_list: # If the list is empty
            return [("(NONE)", "No Versions Found", "Perform a search or check backup path")]
         # Ensure all items are 3-element tuples
        # The list should already contain 3-element tuples from find_versions
        return current_list
          
    restore_versions: EnumProperty(items=populate_restorelist, 
                                   name="Restore", 
                                   description="Choose the version to Resotre", 
                                   update=_on_version_or_custom_changed) # This specific update is fine for path details
    
    restore_cache: BoolProperty(name="cache", description="restore_cache", default=False)  # default = False  
    restore_bookmarks: BoolProperty(name="bookmarks", description="restore_bookmarks", default=True)    # default = True
    restore_recentfiles: BoolProperty(name="recentfiles", description="restore_recentfiles", default=True)  # default = True
    restore_startup_blend: BoolProperty(name="startup.blend", description="restore_startup_blend",  default=True)   # default = True  
    restore_userpref_blend: BoolProperty(name="userpref.blend", description="restore_userpref_blend", default=True)  # default = True  
    restore_workspaces_blend: BoolProperty(name="workspaces.blend", description="restore_workspaces_blend", default=True)   # default = True
    restore_datafile: BoolProperty(name="datafile", description="restore_datafile", default=True)       # default = True  
    restore_addons: BoolProperty(name="addons", description="restore_addons", default=True)    # default = True  
    restore_extensions: BoolProperty(name="extensions", description="restore_extensions", default=True)    # default = True  
    restore_presets: BoolProperty(name="presets", description="restore_presets", default=True)   # default = True  

    ignore_files: StringProperty(name="Ignore Files",
                                description="Ignore files from being backed up or restored", 
                                subtype='FILE_NAME', 
                                default='desktop.ini')

    # Progress Bar Color Customization
    override_progress_bar_color: BoolProperty(
        name="Override Progress Bar Color",
        description="Enable to use a custom color for the addon's progress bar",
        default=False)
    custom_progress_bar_color: FloatVectorProperty(
        name="Custom Progress Bar Color",
        description="Color for the addon's progress bar when override is enabled",
        subtype='COLOR', size=4, default=(0.2, 0.8, 0.2, 1.0), # Default to a nice green (RGBA)
        min=0.0, max=1.0)

    def _ensure_backup_items_populated(self):
        if not self.backup_items_collection: # Check if it's empty or not populated
            for identifier, name in BM_Preferences._ITEM_DEFINITIONS_FOR_POPULATE: # Uses local ITEM_DEFINITIONS
                item = self.backup_items_collection.add() # self.backup_items_collection is CollectionProperty of local BM_BackupItem
                item.name = name
                item.identifier = identifier

    # DRAW Preferences      
    def draw(self, context):
        layout = self.layout
        # from . import ui # Import ui locally - Removed to break potential circular import

        # --- Main Operator Button ---
        layout.label(text="Backup Manager operations are now handled in a dedicated window.")
        layout.operator("bm.open_backup_manager_window", text="Open Backup Manager Window", icon='DISK_DRIVE')

        layout.separator()
        
        # --- Path Settings ---
        # Box for path settings and appearance
        box_settings = layout.box()
        col_settings = box_settings.column(align=True)

        # Main Backup Location
        col_settings.label(text="Storage Location:")
        row_backup_path = col_settings.row(align=True)
        row_backup_path.prop(self, "backup_path", text="Main Backup Location") 
        # Use bl_idname string directly for OT_OpenPathInExplorer
        op_backup_loc = row_backup_path.operator("bm.open_path_in_explorer", icon='FILEBROWSER', text="")
        op_backup_loc.path_to_open = self.backup_path
        
        if self.debug: # Only show system paths if debug is enabled
            col_settings.separator()

            # Blender System Paths (Read-Only)
            col_settings.label(text="Blender System Paths (Read-Only - Debug):")

            # Blender Installation Path
            blender_install_path = os.path.dirname(bpy.app.binary_path)
            row_install = col_settings.row(align=True)
            row_install.label(text="Installation Path:")
            # Use bl_idname string directly for OT_OpenPathInExplorer
            op_install = row_install.operator("bm.open_path_in_explorer", icon='FILEBROWSER', text=blender_install_path)
            op_install.path_to_open = blender_install_path

            # User Version Folder Path
            row_user_version_folder = col_settings.row(align=True)
            row_user_version_folder.label(text="User Version Folder:")
            # row_user_version_folder.label(text=self.blender_user_path)
            # Use bl_idname string directly for OT_OpenPathInExplorer
            op_user_version_folder = row_user_version_folder.operator("bm.open_path_in_explorer", icon='FILEBROWSER', text=self.blender_user_path)
            op_user_version_folder.path_to_open = self.blender_user_path

            # User Config Subfolder Path (e.g., .../VERSION/config)
            row_config_subfolder = col_settings.row(align=True)
            row_config_subfolder.label(text="User Config Subfolder:")
            # row_config_subfolder.label(text=self.config_path)
            # Use bl_idname string directly for OT_OpenPathInExplorer
            op_config_subfolder = row_config_subfolder.operator("bm.open_path_in_explorer", icon='FILEBROWSER', text=self.config_path)
            op_config_subfolder.path_to_open = self.config_path

        col_settings.separator()
        col_settings.label(text="Progress Bar Appearance:")
        row_override_color = col_settings.row(align=True)
        row_override_color.prop(self, "override_progress_bar_color", text="Override Color", icon='COLOR')
        if self.override_progress_bar_color:
            row_custom_color = col_settings.row(align=True)
            row_custom_color.prop(self, "custom_progress_bar_color", text="")

    # The UIList for item configuration has been moved to the OT_BackupManagerWindow in core.py
    def draw_backup_age(self, col, path):       
        # Access class attribute
        display_text = BM_Preferences._age_cache.get(path)
        if display_text is None: # Not yet calculated by timer or path is new
            display_text = "Last change: Calculating..."
            if self.debug: print(f"DEBUG: draw_backup_age: No cache for '{path}', displaying 'Calculating...'")
        elif self.debug:
             print(f"DEBUG: draw_backup_age: Using cached value for '{path}': {display_text}")
        col.label(text=display_text)


    def draw_backup_size(self, col, path):
        # Access class attribute
        display_text = BM_Preferences._size_cache.get(path)
        if display_text is None: # Not yet calculated by timer or path is new
            display_text = "Size: Calculating..."
            if self.debug: print(f"DEBUG: draw_backup_size: No cache for '{path}', displaying 'Calculating...'")
        elif self.debug:
            print(f"DEBUG: draw_backup_size: Using cached value for '{path}': {display_text}")
        col.label(text=display_text)
            
        
