# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: tools for creating nodes programmatically.

@author: Ed Whetstone

@applications: NUKE
"""

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #
import nuke
import vfx_utils.plutonium.core.move as move
import vfx_utils.plutonium.core.pos as pos
import vfx_utils.plutonium.core.tile_colors as tile_colors

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
DEFAULT_BD_COLOR = (.325, .325, .325)

# --------------------------------------------------- Version Information -- #
VERSION = '1.0'
DEBUG_VERSION = '1.0.9'

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- CLASSES -- #
class NodeGroup():
    def __init__(self, nodes=None):
        self.nodes = nodes if nodes else []
        self.pos = pos.PositionGroup(self.nodes)
        self.move = move.MovementGroup(self.nodes)

    def __getitem__(self, item):
        return KnobGroup(item)

    def backdrop(self, label='', offset=20, label_size=20):
        """add a backdrop to this group of nodes"""
        # ------------------- Create Base Backdrop ------------------------- #
        create_position = self.pos.corners['top-left']
        label_buffer = label_size + (label_size / 2)
        node_kwargs = \
            {'xpos': create_position[0] - offset,
             'ypos': create_position[1] - offset - label_buffer,
             'bdwidth': self.pos.width + (offset * 2),
             'bdheight': self.pos.height + (offset * 2) + label_buffer,
             'label': label,
             'note_font_size': label_size}
        bdnode = nuke.nodes.BackdropNode(**node_kwargs)
        tile_colors.assign_tile_color(bdnode, DEFAULT_BD_COLOR)

        # ------------------- Lift Contained Backdrops --------------------- #
        contained_bds = [bd for bd in self.nodes
                         if bd.Class() == 'BackdropNode']
        for bd in contained_bds:
            bd['z_order'].setValue(bd['z_order'].value() + 1)

        # ------------------- Add Backdrop to Group ------------------------ #
        self.nodes.append(bdnode)
        return bdnode

class KnobGroup():
    def __init__(self, nodes, knob_name):
        self.knobs = [n[knob_name] for n in nodes
                      if knob_name in n.allKnobs()]

    def setValue(self, value):
        for k in self.knobs:
            k.setValue(value)

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# --------------------------------------------------- Basic Node Creation -- #
def create_node(node_class='NoOp', *args, **kwargs):
    """Make a node of the given class. By default, creates a NoOp node."""
    n = getattr(nuke.nodes, node_class)(*args, **kwargs)
    return n

# ------------------- Merges ----------------------------------------------- #
def plus():
    n = create_node('Merge2', operation='plus')
    return n

def add_alphas():
    n = plus()
    for knob in ('output', 'Achannels', 'Bchannels'):
        n[knob].setValue('alpha')
    return n

# ------------------- Copies ----------------------------------------------- #
def copy(from_channels=[], to_channels=[]):
    n = create_node('Copy')
    for i, channel_set in enumerate(zip(from_channels, to_channels)):
        i_str = str(i)
        from_ = 'from{}'.format(i_str)
        to_ = 'to{}'.format(i_str)
        n[from_].setValue(channel_set[0])
        n[to_].setValue(channel_set[1])
    return n

# ------------------- Contact Sheets --------------------------------------- #
def auto_contact_sheet(inputs=[], offset=move.align_offset):
    n = nuke.nodes.ContactSheet(roworder='TopBottom', gap=0)
    scale_knob = nuke.Double_Knob('scale', 'Scale:')
    scale_knob.setValue(0.5)
    n.addKnob(scale_knob)
    n['width'].setExpression('input.width * columns * scale')
    n['height'].setExpression('input.height * rows * scale')
    n['rows'].setExpression('ceil(inputs / columns)')
    n['columns'].setValue(min((7, len(inputs))))
    for i, inp in enumerate(inputs):
        n.setInput(i, inp)
    input_group = pos.PositionGroup(inputs)
    cen_x, cen_y = input_group.center
    move.center_to(n, cen_x, cen_y)
    print input_group.center
    move.nudge(n, x=0, y=((input_group.height / 2) + offset))
    return n
