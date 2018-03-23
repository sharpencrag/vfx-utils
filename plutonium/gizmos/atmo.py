# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: code to run the Atmo gizmo

@author: Ed Whetstone

@applications: NUKE

@notes:

"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
from vfx_utils.plutonium.core import channels

import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'
APP_NAME = 'gizmo_Atmo'

metrics.log_usage(APP_NAME)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
@metrics.feature_logging('gizmo_rfxAtmo', 'auto z depth')
def auto_z_depth():
    node = nuke.thisNode()
    depth_channel = nuke.toNode('Depth_Copy')['from0'].value()
    field_samples = channels.field_sample(node=node, channel=depth_channel,
                                          return_field=True)
    field_samples = [fs for fs in field_samples if fs[0][0] > .1]

    def key(x):
        return x[0]

    max_value, max_field = max(field_samples, key=key)
    min_value, min_field = min(field_samples, key=key)
    node['near_value'].setValue(min_value)
    node['near_dropper'].setValue(min_field)
    node['far_value'].setValue(max_value)
    node['far_dropper'].setValue(max_field)


knob_changed = \
    """
if nuke.thisKnob().name() in ('near_dropper', 'far_dropper'):
    depth_channel = nuke.toNode('Depth_Copy')['from0'].value()
    with nuke.thisNode():
        # near_dropper
        knobs.update_drop_sample('near_dropper', 'near_value', depth_channel)

        # far_dropper
        knobs.update_drop_sample('far_dropper', 'far_value', depth_channel)

    """
