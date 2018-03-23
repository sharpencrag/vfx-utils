# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: filter set for NUKE nodes

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
from vfx_utils.plutonium.core import decorators

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.1'

# -- Node Types ------------------------------------------------------------ #
SHAPES = ('Ramp', 'Roto', 'RotoPaint', 'Radial', 'Rectangle')

COLOR_CHANGES = ('Grade', 'Grade2', 'ColorCorrect', 'HueCorrect', 'HueShift',
                 'Saturation')

JOINERS = ('Merge', 'Merge2', 'Copy', 'LightWrap', 'ShuffleCopy',
           'ChannelMerge', 'AddMix', 'Keymix', 'CopyBBox', 'CopyRectangle',
           'Dissolve', 'MergeExpression', 'Blend', 'DeepMerge')

MASKED_JOINS = ('Merge', 'Merge2', 'Copy', 'ChannelMerge', 'Keymix',
                'Dissolve', 'MergeExpression', 'Blend')

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ------------------------------------------------------- Generic Filters -- #
@decorators.all_nodes
def simple_filter(nodes=None, key=None, strategy=None):
    """filter node list by applying 'strategy', a callable which returns a
    string or boolean"""
    return [n for n in nodes if strategy(n, key)]

@decorators.all_nodes
def by_name(nodes=None, key=None):
    """search for nodes by name"""
    return [n for n in nodes if key.lower() in n.name().lower()]

@decorators.all_nodes
def by_class(nodes=None, key=None):
    """search for nodes by class"""
    return [n for n in nodes if key == n.Class()]

@decorators.all_nodes
def by_class_list(nodes=None, keys=None):
    """search for nodes within a list of classes"""
    return [n for n in nodes if n.Class() in keys]

@decorators.all_nodes
def reads(nodes=None):
    """return reads from list"""
    return [n for n in nodes if n.Class() == 'Read']

@decorators.all_nodes
def by_errors(nodes=None):
    """return nodes which contain errors"""
    return [n for n in nodes if n.hasError()]

@decorators.all_nodes
def by_knob_exists(nodes=None, key=None):
    """search for nodes which contain a certain knob name"""
    return [n for n in nodes if key in n.knobs()]

@decorators.all_nodes
def by_knob_value(nodes=None, knob=None, key=None, cmp=None):
    """NOT IMPLEMENTED!"""
    raise NotImplementedError

@decorators.all_nodes
def redundant_reads(nodes=None):
    """returns all read nodes with duplicate file paths"""
    reads_w_paths = [(n, n['file'].value()) for n in reads(nodes)]
    # isolate paths for counting purposes
    paths = [p[1] for p in reads_w_paths]
    return [r[0] for r in reads_w_paths if paths.count(r[1]) > 1]


# -------------------------------------------------------- Stereo Filters -- #
@decorators.all_nodes
def static_reads(nodes=None):
    """return all reads without stereo variables"""
    return [r for r in reads(nodes) if '%v' not in r['file']]

@decorators.all_nodes
def stereo_status(nodes=None):
    """return all nodes with the 'v' icon, indicating stereo status"""
    return [n for n in nodes if "{0:b}".format(int(n['indicators'].value()))[0]]

# ------------------------------------------------- Node Category Filters -- #
@decorators.all_nodes
def color_changes(nodes=None):
    """list of nodes which are color manipulations, like grades and CCs"""
    return by_class_list(nodes=nodes, keys=COLOR_CHANGES)

@decorators.all_nodes
def shapes(nodes=None):
    """list all nodes that are 'shapes', including rotos and ramps"""
    return by_class_list(nodes=nodes, keys=SHAPES)

@decorators.all_nodes
def joiners(nodes=None):
    """list all nodes which combine two streams via a and b pipes"""
    return by_class_list(nodes=nodes, keys=JOINERS)
