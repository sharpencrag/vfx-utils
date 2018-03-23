# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: functions for the pointMatte gizmo

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
from vfx_utils.plutonium.core import decorators
from vfx_utils.plutonium.core import crawl
from vfx_utils.plutonium.core import move
from vfx_utils.plutonium.core import filters

import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '3.1'
DEBUG_VERSION = '3.1.1'

APP_NAME = "gizmo_pointMatte"

metrics.log_usage(APP_NAME)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
@decorators.this_node
def add_point(node=None):
    """add a pointmatte to the gizmo"""
    with node:

        # ------------------- Setup ---------------------------------- #
        builder = nuke.toNode('builder_dot')
        start_position = crawl.up(builder)[0]
        point_nodes = [int(n.name()[-1]) for n
                       in filters.by_class(key='pointMatte')]
        point_num = (max(point_nodes) + 1) if point_nodes else 1
        prefix = 'point_{}'.format(point_num)

        # ------------------- Create Nodes --------------------------- #
        point_matte = nuke.nodes.rfxPointMatte()
        point_matte.setName(prefix)
        merge_points = nuke.nodes.Merge2(operation='plus')
        merge_points.setName(prefix + '_merge')

        # ------------------- Move Into Position --------------------- #
        move.left(point_matte, start_position)
        move.under(merge_points, start_position)

        # ------------------- Set Up Connections --------------------- #
        point_matte.setInput(0, start_position)
        merge_points.setInput(0, start_position)
        merge_points.setInput(1, point_matte)
        builder.setInput(0, merge_points)

        # ------------------- Knobs and Expressions ------------------ #
        knoblist = ['hr', 'Position_value', 'Position_dropper', 'type', 'hr',
                    'rotate_TXT', 'xSlider', 'ySlider', 'zSlider', 'hr',
                    'scale_TXT', 'overall_scale', 'scale_x', 'scale_y',
                    'scale_z', 'hr', 'feather', 'hr', 'Gamma1_value', 'hr',
                    'massage', 'hr']
        new_tab = nuke.Tab_Knob('_'.join((prefix, 'controls')))
        node.addKnob(new_tab)
        merge_op_knob = nuke.Link_Knob('_'.join((prefix, 'merge_op')))
        merge_op_knob.setLink(merge_points.name() + '.operation')
        merge_op_knob.setLabel('operation')
        node.addKnob(merge_op_knob)
        merge_mix_knob = nuke.Link_Knob('_'.join((prefix, 'merge_mix')))
        merge_mix_knob.setLink(merge_points.name() + '.mix')
        merge_mix_knob.setLabel('mix')
        node.addKnob(merge_mix_knob)
        for k in knoblist:
            if k == 'hr':
                knob = nuke.Text_Knob('')
                knob.setName('_'.join((prefix, 'hr')))
                knob.setLabel('')
            else:
                knob = nuke.Link_Knob('_'.join((prefix, k)))
                knob.setLink('.'.join((point_matte.name(), k)))
                knob.setLabel(point_matte[k].label())
                if k == 'massage':
                    knob.setLabel(k)
            node.addKnob(knob)
        del_button = nuke.PyScript_Knob('_'.join((prefix, 'del')))
        del_button.setLabel('Remove Point')
        del_button.setValue('from vfx_utils.plutonium.gizmos import pointmatte\n'
                            'pointmatte.delete_point(point_num={})\n'
                            ''.format(point_num))
        node.addKnob(del_button)

@decorators.this_node
def delete_point(node=None, point_num=1):
    """remove a point that was previously added"""
    with node:
        prefix = 'point_{}'.format(point_num)
        rm_nodes = [n for n in nuke.allNodes() if prefix in n.name()]
        for rmn in rm_nodes:
            nuke.delete(rmn)
        rm_knobs = [knob for knob in node.allKnobs() if prefix in knob.name()]
        for rmk in rm_knobs:
            node.removeKnob(rmk)

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
