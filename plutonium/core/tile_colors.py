# --------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER --- #
"""
@copyright: 2018 Kludgeworks LLC

@description: NUKE tile colors are annoying.  This module provides some
              basic functionality for translating between rgb, hex, and
              the tile colors used by NUKE (integer conversions of hex)

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #

# --------------------------------------------------------------- Imports -- #
from vfx_utils.omni.colors import Color

# ------------------------------------------------------------- Functions -- #
def hex_to_int(hexa):
    return int(hexa, 16)

def assign_tile_color(node, rgb):
    tile_color = Color.from_rgb_float(rgb)
    final_color = hex_to_int(tile_color.hex + 'FF')
    node['tile_color'].setValue(final_color)
