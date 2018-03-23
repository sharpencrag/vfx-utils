# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: Code for running the layerViewer node

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
import vfx_utils.plutonium.core.filters as filters
import vfx_utils.plutonium.core.channels as channels

from vfx_utils.cutie.gadgets import ask
import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
APP_NAME = 'gizmo_layerViewer'

# --------------------------------------------------- Version Information -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'

# --------------------------------------------------------------- Logging -- #
logger = slog.Logger()
logger.formatter = slog.context_formatter(APP_NAME)

metrics.log_usage(APP_NAME)

# -------------------------------------------------------------------------- #
# ---------------------------------------------------- INTERNAL FUNCTIONS -- #
def exp_shuffle(layer_channels, label):
    """create an expression-based 'shuffle' node and hook it up to the
    contact sheet for the gizmo"""
    logger.debug('adding channel expr {0}', layer_channels)
    builder = nuke.toNode('builder_dot')
    sheet = nuke.toNode('sheet')
    expression = nuke.nodes.Expression()
    for i, ch in enumerate(reversed(layer_channels)):
        expression['expr{}'.format(i)].setValue(ch)
    label = make_label(label)
    expression.setInput(0, builder)
    label.setInput(0, expression)
    sheet.setInput(sheet.inputs(), label)

def make_label(label):
    """make a label node inline for the contact sheet"""
    logger.debug('adding label for {0}', label)
    t = nuke.nodes.Text()
    t['font'].setValue('/code/global/nuke/fonts/Vera.ttf')
    t['translate'].setValue((0, 10))
    t['size'].setValue(50)
    t['message'].setValue(label)
    t['disable'].setExpression('1 - parent.labels_chk')
    t['ramp'].setValue('linear')
    t['p1'].setValue((0, 50))
    t['p0'].setValue((0, 0))
    return t

def make(type_):
    """helper function to make a specific kind of node set"""
    clear_existing()
    type_()
    nuke.thisNode()['label'].setValue(type_.__name__.upper())

def one_layer(layername):
    """return a callable that creates a single exp_shuffle for the
    given layer"""
    def callback():
        layers = get_layers()
        chans = layers.get(layername, None)
        if not chans:
            nuke.message('no {} found!'.format(layername))
            return
        chans.sort()
        exp_shuffle(chans, layername)
    callback.__name__ = layername
    return callback

@metrics.feature_logging(APP_NAME, 'add all mattes')
def mattes():
    """add mattes to the contact sheet"""
    layers = get_layers()
    matte_chans = layers.get('matte', None)
    if not matte_chans:
        nuke.message('no mattes found!')
        return
    for chan in matte_chans:
        exp_shuffle((chan, chan, chan), chan.split('.')[-1])

@metrics.feature_logging(APP_NAME, 'add all channels')
def all():
    """add all layers to the contact sheet"""
    layers = get_layers()
    try:
        matte_layers = layers.pop('matte')
    except KeyError:
        pass
    else:
        for matte in matte_layers:
            exp_shuffle((matte, matte, matte), matte.split('.')[-1])
    for layer, chans in layers.iteritems():
            exp_shuffle(sorted(chans), layer)

@metrics.feature_logging(APP_NAME, 'search for channels')
def search_chans():
    """add a user selection of channels to the contact sheet"""
    layers = get_layers()
    try:
        layers.pop('matte')
    except KeyError:
        pass
    search_layers = ask.list_selection('search for layers:', layers.keys())
    if not search_layers:
        return
    clear_existing()
    for layer, chans in layers.iteritems():
        if layer in search_layers:
            exp_shuffle(sorted(chans), layer)

@metrics.feature_logging(APP_NAME, 'search for mattes')
def search_mattes():
    """add a user selection of matte channels to the contact sheet"""
    layers = get_layers()
    try:
        matte_layer = layers.pop('matte')
    except KeyError:
        raise
    search_layers = ask.list_selection('search for mattes:', matte_layer)
    if not search_layers:
        return
    clear_existing()
    for chan in search_layers:
        exp_shuffle((chan, chan, chan), chan.split('.')[-1])

@metrics.feature_logging(APP_NAME, 'clear all')
def clear_existing():
    """clear all nodes currently connected to the contact sheet"""
    node_types = ['Read', 'Merge2', 'Text', 'FrameHold', 'Expression']
    nodes = [n for n in filters.by_class_list(keys=node_types)
             if 'protect' not in n.knobs()]
    for node in nodes:
        nuke.delete(node)
    sheet = nuke.toNode('sheet')
    for i in range(1, sheet.inputs()):
        sheet.setInput(i, None)

    alpha_shuffle = nuke.toNode('alpha_shuffle_switch')
    if alpha_shuffle:
        alpha_shuffle['which'].setValue(0)
    nuke.thisNode()['label'].setValue('')


# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- HELPERS -- #
def get_layers():
    """return all channels organized by owning layers"""
    return channels.layers(nuke.thisNode().input(0))

def set_label(mode):
    """set the label of the main node to the chosen mode"""
    nuke.thisNode()['label'].setValue(mode)
