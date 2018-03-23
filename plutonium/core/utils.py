# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: general utilities, which don't fit in a specific module yet

@author: Ed Whetstone

@applications: NUKE

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
from vfx_utils.plutonium.core import decorators

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '2.5'
DEBUG_VERSION = '2.5.1'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ----------------------------------------------------------- Preferences -- #
@decorators.memo_args
def pref(pref_knob):
    """get the value of a specific NUKE preference"""
    return nuke.toNode('preferences')[pref_knob].value()

def prefList(search_terms):
    """list all preferences and their values in NUKE"""
    for term in search_terms:
        prefs = [n for n in nuke.toNode('preferences').knobs()
                 if term in n]
        for pr in prefs:
            # TODO: pretty printing and slogging
            print pr
            print pref(pr)

def edit_pref(pref_knob, value):
    """edit a preference in NUKE"""
    nuke.toNode('preferences')[pref_knob].setValue(value)


# ------------------------------------------------------------ Undo Queue -- #
class Undoable_Action(object):
    """context manager which allows undo chunking"""
    def __init__(self, action_name='custom_undo'):
        self.queue = nuke.Undo(action_name)

    def __enter__(self):
        self.queue.begin()

    def __exit__(self, *args):
        self.queue.end()
