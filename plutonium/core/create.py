# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: tools for creating nodes programmatically.

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------- Version Information -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'


# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# --------------------------------------------------- Basic Node Creation -- #
def node(node_class='NoOp', *args, **kwargs):
    """Make a node of the given class. By default, creates a NoOp node."""
    n = getattr(nuke.nodes, node_class)(*args, **kwargs)
    return n

# ------------------- Merges ----------------------------------------------- #
def plus():
    n = node('Merge2')
    n['operation'].setValue('plus')
    return n

def add_alphas():
    n = node('Merge2')
    n['operation'].setValue('plus')
    for knob in ('output', 'Achannels', 'Bchannels'):
        n[knob].setValue('alpha')
    return n

# ------------------- Copies ----------------------------------------------- #
def copy(from_channels=[], to_channels=[]):
    n = node('Copy')
    for i, channel_set in enumerate(zip(from_channels, to_channels)):
        i_str = str(i)
        from_ = 'from{}'.format(i_str)
        to_ = 'to{}'.format(i_str)
        n[from_].setValue(channel_set[0])
        n[to_].setValue(channel_set[1])
    return n
