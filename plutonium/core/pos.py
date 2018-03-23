# -------------------------------------------------------------------------- #
# ---------------------------------------------------------------- HEADER -- #
"""
@copyright: 2018 Kludgeworks LLC

@description: Convenience functions relating to node positions on the graph

@author: Ed Whetstone

@applications: NUKE
"""
# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- IMPORTS -- #

# built-in
from math import sqrt

# internal
from vfx_utils.plutonium.core import utils

# domain
import nuke

# third party
from PyQt4.QtGui import QFont, QFontMetrics

# -------------------------------------------------------------------------- #
# --------------------------------------------------------------- GLOBALS -- #
VERSION = '1.1'
DEBUG_VERSION = '1.1.5'

# ------------------- Class Categories ------------------------------------- #
# These are used when determining the proper height of nodes.
# Usually, we would use screenHeight to return the value, but this causes
# alignment problems. This is a known bug in NUKE through and including
# NUKE 9.0v5

DOTS = ['Dot']
THREE_DS = ['Camera', 'Camera2', 'Scene', 'Light2', 'Light', 'Environment',
            'Spotlight', 'DirectLight', 'Axis', 'Axis2']
NOTES = ['BackdropNode', 'StickyNote']
AUTO_POSTAGES = ['Read', 'Constant', 'Checkerboard', 'ColorBars', 'ColorWheel']

class PositionGroup(object):
    def __init__(self, nodes):
        self.nodes = nodes

    @property
    def bounding_box(self):
        return group_bounding_box(self.nodes)

    @property
    def corners(self):
        bbox = self.bounding_box
        return {'top-left': (bbox[0], bbox[1]),
                'top-right': (bbox[2], bbox[1]),
                'bottom-left': (bbox[0], bbox[3]),
                'bottom-right': (bbox[2], bbox[3])
                }

    def _dimension(self, bound_max_index, bound_min_index):
        bbox = self.bounding_box
        return bbox[bound_max_index] - bbox[bound_min_index]

    @property
    def width(self):
        return self._dimension(2, 0)

    @property
    def height(self):
        return self._dimension(3, 1)

    @property
    def center(self):
        bbox = self.bounding_box
        avg_x = (bbox[0] + bbox[2]) / 2
        avg_y = (bbox[1] + bbox[3]) / 2
        return avg_x, avg_y

# -------------------------------------------------------------------------- #
# ------------------------------------------------------------- FUNCTIONS -- #

# -------------------------------------------------------- Node Positions -- #
def xy(node=None):
    """return the (x, y) position of the node in the graph"""
    return [getattr(node, axis)() for axis in ('xpos', 'ypos')]


def average(nodes=None):
    """get the average position of any number of nodes"""
    axes = ('xpos', 'ypos')
    num_nodes = len(nodes)
    avg = [(sum([n[x].value() for n in nodes]) / num_nodes) for x in axes]
    return avg


def center(node=None):
    """get the true center of the node"""
    min_x, min_y = xy(node)
    cen_x = min_x + (true_width(node) / 2)
    cen_y = min_y + (true_height(node) / 2)
    return (cen_x, cen_y)


def average_centered(nodes=None):
    """get the average position of the centers of any number of nodes"""
    num_nodes = len(nodes)
    avg = [(sum(center(n)[i] for n in nodes) / num_nodes) for i in range(2)]
    return avg


def mindread(nodes=None):
    """get the axis of greatest eccentricity of the bounding box of a set
    of nodes
    """
    bbox = group_bounding_box(nodes=nodes)
    if bbox[0] > bbox[1]:
        return 'x'
    else:
        return 'y'


# ------------------------------------------------------------ Node Sizes -- #
def bounding_box(node=None):
    """get the outer bounds of the given node"""
    min_x, min_y = xy(node)
    max_x, max_y = (min_x + true_width(node), min_y + true_height(node))
    return (min_x, min_y, max_x, max_y)


def group_bounding_box(nodes=None):
    """Get the outer bounds of the given nodes"""
    if not nodes:
        return (0, 0, 0, 0)
    bboxes = [bounding_box(n) for n in nodes]
    min_x, min_y = (min(b[0] for b in bboxes), min(b[1] for b in bboxes))
    max_x, max_y = (max(b[2] for b in bboxes), max(b[3] for b in bboxes))
    return (min_x, min_y, max_x, max_y)


def true_height(node=None):
    """Calculates the UI height for all node types, due to a bug in NUKE
    which evaluates to zero for height upon node creation or in non-UI
    modes. By convention, height and width are represented by h and w
    """
    node_class = node.Class()
    # ------------------- Size Determined by Prefs ------------------------- #
    # the UI Prefs determine the size of dots directly:
    if node_class in DOTS:
        return utils.pref('dot_node_scale') * 12
    # TileWidth is the driving preference for round "3D" nodes
    elif node_class in THREE_DS:
        tile_w = utils.pref('TileWidth')
        three_d_w = int(float(tile_w) * (3.0 / 4.0))
        three_d_h = three_d_w if three_d_w % 2 == 0 else (three_d_w + 1)
        return three_d_h

    # ------------------- Size Determined by Labels ------------------------ #
    # All other nodes can be determined via screenheight + labels
    screen_h = node.screenHeight()
    # If the node is a note-type, screenheight will suffice
    if node_class in NOTES:
        return screen_h
    # If the node is returning a value greater than the default, then we
    # assume that the call was made after node creation, unless the node
    # happens to be one of the classes which add a postage stamp
    # by default.
    tile_h = utils.pref('TileHeight')
    if screen_h - tile_h > 3 and node_class not in AUTO_POSTAGES:
        return screen_h
    # all other nodes, we need to do the work to add up the base height
    # to any labels that are included
    base_h = screen_h if screen_h else tile_h
    # each line of text in the label will have a height determined by:
    #    * font size in pixels
    #    * a one-pixel buffer
    try:
        font_size = node['note_font_size'].getValue()
    except NameError:
        font_size = utils.pref('UIFontSize')
    try:
        font_name = node['note_font'].value()
    except NameError:
        font_name = utils.pref('UIFont')
    else:
        # due to a bug in previous versions of NUKE, occassionally our
        # font names got corrupted by adding 'Bold' to the font name
        while font_name.endswith('Bold Bold'):
            font_name = ' '.join(font_name.split(' ')[-1])
    # because the node might use a font other than the default, we have
    # to get the font-size in pixels using PyQt
    font = QFont(font_name, font_size)
    ui_font_h = QFontMetrics(font).height()
    padding_per_line = ui_font_h + 1
    # the full label will include the user notes and any autolabel lines
    full_label = nuke.runIn(node.fullName(), 'nuke.autolabel()')
    lines = full_label.split('\n')
    added_h = padding_per_line * (len(lines) - 1)

    # ------------------- Postage Stamp Sizes ------------------------------ #
    # postage stamps add height in relation to the width of the node
    try:
        has_postage_stamp = node['postage_stamp'].value()
    except NameError:
        return base_h + added_h
    else:
        if not has_postage_stamp:
            return base_h + added_h
    # Only add the postage stamp size if it has been added manually
    if node_class not in AUTO_POSTAGES:
        tile_w = utils.pref('TileWidth')
        added_h += (int(float(tile_w) / sqrt(3)) + 2)
    return base_h + added_h

def true_width(node=None):
    """return the true width of the node in screen space"""
    node_class = node.Class()
    if node_class in DOTS:
        return true_height(node)
    elif node_class in THREE_DS:
        return true_height(node)
    elif node_class in NOTES:
        return node.screenWidth()
    else:
        return utils.pref('TileWidth')


# ------------------------------------ Node Collision and Distance Search -- #
def node_distance(node_one, node_two):
    """get the distance between two nodes"""
    return _2d_distance(center(node_one), center(node_two))

def _2d_distance(p_one, p_two):
    """helper function - just the distance formula"""
    return sqrt(sum(pow((p_one[i] - p_two[i]), 2) for i in range(2)))

def collides(node_one, node_two):
    """returns True if two node bounding boxes overlap"""
    node_one = node_one if node_one else nuke.selectedNodes()[0]
    node_two = node_two if node_two else nuke.selectedNodes()[1]
    minx_one, miny_one, maxx_one, maxy_one = bounding_box(node_one)
    minx_two, miny_two, maxx_two, maxy_two = bounding_box(node_two)
    if maxx_one < minx_two:
        return False
    elif minx_one > maxx_two:
        return False
    elif maxy_one < miny_two:
        return False
    elif miny_one > maxy_one:
        return False
    else:
        return True

# --------------------------------------------------- Sorting by Position -- #
def xmost_node(nodes=None, axis='y', min_max=max):
    """returns the node furthest in any given direction. Expects final
    argument to be either min or max func, and axis is a string
    representing the y or x directions
    NOTE: remember that y-values are inverted in the NUKE DAG
    """
    search = 3
    if axis == 'y':
        if min_max == max:
            search = 3
        elif min_max == min:
            search = 1
    elif axis == 'x':
        if min_max == max:
            search = 2
        elif min_max == min:
            search = 0
    node_bounding_boxes = [(n, bounding_box(n)) for n in nodes]
    return min_max(node_bounding_boxes, key=lambda x: x[1][search])[0]

# ------------------------------------------------- Angular Calculations -- #
def vector_between(node_one, node_two):
    """returns the unit vector drawn from node_one to node_two"""
    pos_one = center(node_one)
    pos_two = center(node_two)
    raw_vector = ((pos_two[0] - pos_one[0]), (pos_two[1] - pos_one[1]))
    normalized_vector = [raw_vector[i] / max(raw_vector) for i in range(1)]
    return normalized_vector

def aligned_on_axis(node_one, node_two, axis):
    """returns true if the nodes are aligned on the given axis"""
    pos_one = center(node_one)
    pos_two = center(node_two)
    i = 0 if axis == 'y' else 1
    return True if pos_one[i] == pos_two[i] else False

def axis_aligned(node_one, node_two):
    """returns the axis two nodes are aligned along"""
    pos_one = center(node_one)
    pos_two = center(node_two)
    if pos_one[0] == pos_two[0]:
        return 'x'
    elif pos_one[1] == pos_two[1]:
        return 'y'
    else:
        return None

def is_aligned(node_one, node_two):
    """returns True if the nodes are aligned on any axis"""
    pos_one = center(node_one)
    pos_two = center(node_two)
    return any(pos_one[i] == pos_two[i] for i in range(2))
