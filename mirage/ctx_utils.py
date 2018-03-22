# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@organization: Kludgeworks LLC

@description: A collection of context managers for Maya operations

@author: Ed Whetstone

@applications: Maya

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from contextlib import contextmanager

# domain
from maya import cmds

# -------------------------------------------------------------------------- #
# ---------------------------------------------------------- VERSION INFO -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.1'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
@contextmanager
def namespace(namespace):
    """sets namespace in maya, yields control, then resets to root"""
    cmds.namespace(set=str(namespace))
    cmds.namespace(relativeNames=True)
    try:
        yield
    except:
        raise
    finally:
        cmds.namespace(set=":")
        cmds.namespace(relativeNames=False)

@contextmanager
def frame(frame):
    """sets the current frame, yields control, then resets the frame"""
    time = cmds.currentTime(q=True)
    cmds.currentTime(frame, e=True, update=True)
    try:
        yield
    except:
        raise
    finally:
        cmds.currentTime(time, e=True, update=True)

@contextmanager
def undoable():
    """creates a new undoChunk, executes the code block, then closes the chunk"""
    cmds.undoInfo(openChunk=True)
    try:
        yield
    except:
        raise
    finally:
        cmds.undoInfo(closeChunk=True)

@contextmanager
def selection(new_selection=None):
    """selects the given item(s), yields control, then restores the previous
    selection state"""
    original_selection = cmds.ls(sl=True)
    cmds.select(new_selection, replace=True)
    try:
        yield
    except:
        raise
    finally:
        cmds.select(original_selection, replace=True)
