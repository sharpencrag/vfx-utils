# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: code to run multiMatte

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
from vfx_utils.plutonium.core import decorators
from vfx_utils.plutonium.core import create
from vfx_utils.plutonium.core import crawl
from vfx_utils.plutonium.core import move

import vfx_utils.cutie.gadgets.ask as ask
from vfx_utils.omni.string_utils import ujoin, djoin

import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
APP_NAME = 'gizmo_multiMatte'

# --------------------------------------------------- Version Information -- #
VERSION = '4.1'
DEBUG_VERSION = '4.1.1'

# --------------------------------------------------------------- Logging -- #
logger = slog.Logger()
logger.formatter = slog.context_formatter(APP_NAME)

metrics.log_usage(APP_NAME)
# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# -------------------------------------------------------- Matte Controls -- #
@decorators.this_node
def add_matte(node=None, matte_layer=None):
    """adds the required nodes and connections for a new matte in
    multimatte gizmo"""
    logger.debug('adding matte: {}'.format(matte_layer))

    # ------------------- Setup -------------------------------------- #
    # Get information required to build the nodes...
    builder = nuke.toNode('builder_dot')
    start_position = crawl.up(builder)[0]

    # ------------------- Build Nodes -------------------------------- #
    # Make the Copy Node
    copy_channel = matte_layer
    to_channel = 'rgba.alpha'
    copy_matte = create.copy([copy_channel], [to_channel])
    copy_matte.setInput(1, start_position)
    # Make the Plus Node
    alpha_plus = create.add_alphas()

    # ------------------- Inputs and Placement ----------------------- #
    alpha_plus.setInput(1, copy_matte)
    alpha_plus.setInput(0, start_position)
    builder.setInput(0, alpha_plus)
    alpha_plus.setXYpos(0, 0)
    move.under(alpha_plus, start_position)
    move.left(copy_matte, alpha_plus, offset=50)

    # ------------------- Knobs -------------------------------------- #
    # text label
    text_label = nuke.Text_Knob(ujoin(alpha_plus.name(), 'lbl'), '')
    text_label.clearFlag(nuke.STARTLINE)
    text_label.clearFlag(nuke.ENDLINE)
    text_label.setValue(matte_layer[6:])

    # mix control
    mix_link = nuke.Link_Knob(ujoin(alpha_plus.name(), 'mix'), ' ')
    mix_link.clearFlag(nuke.STARTLINE)
    mix_link.makeLink(alpha_plus.name(), 'mix')

    # merge operation
    op_link = nuke.Link_Knob(ujoin(alpha_plus.name(), 'op'), '')
    op_link.clearFlag(nuke.STARTLINE)
    op_link.makeLink(alpha_plus.name(), 'operation')

    # remove this matte
    remove_btn = nuke.PyScript_Knob(ujoin(alpha_plus.name(), 'rm'), 'X')
    rm_script = ('from vfx_utils.plutonium.gizmos import multimatte'
                 '\nmultimatte.remove_matte("{}", "{}")')
    rm_formatted = rm_script.format(alpha_plus.name(),
                                    copy_matte.name())
    remove_btn.setValue(rm_formatted)
    remove_btn.setFlag(nuke.STARTLINE)

    # add knobs to interface
    node.addKnob(remove_btn)
    node.addKnob(op_link)
    node.addKnob(text_label)
    node.addKnob(mix_link)
    mix_link.clearFlag(nuke.STARTLINE)

@metrics.feature_logging(APP_NAME, 'remove matte')
@decorators.this_node
def remove_matte(alpha_plus, copy_matte, node=None):
    """remove a matte from the multimatte gizmo"""
    logger.debug('removing matte {0}', alpha_plus)
    with node:
        for knob_type in ('lbl', 'mix', 'op', 'rm'):
            node.removeKnob(node.knobs()[ujoin(alpha_plus, knob_type)])
        nuke.delete(nuke.toNode(alpha_plus))
        nuke.delete(nuke.toNode(copy_matte))

def existing_mattes(node=None):
    labels = [node[k].value() for k in node.knobs() if k.endswith('lbl')]
    return [djoin('matte', label) for label in labels]

@metrics.feature_logging(APP_NAME, 'clear all')
@decorators.this_node
def clear_all(node=None):
    """clear all nodes and knobs created by multimatte"""
    logger.debug('removing all mattes')
    with node:
        rm_knobs = [k for k in node.knobs() if k.endswith('_rm')]
        for rmk in rm_knobs:
            node[rmk].execute()

@metrics.feature_logging(APP_NAME, 'add from list')
@decorators.this_node
def add_from_list(node=None):
    """given a user selection of matte channels, add them all to the gizmo"""
    logger.debug('adding mattes from list')
    chans = _get_mat_channels(node)
    selected = _get_mat_channel_selection(node, chans)
    if selected:
        for m in selected:
            if m not in existing_mattes(node):
                add_matte(node, m)
    else:
        pass

@metrics.feature_logging(APP_NAME, 'add from sample')
@decorators.this_node
def add_from_sample(node=None):
    """add a matte layer from a sampled value at the knob position"""
    logger.debug('adding mattes from sample')
    chans = _get_mat_channels(node)
    x, y = node['sample_pos'].value()
    choices = [ch for ch in chans if sample_returns(node, ch, x, y)]
    if len(choices) < 2:
        selected = choices
    else:
        selected = _get_mat_channel_selection(node, choices)
    if selected:
        for m in selected:
            if m not in existing_mattes(node):
                add_matte(node, m)
    else:
        pass

def sample_returns(node, chan, x, y):
    """if the channel has any data at the given coordinate, return True"""
    if node.sample(chan, x, y):
        return True
    else:
        return False

def _get_mat_channels(node):
    """internal function to return all matte.* channels"""
    return [chan for chan in node.channels() if chan.startswith('matte.')]

def _get_mat_channel_selection(node, chans):
    """internal function to retrieve a matte layer from user selection"""
    layers_truncated = [lyr[6:] for lyr in chans]
    selected = ask.list_selection('Matte Channel:', layers_truncated)
    if selected:
        return [djoin('matte', s) for s in selected]
    else:
        return None
