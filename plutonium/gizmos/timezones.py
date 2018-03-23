# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: functions for the timeZones gizmo

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
from vfx_utils.plutonium.core import filters
import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.0'

# -------------------------------------------------------------------------- #
# --------------------------------------------------- LOGGING AND METRICS -- #
APP_NAME = 'gizmo_timeZones'

metrics.log_usage(APP_NAME)
# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

@decorators.this_node
def add_zone(node=None):
    """add a zone with corresponding nodes and controls to an rfxTimeZones node"""
    metrics.log_feature(APP_NAME, 'add zone')
    with node:
        # ------------------- Setup ---------------------------------- #
        color_choices = [(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1),
                         (1, 1, 0, 1), (0, 1, 1, 1), (1, 0, 1, 1)]
        zones = [int(n.name()[-1]) for n in filters.by_class(key='Input')
                 if 'zone' in n.name()]
        print "zones"
        zone_num = (max(zones) + 1) if zones else 1
        color_num = zone_num - 1
        prev_preview = nuke.toNode('zone_{}_stack'.format(color_num))
        color_num = color_num if color_num <= len(color_choices) else 0
        prefix = 'zone_{}'.format(zone_num)
        builder = nuke.toNode('builder_dot')
        start_position = crawl.up(builder)[0]
        switch = nuke.toNode('preview_zones')
        print "a"
        # ------------------- Create Nodes --------------------------- #
        copy_alpha = create.copy(['rgba.alpha'], ['rgba.alpha'])
        copy_alpha.setName('_'.join((prefix, 'copy')))
        const = nuke.nodes.Constant()
        const['color'].setValue(color_choices[color_num])
        const.setName('_'.join((prefix, 'const')))
        copy_to_const = nuke.nodes.Merge2(operation='mask')
        copy_to_const.setName('_'.join((prefix, 'color_copy')))
        preview_stack = nuke.nodes.Merge2(operation='plus')
        preview_stack.setName('_'.join((prefix, 'stack')))
        zone_over = nuke.nodes.Merge2(operation='matte')
        zone_over.setName('_'.join((prefix, 'merge')))
        zone_time = nuke.nodes.TimeOffset()
        zone_time.setName('_'.join((prefix, 'time')))
        zone_input = nuke.nodes.Input()
        zone_input['name'].setValue(prefix)
        print "b"

        # ------------------- Move Nodes into Position --------------- #
        move.under(zone_over, start_position, offset=120)
        move.left(copy_alpha, zone_over)
        move.under(copy_to_const, copy_alpha)
        move.left(const, copy_to_const)
        move.right(preview_stack, copy_to_const, offset=200)
        move.left(zone_input, copy_alpha)
        move.above(zone_time, copy_alpha)

        # ------------------- Inputs --------------------------------- #
        zone_over.setInput(0, start_position)
        zone_over.setInput(1, copy_alpha)
        copy_alpha.setInput(0, zone_time)
        copy_alpha.setInput(1, zone_input)
        zone_time.setInput(0, start_position)
        builder.setInput(0, zone_over)
        copy_to_const.setInput(0, const)
        copy_to_const.setInput(1, copy_alpha)
        preview_stack.setInput(0, prev_preview)
        preview_stack.setInput(1, copy_to_const)
        switch.setInput(1, preview_stack)

        # ------------------- Knobs and Expressions ------------------ #
        zone_control = nuke.Link_Knob('zone_{}_control'.format(zone_num))
        zone_control.setLink(zone_time.name() + '.time_offset')
        zone_control.setLabel(prefix + ' offset')
        zone_delete = nuke.PyScript_Knob('zone_{}_del'.format(zone_num))
        zone_delete.setLabel('delete')
        zone_delete.setValue('from vfx_utils.plutonium.gizmos import timezones\n'
                             'timezones.delete_zone(zone_num={})'
                             ''.format(zone_num))
        zone_color = nuke.Link_Knob('zone_{}_color'.format(zone_num))
        zone_color.setLabel('preview color')
        zone_color.clearFlag(nuke.STARTLINE)
        zone_color.setLink(const.name() + '.color')
        node.addKnob(zone_control)
        node.addKnob(zone_delete)
        node.addKnob(zone_color)

@decorators.this_node
def delete_zone(node=None, zone_num=1):
    """remove a zone, its related knobs, and its nodes and inputs"""
    metrics.log_feature(APP_NAME, 'delete zone')
    with node:
        prefix = 'zone_{}'.format(zone_num)
        node.setInput(zone_num, None)
        rm_nodes = [n for n in nuke.allNodes() if prefix in n.name()]
        for rmn in rm_nodes:
            nuke.delete(rmn)
        rm_knobs = [k for k in node.knobs() if prefix in k]
        for rmk in rm_knobs:
            node.removeKnob(node[rmk])

@decorators.this_node
def swap_zone(node=None, zone_num=1):
    pass
