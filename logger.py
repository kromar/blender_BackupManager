# Centralized logger for the Backup Manager addon
import logging

DEBUG_ENABLED = False  # Set this from preferences if needed

def set_debug(enabled: bool):
    global DEBUG_ENABLED
    DEBUG_ENABLED = enabled

def debug(msg):
    if DEBUG_ENABLED:
        print(f"[DEBUG] {msg}")
