# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: tools related to selection states in the NUKE graph

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from contextlib import contextmanager

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------ CONTEXT MANAGERS -- #
@contextmanager
def current():
    currentSelection = nuke.selectedNodes()
    try:
        yield
    except:
        raise
    finally:
        replace(currentSelection)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def _selection(nodes, on_off):
    """internal function for setting selection"""
    try:
        for n in nodes:
            try:
                n['selected'].setValue(on_off)
            except:
                pass
    except TypeError:
        nodes['selected'].setValue(on_off)

def add(nodes):
    """set selection to ON for chosen nodes"""
    _selection(nodes, True)

def subtract(nodes):
    """set selection to OFF for chosen nodes"""
    _selection(nodes, False)

def replace(nodes):
    """replace current selection with the chosen nodes"""
    subtract(nuke.selectedNodes())
    add(nodes)

def deselect_all():
    """deselect all nodes"""
    subtract(nuke.selectedNodes())
