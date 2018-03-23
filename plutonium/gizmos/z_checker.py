# ----------------------------------------------------------------------------#
# ------------------------------------------------------------------ HEADER --#
"""
@copyright: 2018 Kludgeworks LLC

@description: code to run the zChecker gizmo (ARCHIVED TOOL)

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
import vfx_utils.plutonium.core.channels as channels

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def run():
    node = nuke.thisNode().input(0)
    this_node = nuke.thisNode()
    samples = channels.field_samples(node=node, channels=['Z.red', 'rgba.alpha'])
    non_zero_samples = [z for z, a in samples if a != 0.0]
    min_z = min(non_zero_samples)
    max_z = max(non_zero_samples)
    this_node['near'].setValue(min_z)
    this_node['far'].setValue(max_z)
