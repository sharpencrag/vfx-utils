# ---------------------------------------------------------------------------- #
# ------------------------------------------------------------------ HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: code to run the imageCompare gizmo

@author: Ed Whetstone

@applications: NUKE

"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# internal
import vfx_utils.omni.slog as slog
import vfx_utils.omni.metrics as metrics

# domain
import nuke

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '2.1'
DEBUG_VERSION = '2.1.1'
APP_NAME = "gizmo_imageCompare"
logger = slog.Logger()

metrics.log_usage(APP_NAME)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #
def update(knob):
    outmodes = {'Interleaved': 'interleaf_grp',
                'Dissolve': 'dissolve_grp'}
    knob_name = knob.name()
    node = nuke.thisNode()
    if knob_name == 'inputChange':
        for i in range(node.inputs()):
            fframe = node.input(i).firstFrame() if node.input(i) else 0
            lframe = node.input(i).lastFrame() if node.input(i) else 1
            if i == 0:
                node['one_frm_slider'].setRange(fframe, lframe)
            else:
                node['two_frm_slider'].setRange(fframe, lframe)
    elif knob_name == 'spotcheck_chk':
        node['spot'].setVisible(knob.value())
    elif knob_name == 'colorcheck_chk':
        node['color'].setVisible(knob.value())
    elif knob_name == 'outmode':
        hide_these_grps = outmodes.values()
        show_this_grp = outmodes.get(knob.value(), False)
        for grp in hide_these_grps:
            node[grp].setVisible(False)
        if show_this_grp:
            node[show_this_grp].setVisible(True)


# -------------------------------------------------------------------------- #
# -------------------------------------------------------- NODE FUNCTIONS -- #

# ----------------------------------------------------------- knobChanged -- #
knob_changed = ("#\n"
                "from vfx_utils.plutonium.gizmos import compare\n"
                "compare.update(nuke.thisKnob())\n#\n")
