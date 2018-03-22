# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgworks LLC

@description: Utilities related to creating and manipulating directories

@author: Ed Whetstone

@applications: Any

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
import os

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.0'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

def safe_make_dir(path, is_file=True):
    if is_file:
        base_path = os.path.dirname(path)
    else:
        base_path = path
    if not os.path.isdir(base_path):
        os.makedirs(base_path)
