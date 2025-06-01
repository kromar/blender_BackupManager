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
from bpy.props import FloatVectorProperty # Added for color property
from . import core # To reference OT_BackupManagerWindow.bl_idname

def get_paths_for_details(prefs_instance):
    """
    Collects all unique directory paths that might need age/size details displayed,
    based on the current addon preference settings.
    """
    paths = set()
    p = prefs_instance

    if not p.backup_path: # If no backup path, many other paths are invalid
        return []

    # Paths from draw_backup logic
    if not p.advanced_mode:
        if p.blender_user_path: paths.add(p.blender_user_path)
        if p.active_blender_version: # Ensure active_blender_version is not empty
            paths.add(os.path.join(p.backup_path, str(p.active_blender_version)))
    elif p.advanced_mode: # advanced_mode is True
        base_user_path_dir = os.path.dirname(p.blender_user_path) if p.blender_user_path else None
        if base_user_path_dir and p.backup_versions: # p.backup_versions is the selected string
             paths.add(os.path.join(base_user_path_dir, p.backup_versions))

        if p.custom_version_toggle and p.custom_version: # p.custom_version is a string
            paths.add(os.path.join(p.backup_path, str(p.custom_version)))
        elif p.restore_versions: # Not custom_version_toggle, p.restore_versions is selected string
            paths.add(os.path.join(p.backup_path, p.restore_versions))

    # Paths from draw_restore logic (many will be duplicates and handled by the set)
    if not p.advanced_mode:
        if p.active_blender_version: # Ensure active_blender_version is not empty
            paths.add(os.path.join(p.backup_path, str(p.active_blender_version)))
        if p.blender_user_path: paths.add(p.blender_user_path)
    elif p.advanced_mode: # advanced_mode is True
        if p.restore_versions: # p.restore_versions is selected string
            paths.add(os.path.join(p.backup_path, p.restore_versions))
        base_user_path_dir = os.path.dirname(p.blender_user_path) if p.blender_user_path else None
        if base_user_path_dir and p.backup_versions: # p.backup_versions is selected string
            paths.add(os.path.join(base_user_path_dir, p.backup_versions))
    
    final_paths = list(path for path in paths if path) # Filter out only None or empty strings
    if prefs_instance.debug:
        print(f"DEBUG: get_paths_for_details collected {len(final_paths)} relevant paths: {final_paths if len(final_paths) < 5 else '[Too many to list, see raw for full list]'}")
    return final_paths

def get_default_base_temp_dir():
    """Safely determines a base temporary directory for addon defaults."""
    temp_dir_path = ""
    try:
        # Try to access bpy.context and its attributes safely
        if bpy.context and hasattr(bpy.context, 'preferences') and \
           hasattr(bpy.context.preferences, 'filepaths') and \
           bpy.context.preferences.filepaths.temporary_directory:
            temp_dir_path = bpy.context.preferences.filepaths.temporary_directory
        else:
            # Fallback if user-specified temp path isn't available or context is limited
            temp_dir_path = bpy.app.tempdir
    except (RuntimeError, AttributeError, ReferenceError):
        # Broader fallback if bpy.context is unstable or bpy.app.tempdir fails
        try:
            temp_dir_path = bpy.app.tempdir
        except AttributeError: # Absolute fallback if bpy.app.tempdir also fails
            temp_dir_path = os.path.join(os.path.expanduser("~"), "blender_temp_fallback")
            os.makedirs(temp_dir_path, exist_ok=True) # Ensure fallback path exists
    return temp_dir_path

def _calculate_path_age_str(path_to_scan):
    try:
        if not path_to_scan or not os.path.isdir(path_to_scan): return "Last change: N/A" # Should be pre-filtered by get_paths_for_details
        files = [os.path.join(dp, f) for dp, dn, filenames in os.walk(path_to_scan) for f in filenames]
        if not files: return "Last change: no data (empty)"
        latest_file = max(files, key=os.path.getmtime)
        backup_age = str(datetime.now() - datetime.fromtimestamp(os.path.getmtime(latest_file))).split('.')[0]
        return "Last change: " + backup_age
    except Exception: return "Last change: error"

def _calculate_path_size_str(path_to_scan):
    try:
        if not path_to_scan or not os.path.isdir(path_to_scan): return "Size: N/A" # Should be pre-filtered
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, filenames in os.walk(path_to_scan) for f in filenames)
        return "Size: " + str(round(size * 0.000001, 2)) + " MB  (" + "{:,}".format(size) + " bytes)"
    except Exception: return "Size: error"

class BM_Preferences(AddonPreferences):
    bl_idname = __package__  
    this_version = str(bpy.app.version[0]) + '.' + str(bpy.app.version[1])  
    
    _age_cache = {}
    _size_cache = {}
    _initial_scan_done = False # Flag to track if the initial version scan has run
    FILES_PER_TICK_MODAL_OP: int = 10 # Process this many files per timer event in OT_BackupManager
    
    initial_version = f'{str(bpy.app.version[0])}.{str(bpy.app.version[1])}'
    backup_version_list = [(initial_version, initial_version, '')] # Standardize to 3-element tuple
    restore_version_list = [(initial_version, initial_version, '')] # Standardize to 3-element tuple
    
    def _update_backup_path_and_versions(self, context):
        """
        Central update handler for backup_path and related UI settings.
        Ensures backup_path is consistent with use_system_id, then refreshes version lists and details.
        """
        if self.debug:
            print("\n" + "-"*10 + f" _update_backup_path_and_versions (NEW FRAME) for tabs: {self.tabs} " + "-"*10 + "\n")
            _start_time_main_update = datetime.now()
            print(f"DEBUG: _update_backup_path_and_versions START. Current backup_path: '{self.backup_path}', use_system_id: {self.use_system_id}")

        # Step 1: Ensure backup_path consistency with use_system_id
        _current_bp_val = self.backup_path
        _made_change_to_bp_for_consistency = False

        if self.system_id and _current_bp_val: # Only proceed if system_id and current path are valid
            normalized_current_path = os.path.normpath(_current_bp_val)
            # Ensure system_id is treated as a single, clean directory name
            clean_system_id_name = self.system_id.strip(os.sep)
            system_id_suffix_to_check = os.sep + clean_system_id_name

            path_ends_with_system_id = normalized_current_path.endswith(system_id_suffix_to_check)

            if self.use_system_id:
                if not path_ends_with_system_id and clean_system_id_name: # Append if not present and system_id is non-empty
                    new_path = os.path.join(_current_bp_val, clean_system_id_name)
                    if os.path.normpath(new_path) != normalized_current_path:
                        if self.debug: print(f"DEBUG: _update_backup_path_and_versions: Appending system_id. Path changing from '{_current_bp_val}' to '{new_path}'")
                        self.backup_path = new_path
                        _made_change_to_bp_for_consistency = True
            else: # use_system_id is False
                if path_ends_with_system_id: # Strip if present
                    base_path = normalized_current_path[:-len(system_id_suffix_to_check)]
                    if base_path and os.path.normpath(base_path) != normalized_current_path: # Ensure base_path is not empty and a real change occurs
                        if self.debug: print(f"DEBUG: _update_backup_path_and_versions: Stripping system_id. Path changing from '{_current_bp_val}' to '{base_path}'")
                        self.backup_path = base_path
                        _made_change_to_bp_for_consistency = True
        
        if _made_change_to_bp_for_consistency:
            if self.debug: print(f"DEBUG: _update_backup_path_and_versions: self.backup_path was modified for consistency. Exiting to re-enter update cycle. New path: '{self.backup_path}'")
            return # Exit because self.backup_path was changed, this update function will run again.

        # Step 2: Original logic (clear caches, search versions, update path details)
        # This part only runs if no early return happened due to consistency changes.
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
                print("DEBUG: _update_backup_path_and_versions: show_path_details is True, recalculating details.")
            paths = get_paths_for_details(self)
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
    _initial_default_backup_path = os.path.join(get_default_base_temp_dir(), '!backupmanager')

    def update_system_id(self, context):
        """Updates the backup_path when use_system_id is toggled."""
        if self.debug: print(f"DEBUG: update_system_id (for use_system_id toggle) CALLED. use_system_id is now {self.use_system_id}. Current backup_path: '{self.backup_path}'")

        current_path = self.backup_path
        if not current_path or not self.system_id: # Safety check
            if self.debug: print("DEBUG: update_system_id: Current path or system_id is empty, cannot modify path.")
            # Trigger the main update anyway to refresh lists based on current state
            self._update_backup_path_and_versions(context)
            return

        normalized_current_path = os.path.normpath(current_path)
        clean_system_id_name = self.system_id.strip(os.sep)
        system_id_suffix_to_check = os.sep + clean_system_id_name
        path_ends_with_system_id = normalized_current_path.endswith(system_id_suffix_to_check)
        
        new_path_candidate = None

        if self.use_system_id: # User wants system_id in path
            if not path_ends_with_system_id and clean_system_id_name:
                new_path_candidate = os.path.join(current_path, clean_system_id_name)
        else: # User does NOT want system_id in path
            if path_ends_with_system_id:
                potential_base = normalized_current_path[:-len(system_id_suffix_to_check)]
                if potential_base: 
                    new_path_candidate = potential_base

        if new_path_candidate and os.path.normpath(new_path_candidate) != normalized_current_path:
            if self.debug: print(f"DEBUG: update_system_id: Changing backup_path from '{current_path}' to '{new_path_candidate}'")
            self.backup_path = new_path_candidate # This assignment will trigger _update_backup_path_and_versions
        elif self.debug:
            print(f"DEBUG: update_system_id: backup_path ('{current_path}') already consistent or no change needed. Triggering full update.")
            # Even if path doesn't change here, lists might need refresh based on the toggle.
            # The main update function will handle consistency again, then refresh lists.
            self._update_backup_path_and_versions(context)

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
     
    use_system_id: BoolProperty(name="Organize Backups by Computer",
                                description="If enabled, appends this computer's unique network name (e.g., 'MyComputer.domain.com') " \
                                "as a subfolder to the 'Main Backup Location'. " \
                                "This prevents backups from different computers from overwriting each other when using a shared backup drive.",
                                update=update_system_id,
                                default=True)   # default = True
    
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
            new_age_text = _calculate_path_age_str(path)
            if BM_Preferences._age_cache.get(path) != new_age_text:
                BM_Preferences._age_cache[path] = new_age_text
                cache_updated = True
                if self.debug: print(f"DEBUG: _update_path_details_for_paths: Cached new age for '{path}'")

            new_size_text = _calculate_path_size_str(path)
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
            paths = get_paths_for_details(self)
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
            paths = get_paths_for_details(self) # Re-evaluate all relevant paths
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

    # DRAW Preferences      
    def draw(self, context):
        layout = self.layout
        layout.label(text="Backup Manager operations are now handled in a dedicated window.")
        layout.operator(core.OT_BackupManagerWindow.bl_idname, text="Open Backup Manager Window", icon='WINDOW')

        layout.separator()
        box = layout.box()
        col = box.column(align=True)
        col.prop(self, "backup_path", text="Main Backup Location", icon='FILE_FOLDER')

        box.separator()
        col = box.column(align=True)
        col.label(text="Progress Bar Appearance:")
        row = col.row(align=True)
        row.prop(self, "override_progress_bar_color", text="Override Color", icon='COLOR')
        if self.override_progress_bar_color:
            row = col.row(align=True)
            row.prop(self, "custom_progress_bar_color", text="")



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


    def draw_backup(self, box): 

        row  = box.row()
        box1 = row.box() 
        col = box1.column()
        if not self.advanced_mode:            
            path = self.blender_user_path
            col.label(text = "Backup From: " + str(self.active_blender_version), icon='COLORSET_03_VEC')   
            col.label(text = path)      
            if self.show_path_details:
                self.draw_backup_age(col, path) 
                self.draw_backup_size(col, path)            
            
            box = row.box() 
            col = box.column()  
            path =  os.path.join(self.backup_path, str(self.active_blender_version))
            col.label(text = "Backup To: " + str(self.active_blender_version), icon='COLORSET_04_VEC')   
            col.label(text = path)          
            if self.show_path_details:
                self.draw_backup_age(col, path)    
                self.draw_backup_size(col, path)  
            
        elif self.advanced_mode:   
            if self.custom_version_toggle:    
                path = os.path.join(os.path.dirname(self.blender_user_path),  self.backup_versions)
                col.label(text = "Backup From: " + self.backup_versions, icon='COLORSET_03_VEC') 
                col.label(text = path)       
                if self.show_path_details:
                    self.draw_backup_age(col, path)
                    self.draw_backup_size(col, path)
                                
                box2 = row.box() 
                col = box2.column()  
                path = os.path.join(self.backup_path, str(self.custom_version))
                col.label(text = "Backup To: " + str(self.custom_version), icon='COLORSET_04_VEC')   
                col.label(text = path)     
                if self.show_path_details:
                    self.draw_backup_age(col, path)    
                    self.draw_backup_size(col, path)                

            else:                
                path = os.path.join(os.path.dirname(self.blender_user_path),  self.backup_versions)
                col.label(text = "Backup From: " + self.backup_versions, icon='COLORSET_03_VEC') 
                col.label(text = path)       
                if self.show_path_details:
                    self.draw_backup_age(col, path)
                    self.draw_backup_size(col, path)
                
                box2 = row.box() 
                col = box2.column()  
                path =  os.path.join(self.backup_path, self.restore_versions)
                col.label(text = "Backup To: " + self.restore_versions, icon='COLORSET_04_VEC')   
                col.label(text = path)
                if self.show_path_details:
                    self.draw_backup_age(col, path)
                    self.draw_backup_size(col, path)

            # Advanced options
            col = box1.column()   
            col.scale_x = 0.8   
            # Redundant debug prints, populate_backuplist already logs list state
            # if self.debug:
            #     print(f"DEBUG: draw_backup (Advanced): expand={self.expand_version_selection}, val='{self.backup_versions}'")
            #     print(f"DEBUG: draw_backup (Advanced): BM_Preferences.backup_version_list (len={len(BM_Preferences.backup_version_list)})")
            col.prop(self, 'backup_versions', text='Backup From', expand = self.expand_version_selection) 
    
            col = box2.column()   
            if self.custom_version_toggle: 
                col.scale_x = 0.8
                col.prop(self, 'custom_version')
            else:      
                col.scale_x = 0.8 
                col.prop(self, 'restore_versions', text='Backup To', expand = self.expand_version_selection)
                # Redundant debug prints
                # if self.debug:
                #     print(f"DEBUG: draw_backup (Advanced, Backup To): expand={self.expand_version_selection}, val='{self.restore_versions}'")
            
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
            if self.show_path_details:
                self.draw_backup_age(col, path) 
                self.draw_backup_size(col, path)            
                   
            box = row.box() 
            col = box.column()  
            path =  self.blender_user_path
            col.label(text = "Restore To: " + str(self.active_blender_version), icon='COLORSET_03_VEC')   
            col.label(text = path)              
            if self.show_path_details:
                self.draw_backup_age(col, path)    
                self.draw_backup_size(col, path)  

        else:        
            path = os.path.join(self.backup_path, self.restore_versions)
            col.label(text = "Restore From: " + self.restore_versions, icon='COLORSET_04_VEC')   
            col.label(text = path)    
            if self.show_path_details:
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)
            
            box2 = row.box() 
            col = box2.column()  
            path =  os.path.join(os.path.dirname(self.blender_user_path),  self.backup_versions)
            col.label(text = "Restore To: " + self.backup_versions, icon='COLORSET_03_VEC')   
            col.label(text = path)    
            if self.show_path_details:
                self.draw_backup_age(col, path)
                self.draw_backup_size(col, path)

            # Advanced options
            col = box1.column() 
            col.scale_x = 0.8
            # Redundant debug prints
            # if self.debug:
            #     print(f"DEBUG: draw_restore (Advanced): expand={self.expand_version_selection}, val='{self.restore_versions}'")
            #     print(f"DEBUG: draw_restore (Advanced): BM_Preferences.restore_version_list (len={len(BM_Preferences.restore_version_list)})")
            col.prop(self, 'restore_versions', text='Restore From', expand = self.expand_version_selection) 
            
            col = box2.column()  
            col.scale_x = 0.8                 
            # Redundant debug prints
            # if self.debug:
            #     print(f"DEBUG: draw_restore (Advanced, Restore To): expand={self.expand_version_selection}, val='{self.backup_versions}'")
            #     print(f"DEBUG: draw_restore (Advanced, Restore To): BM_Preferences.backup_version_list (len={len(BM_Preferences.backup_version_list)})")
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
            col.prop(self, 'backup_extensions') 
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
            col.prop(self, 'restore_extensions') 
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
            
        
