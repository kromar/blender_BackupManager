# Utility to fetch preferences and debug flag, and set logger debug state
from .preferences_utils import get_addon_preferences
from .logger import set_debug

def get_prefs_and_debug():
    """
    Returns (prefs, debug_flag). Also sets the logger's debug state.
    """
    prefs = None
    debug_flag = False
    try:
        prefs = get_addon_preferences()
        if prefs and hasattr(prefs, 'debug'):
            debug_flag = prefs.debug
    except Exception:
        pass
    set_debug(debug_flag)
    return prefs, debug_flag
