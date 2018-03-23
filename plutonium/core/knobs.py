# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: custom knob types and controls for NUKE

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
VERSION = '3.0'
DEBUG_VERSION = '3.1.0'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# ---------------------------------------------------------- KNOB HELPERS -- #
# NOT IMPLEMENTED
@decorators.this_node
def move(node=None, knob=None, direction='up'):
    raise NotImplementedError

# --------------------------------------------------------- DROPPER KNOBS -- #
def drop_sample(name, knob_type, channel=None, node=None):
    """create a set of paired knobs, a floating point value and a
    droppable 2d position to drive it.  The returning value will either
    be a scalar or an rgb value.

    knob_type will either be an XYZ_Knob for color values, or an
    Array_Knob for scalars.  Use the add_* functions below to add knobs
    to a particular node."""

    # the naming on these knobs is tightly controlled, because we'll be
    # driving knobChanged scripts from here, using the naming convention.
    controlled_knob = knob_type('_'.join((name, 'value')))
    controlled_knob.setLabel(name)
    # the actual dropper knob, which users will use to select points in
    # 2D space.
    control_knob = nuke.XY_Knob('_'.join((name, 'dropper')))
    control_knob.setLabel(' :: ')
    # put the control knob on its own line
    controlled_knob.setFlag(nuke.STARTLINE)
    control_knob.clearFlag(nuke.STARTLINE)

    # add this script to the knobChanged for the node
    current_script = node['knobChanged'].getText()
    new_script = '{}\n'
    if 'import knobs' not in current_script:
        new_script += 'from vfx_utils.plutonium.core import knobs\n'
    else:
        new_script += 'knobs.update_drop_sample(\'{0}\', \'{1}\', \'{2}\')\n'

    # format the script with the correct knob names
    new_script = new_script.format(control_knob.name(), controlled_knob.name(),
                                   channel)
    node.addKnob(controlled_knob)
    node.addKnob(control_knob)
    node['knobChanged'].setValue('\n'.join((current_script, new_script)))

@decorators.selected_node
def add_color_drop_knob(name, channel='rgba', node=None):
    """add a set of knobs to easily dropper color or xyz values"""
    drop_sample(name, nuke.XYZ_Knob, channel=channel, node=node)

@decorators.selected_node
def add_scalar_drop_knob(name, channel='rgba.alpha', node=None):
    """add a set of knobs to easily dropper scalar values"""
    drop_sample(name, nuke.Array_Knob, channel=channel, node=node)

def update_drop_sample(control, controlled, channel):
    """this function is called every time the node's knobChanged callback is
    fired.  If the knob that's changed matches the dropper name, then handle
    updating the dropped value. """
    knob = nuke.thisKnob()
    if not knob:
        return
    if knob.name() in (control,):
        node = nuke.thisNode()
        if not node:
            return
        input_node = node.input(0)
        # if the input node does not exist (i.e. on shot opening)
        # just return without any side-effects
        if not input_node:
            return
        x, y = node[control].value()
        if isinstance(node[controlled], nuke.XYZ_Knob):
            rgb = ('red', 'green', 'blue')
            rgb_samples = [input_node.sample('.'.join((channel, c)), x, y)
                           for c in rgb]
            print rgb_samples
            if any(rgb_samples):
                node[controlled].setValue(rgb_samples)
            else:
                pass
        elif isinstance(node[controlled], nuke.Array_Knob):
            sample_val = node.sample(channel, x, y)
            if sample_val:
                node[controlled].setValue(sample_val)
            else:
                pass
        else:
            pass
    else:
        pass

@decorators.selected_node
def clear_drop(control_name, node=None):
    """clears out dropper knobs and related code"""
    clear_drop_knobs(control_name, node)
    clear_drop_commands(control_name, node)

@decorators.selected_node
def clear_drop_knobs(control_name, node=None):
    """clears out knobs related to the given dropper control"""
    node.removeKnob(node['_'.join((control_name, 'value'))])
    node.removeKnob(node['_'.join((control_name, 'dropper'))])

@decorators.selected_node
def clear_drop_commands(control_name, node=None):
    """clear out code related to the given dropper control"""
    change_script = node['knobChanged'].value().split('\n')
    for i, line in enumerate(change_script):
        if line.startswith('#{}'.format(control_name)):
            to_remove = change_script[i:i + 4]
            for r in to_remove:
                change_script.remove(r)
    node['knobChanged'].setValue('\n'.join(change_script))
