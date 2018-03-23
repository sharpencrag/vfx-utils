# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: tools to work with channels and layers in NUKE

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in

# internal
from vfx_utils.plutonium.core import decorators

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '2.3'
DEBUG_VERSION = '2.3.1'

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# -------------------------------------------------------- Layer Bundling -- #
@decorators.selected_node
def layers(node=None):
    """return a dict of layer:channels for a given node"""
    channels = node.channels()
    image_layers = sorted(list(set(c.split('.')[0] for c in channels)))
    return {lyr: [ch for ch in channels if ch.startswith((lyr + '.'))]
            for lyr in image_layers}

# -------------------------------------------------------------- Sampling -- #
@decorators.selected_node
def field_sample(node=None, channel='rgba.alpha', samples_x=100, samples_y=100,
                 return_field=False):
    """return scalar values from a grid of samples."""
    return field_samples(node, samples_x, samples_y, return_field, (channel,))

@decorators.selected_node
def field_samples(node=None, samples_x=100, samples_y=100, return_field=False,
                  channels=('rgba.red', 'rgba.green', 'rgba.blue', 'rgba.alpha')):
    """Generator function to return pixel values for the given channels
    in a grid of sample positions"""
    dx = node.width()
    dy = node.height()
    div_w = dx / samples_x
    div_h = dy / samples_y
    sample_positions = (((ix * div_w), (iy * div_h))
                        for ix in range(0, (samples_x + 1))
                        for iy in range(0, (samples_y + 1)))
    for x, y in sample_positions:
        rgb_value = [node.sample(channel, x, y) for channel in channels]
        if return_field:
            yield (rgb_value, (x, y))
        else:
            yield rgb_value
