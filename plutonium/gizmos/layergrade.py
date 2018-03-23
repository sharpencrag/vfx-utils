# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: Code for running the layerGrade gizmo

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
import vfx_utils.plutonium.core.channels as channels
import vfx_utils.plutonium.core.crawl as crawl
import vfx_utils.plutonium.core.move as move
import vfx_utils.plutonium.core.decorators as decorators

import vfx_utils.cutie.gadgets.ask as ask
from vfx_utils.omni.string_utils import djoin

import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
APP_NAME = "gizmo_layerGrade"

# ---------------------------------------------------------- Version Info -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'

# ----------------------------------------------------- Logging / Metrics -- #
logger = slog.Logger()
logger.formatter = slog.context_formatter(APP_NAME)

metrics.log_usage(APP_NAME)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
@decorators.this_node
def add_light(_thru=False, node=None, light_selection='none'):
    """Add a light to the rfxGrade gizmo"""
    logger.debug('adding light {0}', light_selection)
    if _thru:
        metrics.log_feature(APP_NAME, 'add light')
    # ------------------- Setup -------------------------------------- #
    # builder node start
    builder_dot = nuke.toNode('builder_dot')
    # bottom of plus-stack
    plus_stack = crawl.up(builder_dot)[0]
    # copy node start
    copy_dot = nuke.toNode('copy_dot')
    # bottom of copy stack
    copy_stack = crawl.up(copy_dot)[0]
    # copy graded lights back into channels
    graded_lights = nuke.toNode('copyfrom_dot')

    # ------------------- Add Nodes ---------------------------------- #
    # add light to the plus stack
    added_light = nuke.nodes.Merge2(output='rgb', operation='plus')
    light_name = added_light.name()
    # move and connect
    move.under(added_light, plus_stack)
    added_light.setInput(0, plus_stack)
    added_light.setInput(1, plus_stack)
    builder_dot.setInput(0, added_light)

    # add light to the copy stack
    copied_light = nuke.nodes.Merge2(Bchannels='none', operation='copy')
    copied_light['Achannels'].setExpression("{}.Achannels".format(light_name))
    copied_light['output'].setExpression("{}.Achannels".format(light_name))
    copied_light['disable'].setExpression("{}.disable".format(light_name))
    # move and connect
    move.under(copied_light, copy_stack)
    copied_light.setInput(0, copy_stack)
    copied_light.setInput(1, graded_lights)
    copy_dot.setInput(0, copied_light)

    # ------------------- Knobs -------------------------------------- #
    link = nuke.Link_Knob((added_light.name() + '_link'), 'light')
    link.clearFlag(nuke.STARTLINE)
    link.makeLink(added_light.name(), 'Achannels')
    disableLink = nuke.Link_Knob((added_light.name() + '_disable_lnk'), 'mute')
    disableLink.clearFlag(nuke.STARTLINE)
    disableLink.makeLink(added_light.name(), 'disable')

    remove_button = nuke.PyScript_Knob((added_light.name() + "_rmb"), 'X')
    remove_button.setValue("import vfx_utils.plutonium.gizmos.rfx_grade as rfx_grade\n"
                           "rfx_grade.remove_light('{}', '{}')"
                           "".format(light_name, copied_light.name()))
    remove_button.setFlag(nuke.STARTLINE)
    node.addKnob(remove_button)
    node.addKnob(link)
    node.addKnob(disableLink)
    # due to a glitch in the way channels are interpreted by the link-knob,
    # this value must be set after the knob is created.
    added_light['Achannels'].setValue(light_selection)
    return added_light

@metrics.feature_logging(APP_NAME, 'remove light')
@decorators.this_node
def remove_light(added_light, copied_light, node=None):
    node.removeKnob(node.knobs()[(added_light + '_disable_lnk')])
    node.removeKnob(node.knobs()[(added_light + '_link')])
    node.removeKnob(node.knobs()[(added_light + '_rmb')])
    nuke.delete(nuke.toNode(added_light))
    nuke.delete(nuke.toNode(copied_light))

@metrics.feature_logging(APP_NAME, 'add from search')
@decorators.this_node
def add_from_search(channelsInput=None, node=None):
    """add lights from a user selection"""
    layers = channels.layers(node=node).keys()
    layers.sort()
    layer_choices = ask.list_selection('Pick Layers:', layers)
    # add layers
    existing_chans = existing_channels()
    for layer in layer_choices:
        if layer not in existing_chans:
            add_light(_thru=True, light_selection=layer)

@metrics.feature_logging(APP_NAME, 'add from sample')
@decorators.this_node
def add_from_sample(node=None):
    """add lights from a given sampler position."""
    xpos, ypos = node['sample_pos'].value()
    layers = channels.layers(node=node).keys()
    rgb_names = ('red', 'green', 'blue')
    rgbsum = sum([node.sample(djoin('rgb', ch)) for ch in rgb_names])
    # Get Layer Contributions
    contribs = []
    for layer in layers:
        chsum = sum([node.sample(djoin(layer, ch)) for ch in rgb_names])
        ratio = (chsum / rgbsum) * 100
        if ratio > float(0.5):
            contribs.append(layer)
    contribs = ask.list_selection('Choose Layers:', contribs)
    # add layers
    existing_chans = existing_channels()
    for layer in contribs:
        if layer not in existing_chans:
            add_light(_thru=True, light_selection=layer)

@decorators.this_node
def existing_channels(node=None):
    """return the layers which have already been added to the gizmo"""
    channel_knobs = [node[k].value() for k in node.knobs() if '_link' in k]
    return channel_knobs

@decorators.this_node
def make_matte(node=None, method='multi'):
    """add a matte node with proper connections to the gizmo"""
    with crawl.parent(node):
        matte = None
        if method == 'multi':
            metrics.log_feature(APP_NAME, 'make multimatte')
            matte = nuke.nodes.rfxMultiMatte()
        elif method == 'eye':
            metrics.log_feature(APP_NAME, 'make eyematte')
            nuke.message('the eyeMatte node is currently not in use')
        elif method == 'p':
            metrics.log_feature(APP_NAME, 'make pointmatte')
            matte = nuke.nodes.rfxPointMatte()
        else:
            pass
        if not matte:
            return
        dot = nuke.nodes.Dot()
        node_input = node.input(0)
        move.above(dot, node)
        move.left(matte, node)
        matte.setInput(0, dot)
        node.setInput(1, matte)
        node.setInput(0, dot)
        if node_input:
            dot.setInput(0, node_input)
        node['maskChannelMask'].setValue('rgba.alpha')
        node.knobs()['maskChannelMask'].setVisible(True)
        node.knobs()['maskChannelInput'].setVisible(False)
        node['maskChannelInput'].setValue('none')
        return matte

@metrics.feature_logging(APP_NAME, 'clear muted')
@decorators.this_node
def clear_muted(node=None):
    """clear any layers which are currently disabled in the interface"""
    rmbs = [r for r in nuke.thisNode().knobs() if '_rmb' in r]
    for r in rmbs:
        disable_chk = r[:-4] + '_disable_lnk'
        if node[disable_chk].getValue():
            nuke.thisNode()[r].execute()
